import os
import re
from typing import List, Dict, Any, Set, Optional, Tuple
from tree_sitter_languages import get_language, get_parser
from app.models.project import ProjectContext, ProjectNode, ProjectEdge, NodeType, EdgeType, AnalysisMetadata, ProjectType

class CodeAnalyzer:
    def __init__(self):
        # 1. Initialize Parsers
        self.parsers = {}
        self.languages = {}
        
        # Supported languages
        for lang in ["python", "javascript", "typescript", "java", "go", "c_sharp"]:
            try:
                ts_lang = "c_sharp" if lang == "c_sharp" else lang 
                self.parsers[lang] = get_parser(ts_lang)
                self.languages[lang] = get_language(ts_lang)
            except Exception as e:
                print(f"⚠️ Warning: Could not load tree-sitter language {lang}: {e}")

        # 2. Service Indicators
        self.service_indicators = {
            "node": ["package.json"],
            "python": ["requirements.txt", "Pipfile", "pyproject.toml", "main.py", "app.py"],
            "java": ["pom.xml", "build.gradle"],
            "go": ["go.mod"],
            "csharp": ["*.csproj", "*.sln", "Program.cs"], # Added Program.cs as indicator
            "docker": ["Dockerfile"]
        }

        # 3. Connection Patterns (The Detective Logic)
        self.connection_patterns = [
            # Standard HTTP/HTTPS
            re.compile(r'https?://([a-zA-Z0-9-]+)(?::\d+)?', re.IGNORECASE),
            
            # Database URI (postgres://...)
            re.compile(r'(postgres|mysql|mongodb|redis|amqp)://([a-zA-Z0-9-]+)', re.IGNORECASE),
            
            # Environment Defaults: os.getenv("HOST", "mydb")
            re.compile(r'getenv\s*\(\s*["\'][A-Z_]+["\']\s*,\s*["\']([a-zA-Z0-9-]+)["\']', re.IGNORECASE),
            
            # JDBC / Spring
            re.compile(r'jdbc:(?:postgresql|mysql)://([a-zA-Z0-9-]+)', re.IGNORECASE),
            
            # --- NEW PATTERNS ADDED BELOW ---
            
            # 1. Python/General "host=" args
            # Matches: host="redis", host='db'
            re.compile(r'host\s*=\s*["\']([a-zA-Z0-9-]+)["\']', re.IGNORECASE),

            # 2. C# / .NET Connection Strings
            # Matches: "Server=db;", "Data Source=postgres;"
            re.compile(r'(?:Server|Data Source|Host)\s*=\s*([a-zA-Z0-9-]+)', re.IGNORECASE),
            
            # 3. Generic "Connect" calls with string literals
            # Matches: Connect("redis"), OpenRedisConnection("redis")
            re.compile(r'Connect(?:ion)?\s*\(\s*["\']([a-zA-Z0-9-]+)["\']', re.IGNORECASE),
        ]

        # 4. Known Infrastructure (The Safety Net)
        # If we find these exact strings in quotes, we assume a dependency.
        self.infra_keywords = {"redis", "postgres", "mysql", "mongodb", "rabbitmq", "kafka", "db"}

        self.ignore_dirs = {"node_modules", "venv", ".git", "__pycache__", "dist", "build", ".next", "target", ".idea", ".vscode", "vendor", "bin", "obj"}
        self.ignore_extensions = {".min.js", ".map", ".spec.ts", ".test.js", ".txt", ".md", ".json", ".lock", ".xml", ".yaml", ".yml", ".class", ".jar", ".properties", ".png", ".jpg", ".dll", ".pdb"}

    def _get_lang_from_ext(self, filename: str) -> str:
        if filename.endswith(".py"): return "python"
        if filename.endswith((".js", ".jsx")): return "javascript"
        if filename.endswith((".ts", ".tsx")): return "typescript"
        if filename.endswith(".java"): return "java"
        if filename.endswith(".go"): return "go"
        if filename.endswith(".cs"): return "c_sharp"
        if filename.endswith(".sh"): return "shell"
        return None

    def analyze_directory(self, root_path: str, project_name: str = "Project") -> ProjectContext:
        nodes: List[ProjectNode] = []
        edges: List[ProjectEdge] = []
        
        print(f"🔍 Starting Analysis on: {root_path}")

        # 1. Discover Services
        discovered_services = self._discover_services(root_path)
        service_names = set(discovered_services.keys())
        print(f"✅ Discovered Services: {list(service_names)}")

        # 2. Scan Files
        all_file_nodes = []
        for svc_name, svc_info in discovered_services.items():
            svc_node = ProjectNode(
                id=svc_name,
                type=NodeType.SERVICE,
                language=svc_info['lang'],
                size_kb=0,
                content=f"/* Service Detected via {svc_info['indicator']} */",
                dependencies=[]
            )
            nodes.append(svc_node)

            file_nodes = self._scan_service_files(root_path, svc_info['path'], svc_name)
            all_file_nodes.extend(file_nodes)
            nodes.extend(file_nodes)

            # Connect Files to Service
            for f_node in file_nodes:
                edges.append(ProjectEdge(source=f_node.id, target=svc_name, type=EdgeType.DIRECT_IMPORT, weight=1))

        # 3. Architecture Edge Detection
        detected_edges, ghost_nodes = self._detect_architecture_edges(all_file_nodes, service_names)
        
        edges.extend(detected_edges)
        nodes.extend(ghost_nodes)

        return ProjectContext(
            project_name=project_name,
            project_type=ProjectType.MICROSERVICES if len(service_names) > 1 else ProjectType.MONOLITH,
            root_language="mixed",
            analysis_metadata=AnalysisMetadata(total_files=len(nodes)),
            nodes=nodes,
            edges=edges,
            detected_frameworks=[]
        )

    def _discover_services(self, root_path: str) -> Dict[str, Dict]:
        services = {}
        root_indicator = self._find_indicator(root_path)
        if root_indicator:
            services["root_service"] = {"path": root_path, "lang": root_indicator[0], "indicator": root_indicator[1]}
        
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            for d in dirs:
                dir_path = os.path.join(root, d)
                indicator = self._find_indicator(dir_path)
                if indicator:
                    # Avoid duplicates if root is already a service
                    if "root_service" in services and services["root_service"]["path"] == dir_path:
                        continue
                    services[d] = {"path": dir_path, "lang": indicator[0], "indicator": indicator[1]}
        return services

    def _find_indicator(self, path: str) -> Optional[Tuple[str, str]]:
        try:
            files = os.listdir(path)
        except:
            return None
        for lang, indicators in self.service_indicators.items():
            for ind in indicators:
                if "*" in ind:
                    ext = ind.replace("*", "")
                    if any(f.endswith(ext) for f in files): return (lang, ind)
                else:
                    if ind in files: return (lang, ind)
        return None

    def _scan_service_files(self, global_root: str, service_path: str, service_name: str) -> List[ProjectNode]:
        file_nodes = []
        for root, dirs, files in os.walk(service_path):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            for file in files:
                if any(file.endswith(ext) for ext in self.ignore_extensions): continue
                lang = self._get_lang_from_ext(file)
                if not lang: continue 
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, global_root).replace("\\", "/")
                
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        code = f.read()
                    file_nodes.append(ProjectNode(
                        id=rel_path, type=NodeType.FILE, language=lang,
                        size_kb=round(os.path.getsize(full_path) / 1024, 2),
                        content=code
                    ))
                except Exception as e:
                    print(f"⚠️ Error reading {rel_path}: {e}")
        return file_nodes

    def _detect_architecture_edges(self, file_nodes: List[ProjectNode], known_services: Set[str]) -> Tuple[List[ProjectEdge], List[ProjectNode]]:
        edges = []
        ghost_nodes_map = {}
        
        # --- FIX: Track seen edges to prevent duplicates ---
        seen_edges = set()
        
        # Helper to add edge
        def add_edge(source_id, target_name):
            target_name = target_name.lower().strip()
            # Filter noise
            if target_name in ["localhost", "127.0.0.1", "0.0.0.0"] or len(target_name) < 2: return

            # --- FIX: Check for duplicates ---
            edge_key = (source_id, target_name)
            if edge_key in seen_edges:
                return
            seen_edges.add(edge_key)
            # ---------------------------------

            if target_name in known_services:
                edges.append(ProjectEdge(source=source_id, target=target_name, type=EdgeType.HTTP_CALL, weight=5))
            else:
                # Ghost Node Logic
                if target_name in self.infra_keywords or "service" in target_name:
                    if target_name not in ghost_nodes_map:
                        ghost_nodes_map[target_name] = ProjectNode(
                            id=target_name, type=NodeType.SERVICE, language="infrastructure",
                            size_kb=0, content=f"/* Detected Infrastructure: {target_name} */"
                        )
                    edges.append(ProjectEdge(source=source_id, target=target_name, type=EdgeType.HTTP_CALL, weight=3))

        for node in file_nodes:
            if not node.content: continue
            
            # 1. Regex Scan
            for pattern in self.connection_patterns:
                matches = pattern.findall(node.content)
                for match in matches:
                    target = match[0] if isinstance(match, tuple) else match
                    add_edge(node.id, target)

            # 2. Safety Net: Explicit String Search
            for keyword in self.infra_keywords:
                if f'"{keyword}"' in node.content or f"'{keyword}'" in node.content:
                     add_edge(node.id, keyword)

        return edges, list(ghost_nodes_map.values())