// frontend/lib/types.ts

export type APIEndpoint = {
    path: string;
    method: string;
    purpose: string;
  };
  
  export type ProposedService = {
    service_name: string;
    bounded_context: string;
    primary_responsibility: string;
    files_and_folders: string[];
    database_tables: string[];
    exposed_endpoints: APIEndpoint[];
  };
  
  export type IntegrationPoint = {
    source_service: string;
    target_service: string;
    communication_pattern: string;
    description: string;
  };
  
  export type DecompositionProposal = {
    executive_summary: string;
    proposed_services: ProposedService[];
    integration_points: IntegrationPoint[];
    refactoring_risks: string[];
  };