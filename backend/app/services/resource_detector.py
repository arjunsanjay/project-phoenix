from typing import List
from app.models.project import ProjectContext, NodeType
from app.models.infrastructure import InfrastructureProposal, DetectedResource, TerraformConfig

class ResourceDetector:
    def detect(self, context: ProjectContext) -> InfrastructureProposal:
        detected_resources = []
        found_signatures = set() 
        
        # --- 1. Detect from Ghost Nodes (The "Detective" Results) ---
        # These are nodes created by the Analyzer when it saw 'host="db"' or 'redis("redis")'
        
        for node in context.nodes:
            # Look for the special "SERVICE" nodes marked as "infrastructure"
            if node.type == NodeType.SERVICE and node.language == "infrastructure":
                
                name = node.id.lower()
                r_type = "unknown"
                engine = "unknown"
                module = ""
                
                # Heuristic mapping based on common hostnames
                if name in ["postgres", "db", "mysql", "mariadb", "sqlserver"]:
                    r_type = "database"
                    engine = "postgres" if name in ["postgres", "db"] else name
                    module = "terraform-aws-modules/rds/aws"
                    
                elif name in ["redis", "memcached", "cache"]:
                    r_type = "cache"
                    engine = "redis"
                    module = "terraform-aws-modules/elasticache/aws"
                    
                elif name in ["rabbitmq", "kafka", "activemq", "queue"]:
                    r_type = "queue"
                    engine = name
                    module = "terraform-aws-modules/mq/aws"
                
                signature = f"{r_type}-{engine}"
                
                if signature not in found_signatures:
                    detected_resources.append(DetectedResource(
                        resource_type=r_type,
                        engine=engine,
                        reason=f"Detected active connection to '{node.id}' in source code.",
                        suggested_tier="db.t3.micro" if r_type == "database" else "cache.t3.micro",
                        approved=False, # User must click approve!
                        terraform_module=module
                    ))
                    found_signatures.add(signature)

        # --- 2. Fallback: Detect from Library Imports (The Old Method) ---
        # We keep this as a backup in case the Detective missed the connection string
        # but found the library import.
        
        library_map = {
            "python": {"psycopg2": "postgres", "boto3": "s3", "pymongo": "mongodb", "redis": "redis"},
            "javascript": {"pg": "postgres", "mongoose": "mongodb", "mysql": "mysql", "redis": "redis"},
            "java": {"postgresql": "postgres", "mysql-connector": "mysql", "jedis": "redis"},
            "go": {"pgx": "postgres", "mongo-driver": "mongodb", "go-redis": "redis"},
            "c_sharp": {"Npgsql": "postgres", "StackExchange.Redis": "redis"}
        }

        for node in context.nodes:
            if node.type != NodeType.FILE: continue

            lang = node.language.lower()
            if lang not in library_map: continue

            for lib, engine in library_map[lang].items():
                # Check imports for known libraries
                # We simply check if the library string exists in the import list
                if any(lib in imp for imp in node.imports):
                    
                    r_type = "database" if engine in ["postgres", "mysql", "mongodb"] else "cache"
                    if engine == "s3": r_type = "object_storage"
                    
                    signature = f"{r_type}-{engine}"
                    
                    # Only add if we haven't already found it via Ghost Nodes
                    if signature not in found_signatures:
                        detected_resources.append(DetectedResource(
                            resource_type=r_type,
                            engine=engine,
                            reason=f"Detected library '{lib}' in {node.id}",
                            suggested_tier="db.t3.micro" if r_type == "database" else "cache.t3.micro",
                            approved=False,
                            terraform_module=f"terraform-aws-modules/{engine}/aws"
                        ))
                        found_signatures.add(signature)

        return InfrastructureProposal(
            project_id=context.project_id,
            cloud_provider="aws",
            terraform_config=TerraformConfig(
                region="us-east-1",
                vpc_cidr="10.0.0.0/16",
                cluster_name=f"phoenix-{context.project_name.lower().replace(' ', '-')}"
            ),
            detected_resources=detected_resources
        )