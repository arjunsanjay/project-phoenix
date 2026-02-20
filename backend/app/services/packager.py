import os
import shutil
import zipfile
import io
from typing import Dict, Any

class ProjectPackager:
    def create_download_bundle(self, 
                               source_path: str, 
                               dockerfiles: Dict[str, str], 
                               terraform_code: str, 
                               k8s_manifests: Dict[str, Any], 
                               pipeline_yaml: str) -> io.BytesIO:
        
        # Create an in-memory zip file
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
            
            # 1. Add Source Code (/src)
            # We walk the original source directory and add it to the zip under /src
            for root, _, files in os.walk(source_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, source_path)
                    zf.write(full_path, arcname=f"src/{rel_path}")

            # 2. Add Dockerfiles (Root or /src)
            # We overwrite any existing Dockerfiles or place them next to their services
            for node_id, content in dockerfiles.items():
                # Assuming node_id is the file path (e.g., backend/main.py)
                # We place Dockerfile in the same folder
                folder = os.path.dirname(node_id)
                zf.writestr(f"src/{folder}/Dockerfile", content)

            # 3. Add Infrastructure (/infra)
            if terraform_code:
                zf.writestr("infra/main.tf", terraform_code)
                # Add a basic versions.tf or variables.tf if needed
                zf.writestr("infra/providers.tf", 'provider "aws" { region = "us-east-1" }')

            # 4. Add Kubernetes Manifests (/k8s)
            for service_name, manifests in k8s_manifests.items():
                # manifests is a K8sManifests object (or dict)
                base_path = f"k8s/{service_name}"
                zf.writestr(f"{base_path}/deployment.yaml", manifests.deployment_yaml)
                zf.writestr(f"{base_path}/service.yaml", manifests.service_yaml)
                zf.writestr(f"{base_path}/configmap.yaml", manifests.configmap_yaml)

            # 5. Add CI/CD (.github)
            if pipeline_yaml:
                zf.writestr(".github/workflows/deploy.yml", pipeline_yaml)

        zip_buffer.seek(0)
        return zip_buffer