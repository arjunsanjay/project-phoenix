from pydantic import BaseModel, Field
from typing import List, Optional

class APIEndpoint(BaseModel):
    path: str = Field(description="Suggested REST/gRPC endpoint path (e.g., '/api/v1/inventory/check')")
    method: str = Field(description="HTTP method (GET, POST, etc.) or protocol type")
    purpose: str = Field(description="What this endpoint does for the bounded context")

class IntegrationPoint(BaseModel):
    source_service: str = Field(description="Name of the calling service")
    target_service: str = Field(description="Name of the service being called")
    communication_pattern: str = Field(description="Synchronous (REST/gRPC) or Asynchronous (Event Bus/Kafka)")
    description: str = Field(description="Why this integration is needed based on legacy internal function calls")

class ProposedService(BaseModel):
    service_name: str = Field(description="Proposed microservice name (e.g., 'execution-service', 'inventory-service')")
    bounded_context: str = Field(description="The Domain-Driven Design (DDD) Bounded Context this service encapsulates")
    primary_responsibility: str = Field(description="A short description of what this service owns")
    files_and_folders: List[str] = Field(description="Exact file paths and directories from the monolith assigned to this service")
    database_tables: Optional[List[str]] = Field(default=[], description="Guessed database tables/entities based on ORM models")
    exposed_endpoints: List[APIEndpoint] = Field(description="APIs this service must expose to satisfy existing internal monolith dependencies")

class DecompositionProposal(BaseModel):
    executive_summary: str = Field(description="High-level explanation of the Domain-Driven Design strategy used for this monolith")
    proposed_services: List[ProposedService] = Field(description="The distinct microservices extracted from the monolith")
    integration_points: List[IntegrationPoint] = Field(description="How the new services must communicate to replace legacy code imports")
    refactoring_risks: List[str] = Field(description="Potential circular dependencies, shared utilities, or tight coupling bottlenecks")