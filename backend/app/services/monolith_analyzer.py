import os
import json
from typing import Dict, List, Set
from tree_sitter_languages import get_language, get_parser

class MonolithAnalyzer:
    def __init__(self, target_dir: str):
        self.target_dir = os.path.abspath(target_dir)
        self.parsers = {}
        self.languages = {}
        
        # We will focus on Python and TS/JS for the initial implementation
        for lang in ["python", "javascript", "typescript"]:
            try:
                self.parsers[lang] = get_parser(lang)
                self.languages[lang] = get_language(lang)
            except Exception as e:
                print(f"⚠️ Could not load tree-sitter language {lang}: {e}")

        self.ignore_dirs = {"node_modules", "venv", ".git", "__pycache__", "dist", "build"}
        self.internal_modules = set() # To track files that belong to our project
        self.dependency_graph: Dict[str, List[str]] = {}

    def _get_lang(self, filename: str) -> str:
        if filename.endswith(".py"): return "python"
        if filename.endswith((".js", ".jsx")): return "javascript"
        if filename.endswith((".ts", ".tsx")): return "typescript"
        return None

    def _build_project_index(self):
        """Indexes all valid source files to distinguish internal vs external imports."""
        for root, dirs, files in os.walk(self.target_dir):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            for file in files:
                lang = self._get_lang(file)
                if lang:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.target_dir).replace("\\", "/")
                    self.internal_modules.add(rel_path)
                    
                    # Also map Python module paths (e.g., 'app/api/router.py' -> 'app.api.router')
                    if lang == "python":
                        mod_path = rel_path.replace(".py", "").replace("/", ".")
                        self.internal_modules.add(mod_path)

    def extract_dependencies(self) -> str:
        """Parses all files, extracts imports, and builds the graph."""
        self._build_project_index()
        
        for root, dirs, files in os.walk(self.target_dir):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            for file in files:
                lang = self._get_lang(file)
                if not lang or lang not in self.parsers:
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.target_dir).replace("\\", "/")
                
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        code = f.read()
                except Exception:
                    continue

                # Parse AST
                tree = self.parsers[lang].parse(bytes(code, "utf8"))
                root_node = tree.root_node
                
                imports = self._find_imports(root_node, lang)
                
                # Filter for INTERNAL dependencies only
                internal_deps = [imp for imp in imports if self._is_internal(imp)]
                
                if internal_deps:
                    self.dependency_graph[rel_path] = list(set(internal_deps))

        return self._serialize_graph()

    def _find_imports(self, node, lang: str) -> List[str]:
        """Recursively walks the AST to find import statements."""
        imports = []
        
        # Python: import x, from x import y
        if lang == "python":
            if node.type == "import_statement":
                for child in node.children:
                    # Catch both 'import app.db' and 'import database'
                    if child.type in ["dotted_name", "identifier"]:
                        imports.append(child.text.decode("utf8"))
                    elif child.type=="aliased_import":
                        for sub in child.children:
                            if sub.type in ["dotted_name", "identifier"]:
                                imports.append(sub.text.decode("utf8"))
            elif node.type == "import_from_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        imports.append(child.text.decode("utf8"))
        
        # JS/TS: import x from 'y', require('y')
        elif lang in ["javascript", "typescript"]:
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "string":
                        imports.append(child.text.decode("utf8").strip("'\""))
            elif node.type == "call_expression":
                # Rough check for require()
                if b"require" in node.text:
                    for child in node.children:
                        if child.type == "arguments":
                            for arg in child.children:
                                if arg.type == "string":
                                    imports.append(arg.text.decode("utf8").strip("'\""))

        for child in node.children:
            imports.extend(self._find_imports(child, lang))
            
        return imports

    def _is_internal(self, import_str: str) -> bool:
        """Checks if an imported module is part of the local codebase."""
        # Clean up relative JS/TS imports
        clean_imp = import_str.lstrip("./").lstrip("../")
        
        # Check against our index
        for mod in self.internal_modules:
            if clean_imp in mod or mod in clean_imp:
                return True
        return False

    def _serialize_graph(self) -> str:
        """Serializes the graph into a token-efficient JSON string for the LLM."""
        return json.dumps(self.dependency_graph, indent=2)

if __name__ == "__main__":
    # Test the analyzer on a dummy directory or your own backend!
    target_directory = "../../mock-mes" # Point this to a monolithic test repo
    analyzer = MonolithAnalyzer(target_directory)
    graph_json = analyzer.extract_dependencies()
    print("Internal Dependency Graph:")
    print(graph_json)