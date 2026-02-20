import os
from enum import Enum

class ProjectType(str, Enum):
    MONOLITH = "MONOLITH"
    MICROSERVICES = "MICROSERVICES"
    UNKNOWN = "UNKNOWN"

class ProjectDetectionService:
    def __init__(self):
        # Files that indicate a service boundary or project root
        self.dependency_files = {"requirements.txt", "package.json", "pom.xml", "go.mod", "pyproject.toml"}

    def detect_project_type(self, root_path: str) -> ProjectType:
        """
        Scans the project structure to determine if it's a Monolith or Microservices.
        Strategy:
        - If dependency files exist ONLY at root -> MONOLITH
        - If dependency files exist in sub-directories -> MICROSERVICES
        """
        has_root_deps = False
        has_sub_deps = False

        # Walk through the directory
        for root, dirs, files in os.walk(root_path):
            # Calculate depth to distinguish root from sub-directories
            rel_path = os.path.relpath(root, root_path)
            depth = 0 if rel_path == "." else rel_path.count(os.sep) + 1

            # Check for dependency files in current folder
            found_deps = any(f in self.dependency_files for f in files)

            if found_deps:
                if depth == 0:
                    has_root_deps = True
                else:
                    has_sub_deps = True

        # Decision Logic [Source: 26, 27]
        if has_sub_deps:
            # Even if it has root deps (shared libs), if it has sub-deps, it's likely a monorepo/microservices
            return ProjectType.MICROSERVICES
        elif has_root_deps and not has_sub_deps:
            return ProjectType.MONOLITH
        else:
            return ProjectType.UNKNOWN