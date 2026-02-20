from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class ResourceType(str, Enum):
    DATABASE = "database"
    CACHE = "cache"
    OBJECT_STORAGE = "object_storage"
    QUEUE = "queue"

class DetectedResource(BaseModel):
    resource_type: ResourceType
    engine: str  # e.g., "postgres", "redis"
    reason: str  # e.g., "Detected 'psycopg2' in imports"
    suggested_tier: str = "db.t3.micro"
    approved: bool = False  # Defaults to False (Human-in-the-loop)
    terraform_module: str

class TerraformConfig(BaseModel):
    region: str = "us-east-1"
    vpc_cidr: str = "10.0.0.0/16"
    cluster_name: str = "phoenix-cluster-01"

class InfrastructureProposal(BaseModel):
    project_id: str
    cloud_provider: str = "aws"
    terraform_config: TerraformConfig
    detected_resources: List[DetectedResource]