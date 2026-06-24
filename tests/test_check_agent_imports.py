"""Check agent top-level exports that are never imported elsewhere."""
import ast, re
from pathlib import Path

agents_dir = Path("iaglobal/agents")
source_dir = Path("iaglobal")

agent_exports = {}
for f in sorted(agents_dir.rglob("*.py")):
    if f.name == "__init__.py":
        continue
    rel = str(f.relative_to(source_dir))
    try:
        tree = ast.parse(f.read_text())
        exports = []
        for node in ast.walk(tree):
            # Only top-level class/function definitions
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if isinstance(node, ast.ClassDef) or \
                   (isinstance(getattr(node, 'parent', None), ast.Module) or \
                    any(isinstance(parent, ast.Module) for parent in ast.walk(tree) if hasattr(parent, 'body') and node in parent.body if isinstance(parent, ast.Module))):
                    pass  # We'll handle this differently
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if isinstance(node.parent, ast.Module) if hasattr(node, 'parent') else False:
                    exports.append(node.name)
        if exports:
            agent_exports[rel] = exports
    except:
        pass

# Better approach: only top-level names
agent_exports = {}
for f in sorted(agents_dir.rglob("*.py")):
    if f.name == "__init__.py":
        continue
    rel = str(f.relative_to(source_dir))
    try:
        tree = ast.parse(f.read_text())
        exports = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                exports.append(node.name)
        if exports:
            agent_exports[rel] = exports
    except Exception as e:
        print(f"  PARSE ERROR {rel}: {e}")

# Build content lookup
all_files = {}
for f in sorted(source_dir.rglob("*.py")):
    if "__pycache__" in str(f) or "venv" in str(f):
        continue
    try:
        all_files[str(f)] = f.read_text()
    except:
        pass

total_orphans = 0
deaths_by_file = {}  # file -> [names]

for agent_file, exports in sorted(agent_exports.items()):
    alt_module = f"iaglobal.agents.{Path(agent_file).name.replace('.py', '')}"
    orphans = []
    for name in exports:
        if name.startswith("__"):
            continue
        imported = False
        for filepath, content in all_files.items():
            # Skip the file itself
            if agent_file in filepath:
                continue
            for module in [agent_file.replace("/", ".").replace(".py", ""), alt_module]:
                # from module import ..., Name, ...
                if re.search(rf"from\s+{re.escape(module)}\s+import\s+.*\b{re.escape(name)}\b", content):
                    imported = True
                    break
                # import module  (then used as module.Name)
                if re.search(rf"import\s+{re.escape(module)}", content):
                    imported = True
                    break
            if imported:
                break
        if not imported:
            orphans.append(name)
    
    if orphans:
        deaths_by_file[agent_file] = orphans
        total_orphans += len(orphans)

print(f"=== TOP-LEVEL EXPORTS NUNCA IMPORTADOS ({total_orphans}) ===\n")
for f, names in sorted(deaths_by_file.items()):
    print(f"  {f}:")
    for n in names:
        print(f"    - {n}")
    print()
