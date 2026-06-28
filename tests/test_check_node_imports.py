"""Check if nodes import agents that exist but by a wrong name."""
import ast, re
from pathlib import Path

nodes_dir = Path("iaglobal/graphs/nodes")

# Collect what each node file actually imports from agents
print("=== NODES QUE IMPORTAM DE AGENTS ===")
for f in sorted(nodes_dir.glob("no_*.py")):
    content = f.read_text()
    imports = re.findall(r"from\s+(iaglobal\.agents\.[\w.]+)\s+import\s+(.+)", content)
    for module, names in imports:
        names_clean = [n.strip().split(" as ")[0] for n in names.split(",")]
        print(f"  {f.name}:")
        print(f"    from {module} import {', '.join(names_clean)}")
    if not imports:
        # Check direct imports
        imports2 = re.findall(r"import\s+(iaglobal\.agents\.[\w.]+)", content)
        if imports2:
            for m in imports2:
                print(f"  {f.name}: import {m}")
print()

# Now check if those imports actually resolve to the real agent files
print("=== VERIFICANDO SE IMPORTS RESOLVEM ===")
agents_dir = Path("iaglobal/agents")
errors = []
for f in sorted(nodes_dir.glob("no_*.py")):
    content = f.read_text()
    for match in re.finditer(r"from\s+(iaglobal\.agents\.(\w+(?:\.\w+)*))\s+import\s+(.+)", content):
        module_path = match.group(1)
        module_name = match.group(2)
        imported_names = [n.strip().split(" as ")[0] for n in match.group(3).split(",")]
        
        # Check if agent file exists
        agent_file = agents_dir / f"{module_name.split('.')[-1]}.py"
        if not agent_file.exists():
            # Check subpackage
            parts = module_name.split(".")
            agent_sub = agents_dir
            for p in parts:
                if p == "agents":
                    continue
                agent_sub = agent_sub / p
            agent_file_py = agent_sub.with_suffix(".py")
            agent_file_init = agent_sub / "__init__.py"
            
            if agent_file_py.exists():
                agent_file = agent_file_py
            elif agent_file_init.exists():
                agent_file = agent_file_init
            else:
                agent_file = None
        
        if agent_file and agent_file.exists():
            with open(agent_file) as af:
                agent_content = af.read()
            tree = ast.parse(agent_content)
            defined = set()
            for node in ast.iter_child_modules(tree) if hasattr(ast, 'iter_child_modules') else []:
                pass
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined.add(node.name)
                elif isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            defined.add(t.id)
            
            for n in imported_names:
                if n not in defined:
                    errors.append(f"  {f.name}: importa '{n}' de {module_path} mas nao encontrado em {agent_file.name}")
        else:
            errors.append(f"  {f.name}: modulo {module_path} nao encontrado (arquivo: {agent_file})")

if errors:
    print("\n".join(errors))
else:
    print("  Todos os imports dos nodes resolvem corretamente!")
