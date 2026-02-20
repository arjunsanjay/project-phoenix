import os
import shutil
import uuid
from git import Repo
from fastapi import UploadFile

class IngestionService:
    def __init__(self, base_dir: str = "/tmp/phoenix_uploads"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _create_workspace(self) -> str:
        """Creates a unique temp directory for this analysis session."""
        session_id = str(uuid.uuid4())
        path = os.path.join(self.base_dir, session_id)
        os.makedirs(path, exist_ok=True)
        return path

    def clone_repo(self, url: str) -> str:
        """Clones a public Git repository. Handles tree/blob URLs automatically."""
        
        # --- 1. Sanitize the URL ---
        clean_url = url.strip().rstrip("/")
        
        # If user pasted a subdirectory link (e.g. .../tree/main/folder), strip it
        if "/tree/" in clean_url:
            clean_url = clean_url.split("/tree/")[0]
        
        # If user pasted a file link (e.g. .../blob/main/file.py), strip it
        if "/blob/" in clean_url:
            clean_url = clean_url.split("/blob/")[0]

        # --- 2. Create Workspace ---
        workspace = self._create_workspace()
        repo_path = os.path.join(workspace, "repo")
        
        # --- 3. Clone ---
        print(f"⬇️ Cloning clean URL: {clean_url} into {repo_path}...")
        
        try:
            Repo.clone_from(clean_url, repo_path)
            return repo_path
        except Exception as e:
            # Clean up the empty workspace if cloning fails
            if os.path.exists(workspace):
                shutil.rmtree(workspace)
            print(f"❌ Clone failed: {str(e)}")
            raise Exception(f"Failed to clone repository '{clean_url}'. Check if it is public.")

    async def parse_zip(self, file: UploadFile) -> str:
        """Saves and unzips an uploaded file."""
        workspace = self._create_workspace()
        zip_path = os.path.join(workspace, "upload.zip")
        extract_path = os.path.join(workspace, "extracted")

        # 1. Save the uploaded file
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Unzip using shutil 
        shutil.unpack_archive(zip_path, extract_path)
        
        return extract_path