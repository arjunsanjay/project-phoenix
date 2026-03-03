import os
import json
import re
from typing import List, Dict, Any
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from app.models.infrastructure import InfrastructureProposal
from app.models.k8s import ServiceDefinition, K8sManifests
from app.models.monolith import DecompositionProposal
class AIEngine:
    def __init__(self):
        # 1. Initialize the LLM (Gemini)
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.llm = None
        
        if self.api_key:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-flash-latest", # Updated to latest stable model name
                temperature=0.2,
                google_api_key=self.api_key
            )
        
        # 2. Define Prompts

        # --- DOCKER (Phase 1) ---
        self.docker_prompt = PromptTemplate.from_template("""
        You are a Senior DevOps Engineer. Generate a production-ready Dockerfile for:
        
        Service: {entrypoint}
        Language: {language}
        Dependencies: {dependencies}
                                                          
        SOURCE CONTEXT:
        {context_dump}                                      
        
        STRICT REQUIREMENTS:
        1. Use Multi-Stage Builds (Build -> Final).
        2. Create non-root user 'appuser'.
        3. Optimize caching (copy manifest files first).
        4. Use slim/alpine images.
        5. OUTPUT: ONLY the Dockerfile content. No markdown.
        """)

        # --- TERRAFORM (Phase 2 - The Foundation) ---
        self.terraform_prompt = PromptTemplate.from_template("""
        You are a Principal Cloud Architect. Generate a AWS Terraform setup.
        
        Config:
        - Region: {region}
        - CIDR: {cidr}
        
        RESOURCES TO CREATE:
        {resources}
        
        CRITICAL REQUIREMENT (The Bridge):
        For every Database (RDS) or Cache (ElastiCache) you create, you MUST also create a 
        'kubernetes_secret' resource (provider: hashicorp/kubernetes).
        - Secret Name: 'infra-secrets' or specific service secret.
        - Data: Must contain 'db_host', 'db_password', 'redis_host' etc.
        - Why: So the Kubernetes cluster can connect to these resources immediately.

        STRICT JSON OUTPUT (No Markdown):
        Returns a JSON object with keys:
        - "main.tf": Provider, VPC, EKS, RDS, ElastiCache, Kubernetes Provider config.
        - "variables.tf": Variable definitions.
        - "outputs.tf": Must export VPC_ID, EKS_ENDPOINT, RDS_ENDPOINT.
        """)

        self.k8s_prompt = PromptTemplate.from_template("""
        You are a Kubernetes Expert. Generate YAML manifests for:
        
        App Name: {name}
        Image: {image}
        Context: {context_snippet}
        
        ENV VARS:
        {env_vars}
        
        DECISION LOGIC:
        1. Analyze the context hint. 
           - If it is a "Standard Microservice" (web server, API, listener):
             -> Generate a **Deployment** and a **ClusterIP Service**.
           - If it is a "Batch Script / One-off Task" (seed data, migration, init):
             -> Generate a **Job** (kind: Job) with `restartPolicy: OnFailure`.
             -> Do NOT generate a Service.
        
        STRICT OUTPUT (JSON):
        Return a valid JSON object with these exact keys:
        - "kind": "Deployment" or "Job"
        - "manifest_yaml": The full YAML for the Deployment or Job.
        - "service_yaml": The Service YAML (return null or empty string if it's a Job).
        - "configmap_yaml": Any config maps needed (or empty string).
        """)

        # --- MONOLITH DECOMPOSITION ---
        self.decomposition_prompt = PromptTemplate.from_template("""
        You are an Expert Enterprise Architect specializing in Domain-Driven Design (DDD) and microservices migration.
        Your task is to analyze the internal dependency graph of a tightly coupled monolithic application and propose a strategy to decouple it into independent microservices.

        INTERNAL DEPENDENCY GRAPH (Adjacency List):
        {dependency_graph}
        
        RULES FOR DECOMPOSITION:
        1. Identify "Bounded Contexts" based on the clusters of dependencies.
        2. Identify shared utilities or databases that might become bottlenecks.
        3. Determine which files belong to which new proposed microservice.
        4. Define the necessary integration points (APIs/Event buses) required to replace the internal function imports.

        STRICT OUTPUT (JSON):
        You must return a valid JSON object that strictly adheres to the following schema:
        {schema_instructions}
        
        Do not include markdown blocks, just the raw JSON.
        """)
    
    async def generate_docker_stream(self, node_data: dict):
        """Generates Dockerfile content as a stream."""
        language = node_data.get("language", "unknown")
        
        # FIX 1: Retrieve imports, but don't rely on them exclusively
        # (Service nodes might have empty imports, but the context_dump has the real data)
        imports = node_data.get("imports", [])
        
        entrypoint = node_data.get("id", "app")
        full_content = node_data.get("content", "")

        if not self.llm:
            yield "# MOCK DOCKERFILE (No API Key)\nFROM alpine"
            return

        chain = self.docker_prompt | self.llm | StrOutputParser()
        
        # FIX 2: INCREASE CONTEXT LIMIT
        # Gemini 1.5 Flash has a 1M token window. 
        # 2000 chars is too small for a multi-file context. 
        # We increase it to 20,000 to ensure we capture requirements.txt and scripts.
        safe_context_limit = 20000 
        
        async for chunk in chain.astream({
            "language": language,
            "entrypoint": entrypoint,
            "dependencies": ", ".join(imports),
            "context_dump": full_content[:safe_context_limit] # Increased from 2000
        }):
            yield chunk

    def generate_terraform(self, proposal: InfrastructureProposal) -> dict:
        """Generates Terraform infrastructure with K8s Secrets bridge."""
        approved_items = [r for r in proposal.detected_resources if r.approved]
        
        resource_summary = "\n".join(
            [f"- {r.resource_type} ({r.engine}): {r.reason}" for r in approved_items]
        ) or "No specific resources. Just VPC and EKS."

        if not self.llm:
            return {"main.tf": "# MOCK TF", "error": "No API Key"}

        chain = self.terraform_prompt | self.llm | StrOutputParser()
        
        try:
            response_text = chain.invoke({
                "region": proposal.terraform_config.region,
                "cidr": proposal.terraform_config.vpc_cidr,
                "resources": resource_summary
            })
            return self._clean_json(response_text)
        except Exception as e:
             return {"error.txt": f"AI Generation Failed: {str(e)}"}

    def generate_k8s(self, service_def: ServiceDefinition) -> K8sManifests:
        """
        Generates K8s manifests with intelligent workload detection (Job vs Deployment).
        """
        # 1. Format Env Vars for the Prompt
        formatted_envs = []
        for env in service_def.env_vars:
            # Logic: If value is "SECRET:db-secret:host", LLM knows to use valueFrom
            val = env.value if env.value else f"SECRET:infra-secrets:{env.key.lower()}"
            formatted_envs.append(f"{env.key} = {val}")
        
        env_str = "\n".join(formatted_envs)

        # 2. Generate Context Hint based on Service Name
        # If the name implies a task, we hint the AI to build a Job.
        context_hint = "Standard Microservice"
        task_keywords = ["seed", "migrate", "job", "init", "task", "batch", "cron"]
        
        if any(keyword in service_def.service_name.lower() for keyword in task_keywords):
            context_hint = "Batch Script / One-off Task"

        # 3. Mock Fallback
        if not self.llm:
            return self._generate_mock_k8s(service_def)

        # 4. AI Generation
        chain = self.k8s_prompt | self.llm | StrOutputParser()
        try:
            response_text = chain.invoke({
                "name": service_def.service_name,
                "image": service_def.image_name,
                "context_snippet": f"Type hint: {context_hint}",
                "env_vars": env_str
            })
            
            result = self._clean_json(response_text)
            
            # 5. Map Dynamic Keys to Pydantic Model
            # Note: We map the AI's 'manifest_yaml' to our model's 'deployment_yaml' field 
            # to keep the frontend compatible, even if the content is actually a Job.
            return K8sManifests(
                deployment_yaml=result.get("manifest_yaml", "") or result.get("deployment_yaml", ""),
                service_yaml=result.get("service_yaml", ""), # Will be empty for Jobs
                configmap_yaml=result.get("configmap_yaml", "")
            )
        except Exception as e:
            print(f"K8s Gen Failed: {e}")
            return self._generate_mock_k8s(service_def)
    

    async def generate_monolith_decomposition(self, dependency_graph_json: str) -> dict:
        """
        Analyzes a monolith's internal dependency graph and proposes a DDD microservices architecture.
        """
        if not self.llm:
            return {"error": "No API Key available for decomposition."}

        # We use LangChain's JsonOutputParser to automatically inject our Pydantic schema
        # instructions into the prompt, ensuring Gemini returns exactly what we need.
        parser = JsonOutputParser(pydantic_object=DecompositionProposal)
        
        chain = self.decomposition_prompt | self.llm | parser

        try:
            print("🧠 Analyzing Monolith Architecture with Gemini...")
            # We use ainvoke because architecture analysis can take a few seconds
            # and we don't want to block the FastAPI event loop.
            result = await chain.ainvoke({
                "dependency_graph": dependency_graph_json,
                "schema_instructions": parser.get_format_instructions()
            })
            
            return result
            
        except Exception as e:
            print(f"⚠️ Monolith Decomposition Failed: {e}")
            return {"error": str(e)}
        

    def _clean_json(self, text: str) -> Dict[str, Any]:
        """
        Helper to strip markdown code blocks from LLM response 
        before parsing as JSON.
        """
        # Remove ```json and ```
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```', '', text)
        return json.loads(text.strip())

    # --- MOCK HELPERS ---
    def _generate_mock_k8s(self, service):
        return K8sManifests(
            deployment_yaml=f"# Mock Deployment for {service.service_name}",
            service_yaml=f"# Mock Service for {service.service_name}",
            configmap_yaml=f"# Mock ConfigMap for {service.service_name}"
        )