import os
import re
from dotenv import load_dotenv
from typing import Dict, Any, List
from pydantic import BaseModel, Field 


# Load Environment Variables
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware


# --- Services ---
from app.services.ingestion import IngestionService
from app.services.analyzer import CodeAnalyzer
from app.services.monolith_analyzer import MonolithAnalyzer
from app.services.ai_engine import AIEngine
from app.services.resource_detector import ResourceDetector
from app.services.pipeline_generator import PipelineGenerator
from app.services.packager import ProjectPackager

# --- Models ---
from app.models.project import ProjectContext
from app.models.infrastructure import InfrastructureProposal
from app.models.k8s import ServiceDefinition, K8sManifests, UpstreamDependency, EnvVar

app = FastAPI(title="Project Phoenix API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Initialize Services ---
ingestion_service = IngestionService()
analyzer = CodeAnalyzer() 
ai_engine = AIEngine()
resource_detector = ResourceDetector()
pipeline_generator = PipelineGenerator()
packager = ProjectPackager()

# --- STATE MANAGEMENT ---
project_store: Dict[str, Dict[str, Any]] = {}

# --- Request Models ---
class GenerateRequest(BaseModel):
    project_id: str
    node_id: str

class MonolithAnalyzeRequest(BaseModel):
    target_directory: str = Field(
        ..., 
        description="The absolute or relative path to the monolithic codebase to analyze."
    )

@app.post("/ingest/upload")
async def ingest_zip(file: UploadFile = File(...)):
    try:
        path = await ingestion_service.parse_zip(file)
        return {"message": "Successfully ingested ZIP", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest/git")
def ingest_git(url: str = Form(...)):
    try:
        path = ingestion_service.clone_repo(url)
        return {"message": "Successfully cloned Repo", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/upload", response_model=ProjectContext)
async def analyze_project(file: UploadFile = File(...)):
    try:
        # 1. Ingest
        project_path = await ingestion_service.parse_zip(file)
        
        # 2. Analyze
        context = analyzer.analyze_directory(project_path)
        
        # 3. Save State
        project_store[context.project_id] = {
            "context": context,
            "source_path": project_path,
            "dockerfiles": {},
            "terraform": None,
            "k8s": {},
            "pipeline": None
        }
        return context
    except Exception as e:
        print(f"Error: {str(e)}") 
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/git", response_model=ProjectContext)
def analyze_git(url: str = Form(...)):
    try:
        # 1. Ingest (Clone)
        project_path = ingestion_service.clone_repo(url)
        
        # 2. Analyze
        context = analyzer.analyze_directory(project_path)
        
        # 3. Save State
        project_store[context.project_id] = {
            "context": context,
            "source_path": project_path,
            "dockerfiles": {},
            "terraform": None,
            "k8s": {},
            "pipeline": None
        }
        
        print(f"\n✅ ANALYSIS COMPLETE!")
        print(f"🆔 PROJECT ID: {context.project_id}")
        print(f"📂 TYPE: {context.project_type}")
        print(f"📄 FILES: {len(context.nodes)}")
        print(f"🔗 EDGES: {len(context.edges)}\n")
        
        return context
    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/docker")
async def generate_docker(req: GenerateRequest):
    project_data = project_store.get(req.project_id)
    if not project_data: raise HTTPException(404, detail="Project not found")
    
    context = project_data["context"]
    
    # 1. Find the Service Node
    target_node = next((n for n in context.nodes if n.id == req.node_id), None)
    if not target_node: raise HTTPException(404, detail="Node not found")

    # --- FIX START: HYDRATE CONTEXT ---
    # We must gather the content of all files BELONGING to this service.
    # Logic: Find all nodes that have an edge pointing TO this service node.
    
    related_files = []
    children_content = ""
    
    # Identify file IDs connected to this service
    child_file_ids = [
        edge.source for edge in context.edges 
        if edge.target == req.node_id and edge.type == "DIRECT_IMPORT"
    ]

    # Fetch content
    for node in context.nodes:
        if node.id in child_file_ids:
            # We add the filename and a snippet of its content
            # Truncating huge files to prevent token overflow, but giving enough for AI to identify logic
            snippet = node.content[:1500] if node.content else ""
            children_content += f"\n--- FILE: {node.id} ---\n{snippet}\n"

            # Correction: If the service language was 'docker' (fallback), 
            # try to detect the REAL language from the files.
            if target_node.language == "docker" or target_node.language == "unknown":
                if node.language not in ["docker", "unknown"]:
                    target_node.language = node.language # Inherit language from children (e.g., found a .py file)

    # Update the node's content with this rich context before sending to AI
    # This ensures the AI sees "make-data.py" and "generate-votes.sh"
    rich_node_data = target_node.model_dump()
    rich_node_data["content"] = children_content
    # --- FIX END ---

    # UPDATE STATE: Register that this service now has a Docker image plan
    service_name = req.node_id.split('/')[0]
    context.devops_state.docker_images[service_name] = f"repo/{service_name}:latest"

    # Return a Streaming Response
    return StreamingResponse(
        ai_engine.generate_docker_stream(rich_node_data), 
        media_type="text/plain"
    )
@app.get("/infra/proposal/{project_id}", response_model=InfrastructureProposal)
def get_infra_proposal(project_id: str):
    project_data = project_store.get(project_id)
    if not project_data: raise HTTPException(404, detail="Project not found")
    return resource_detector.detect(project_data["context"])

@app.post("/infra/generate")
def generate_infra(proposal: InfrastructureProposal):
    project_data = project_store.get(proposal.project_id)
    if not project_data: raise HTTPException(404, detail="Project not found")

    if not project_data["context"].nodes:
         raise HTTPException(400, detail="No services detected. Cannot generate infrastructure for an empty project.")

    # Generate Terraform
    tf_files = ai_engine.generate_terraform(proposal)
    
    # UPDATE STATE: Capture the outputs we expect Terraform to produce
    # This allows the K8s step to know that "DB_HOST" is available.
    context = project_data["context"]
    
    # We populate standard outputs based on approved resources
    for resource in proposal.detected_resources:
        if resource.approved:
            if resource.resource_type == "database":
                context.devops_state.terraform_outputs["DB_HOST"] = "module.db.db_instance_address"
                context.devops_state.terraform_outputs["DB_PORT"] = "5432"
            elif resource.resource_type == "cache":
                context.devops_state.terraform_outputs["REDIS_HOST"] = "module.elasticache.primary_endpoint"

    project_data["terraform"] = tf_files
    return {"project_id": proposal.project_id, "terraform_files": tf_files}

@app.post("/generate/k8s", response_model=K8sManifests)
def generate_k8s_manifests(service_def: ServiceDefinition):
    project_data = project_store.get(service_def.project_id)
    if not project_data: raise HTTPException(404, detail="Project not found")
    
    context = project_data["context"]
    state = context.devops_state

    # --- STRICT GUARD CLAUSES (The "Anti-Deviation" Logic) ---

    # RULE 1: Must have a Docker Image (Phase 3)
    # We check if *this specific service* has been containerized yet.
    # We use a loose match or check the specific service name key
    if service_def.service_name not in state.docker_images:
        raise HTTPException(
            status_code=400, 
            detail=f"STEP MISSING: Dockerfile for '{service_def.service_name}' has not been generated yet. Please complete the Docker generation step first."
        )
    
    # RULE 2: Must have Infrastructure/Terraform (Phase 4)
    # If the analysis detected a database (e.g., edges pointing to 'postgres'),
    # but the user skipped the Terraform step, the K8s app will crash.
    # We check: If we have "Infrastructure Dependencies", did we run Terraform?
    
    has_infra_dependencies = any(edge.target in ["postgres", "redis", "mysql", "mongodb"] for edge in context.edges)
    
    if has_infra_dependencies and not state.terraform_outputs:
        raise HTTPException(
            status_code=400, 
            detail="STEP MISSING: This project requires Infrastructure (Database/Cache), but Terraform has not been generated. Please complete the Infrastructure step first."
        )

    # --- INTELLIGENT LINKING LOGIC ---
    
    # 1. Service Discovery (What does this service talk to?)
    # We look at the 'edges' from the analysis phase.
    upstream_deps = []
    for edge in context.edges:
        if edge.source == service_def.service_name: # If THIS service calls something else
            # It's a dependency!
            upstream_deps.append(UpstreamDependency(
                target_service=edge.target,
                connection_type="http", # Default
                suggested_env_var=f"{edge.target.upper().replace('-', '_')}_HOST"
            ))

    service_def.upstream_dependencies = upstream_deps

    # 2. Infrastructure Injection (Terraform Outputs)
    # If Terraform has been generated, we pass those outputs to the AI
    if context.devops_state.terraform_outputs:
        service_def.terraform_outputs = context.devops_state.terraform_outputs
        
        # Also auto-inject them into env_vars list if not already present
        for key, val in context.devops_state.terraform_outputs.items():
            # We add them as placeholders so the AI knows to map them
            service_def.env_vars.append(EnvVar(
                key=key,
                value=f"terraform_output:{val}", # Hint to AI
                source="terraform_output"
            ))

    # 3. Generate
    manifests = ai_engine.generate_k8s(service_def)
    project_data["k8s"][service_def.service_name] = manifests
    return manifests

@app.post("/generate/pipeline")
def generate_pipeline(project_id: str = Body(...), provider: str = Body("github")):
    project_data = project_store.get(project_id)
    if not project_data: raise HTTPException(404, detail="Project not found")

    pipeline_code = pipeline_generator.generate_github_actions(
        project_name=project_data["context"].project_name
    )
    project_data["pipeline"] = pipeline_code
    return {"pipeline_yaml": pipeline_code}

@app.get("/download/{project_id}")
def download_project(project_id: str):
    project_data = project_store.get(project_id)
    if not project_data: raise HTTPException(404, detail="Project not found")

    zip_buffer = packager.create_download_bundle(
        source_path=project_data["source_path"],
        dockerfiles=project_data["dockerfiles"],
        terraform_code=project_data["terraform"],
        k8s_manifests=project_data["k8s"],
        pipeline_yaml=project_data["pipeline"]
    )

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=phoenix_bundle_{project_id}.zip"}
    )

@app.get("/analyze/{project_id}")
def get_project_context(project_id: str):
    if project_id not in project_store:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_store[project_id]["context"]

@app.post("/api/v1/decompose-monolith", tags=["Architecture"])
async def decompose_monolith(request: MonolithAnalyzeRequest):
    """
    Analyzes a monolithic codebase and returns an AI-generated 
    Domain-Driven Design (DDD) decomposition proposal.
    """
    target_path = os.path.abspath(request.target_directory)

    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail=f"Directory not found: {target_path}")

    try:
        # Step 1: Extract the internal dependency graph using tree-sitter
        print(f"🔍 Starting local AST analysis on: {target_path}")
        analyzer = MonolithAnalyzer(target_path)
        dependency_graph_json = analyzer.extract_dependencies()

        # Safety check: Did we find anything?
        if dependency_graph_json == "{}" or not dependency_graph_json:
            raise HTTPException(
                status_code=400, 
                detail="No internal dependencies found. Ensure the directory contains Python/JS/TS files."
            )

        print(f"✅ Extracted Graph: {dependency_graph_json}")
        
        # Step 2: Pass the structural graph to Gemini for DDD analysis
        print("🧠 Sending graph to Gemini for Bounded Context decomposition...")
        proposal = await ai_engine.generate_monolith_decomposition(dependency_graph_json)

        # Handle potential AI failure gracefully
        if "error" in proposal:
             raise HTTPException(status_code=500, detail=proposal["error"])

        # Step 3: Return the structured JSON directly to the client/frontend
        return proposal

    except Exception as e:
        print(f"🔥 Error during monolith decomposition: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"status": "Phoenix Core Active"}