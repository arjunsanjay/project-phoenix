from pydantic import BaseModel
from typing import List, Optional, Dict

class EnvVar(BaseModel):
    key: str
    value: Optional[str] = None
    source: str = "literal"  # literal, terraform_output, secret
    is_sensitive: bool = False

class UpstreamDependency(BaseModel):
    target_service: str
    connection_type: str = "http"  # http, grpc, queue, database
    suggested_env_var: str = "" # e.g. "PAYMENT_SERVICE_HOST"

class ServiceDefinition(BaseModel):
    project_id: str
    service_name: str
    image_name: str  # e.g., "my-repo/payment-service:latest"
    container_port: int = 8000
    replicas: int = 2
    
    # Environment Variables to inject into Deployment
    env_vars: List[EnvVar] = []
    
    # Context for the AI: "Who does this service talk to?"
    # This helps the AI write better comments and config maps
    upstream_dependencies: List[UpstreamDependency] = []
    
    # Reference to Terraform Outputs (e.g., {"db_endpoint": "terraform.rds.host"})
    # Used to resolve EnvVar values
    terraform_outputs: Optional[Dict[str, str]] = {}

class K8sManifests(BaseModel):
    # Make these Optional because a Script/Job might not have a Service or ConfigMap
    deployment_yaml: Optional[str] = "" 
    service_yaml: Optional[str] = ""
    configmap_yaml: Optional[str] = ""