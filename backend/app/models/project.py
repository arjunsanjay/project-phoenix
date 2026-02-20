from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime
import uuid

# Enums
class DevOpsState(BaseModel):
    # Phase 1: Docker
    docker_images: Dict[str, str] = {} # {"payment-service": "payment:v1"}
    
    # Phase 2: Infra
    detected_external_services: List[str] = [] # ["postgres", "redis"]
    terraform_outputs: Dict[str, str] = {} # {"db_endpoint": "${module.db.endpoint}"}
    
    # Phase 3: K8s
    k8s_secrets: List[str] = [] # ["db-secret"]

class ProjectType(str, Enum):
    MONOLITH = "MONOLITH"
    MICROSERVICES = "MICROSERVICES"
    UNKNOWN = "UNKNOWN"

class NodeType(str, Enum):
    FILE = "FILE"
    MODULE = "MODULE"
    SERVICE = "SERVICE" # Added for Microservices

class EdgeType(str, Enum):
    DIRECT_IMPORT = "DIRECT_IMPORT"
    HTTP_CALL = "HTTP_CALL" # Added for Microservices
    UNKNOWN = "UNKNOWN"

# Nested Models
class AnalysisMetadata(BaseModel):
    total_files: int
    scanned_at: datetime = Field(default_factory=datetime.utcnow)

class ProjectNode(BaseModel):
    id: str
    type: NodeType = NodeType.FILE
    language: str
    size_kb: float
    imports: List[str] = []
    dependencies: List[str] = []
    # CRITICAL FIX: Ensure content is carried over. 
    # Frontend likely expects 'code' or 'content', we stick to 'content' here.
    content: Optional[str] = Field(default=None, description="Raw source code content")

    model_config = ConfigDict(from_attributes=True)

class ProjectEdge(BaseModel):
    source: str
    target: str
    weight: int = 1
    type: EdgeType = EdgeType.DIRECT_IMPORT

# Main Context Model
class ProjectContext(BaseModel):
    devops_state: DevOpsState = Field(default_factory=DevOpsState)
    project_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_name: str
    project_type: ProjectType = ProjectType.UNKNOWN
    root_language: str
    detected_frameworks: List[str] = []
    analysis_metadata: AnalysisMetadata
    nodes: List[ProjectNode]
    edges: List[ProjectEdge]