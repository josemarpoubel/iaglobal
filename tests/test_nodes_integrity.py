"""Testes de integridade estrutural da pasta iaglobal/graphs/nodes/.

Verifica:
1. Todos os arquivos de nó estão na pasta correta
2. Nenhum nó órfão fora da pasta
3. Consistência entre registry.py / topology.py e os arquivos existentes
4. Convenção de nomenclatura (no_*.py)
5. Assinatura das funções run_*
6. Import dos agentes referenciados
7. Carregamento dinâmico pelo singleton Nodes
"""
import os
import ast
import sys
import pytest
from typing import Dict, List, Set

NODES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "iaglobal", "graphs", "nodes"
)
GRAPHS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "iaglobal", "graphs"
)
IAGLOBAL_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "iaglobal"
)
AGENTS_DIR = os.path.join(IAGLOBAL_DIR, "agents")


# ── Utilitários ─────────────────────────────────────────────────


def _list_node_files() -> List[str]:
    """Lista todos os arquivos de nó (no_*.py e _*.py) na pasta nodes/."""
    if not os.path.isdir(NODES_DIR):
        return []
    return sorted(
        f for f in os.listdir(NODES_DIR)
        if f.endswith(".py") and f != "__init__.py"
    )


def _node_name_from_file(filename: str) -> str:
    """Extrai o nome do nó a partir do nome do arquivo (ex: no_coder.py -> coder)."""
    if filename.startswith("no_"):
        return filename[3:-3]
    if filename.startswith("_"):
        return filename[1:-3]
    return filename[:-3]


def _find_all_no_files_outside_nodes() -> List[str]:
    """Procura arquivos no_*.py que estejam FORA da pasta nodes/ mas dentro de graphs/."""
    if not os.path.isdir(GRAPHS_DIR):
        return []
    orphans = []
    for f in os.listdir(GRAPHS_DIR):
        if f.startswith("no_") and f.endswith(".py"):
            orphans.append(f)
    return sorted(orphans)


def _extract_run_functions(filepath: str) -> Set[str]:
    """Extrai nomes de funções run_* de um arquivo Python via AST."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (SyntaxError, UnicodeDecodeError):
        return set()
    funcs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("run_"):
            funcs.add(node.name)
    return funcs


def _extract_agent_imports(filepath: str) -> List[str]:
    """Extrai imports de iaglobal.agents de um arquivo Python via AST."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (SyntaxError, UnicodeDecodeError):
        return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("iaglobal.agents"):
            agent_module = node.module[len("iaglobal.agents."):]
            # Pega o primeiro segmento (ex: "ingestion.file_ingestion_agent" -> "ingestion")
            agent_module = agent_module.split(".")[0]
            imports.append(agent_module)
    return sorted(set(imports))


def _list_agent_modules() -> Set[str]:
    """Lista módulos de agente disponíveis (arquivos .py e subpacotes) em iaglobal/agents/."""
    if not os.path.isdir(AGENTS_DIR):
        return set()
    agents = set()
    for entry in os.listdir(AGENTS_DIR):
        entry_path = os.path.join(AGENTS_DIR, entry)
        if entry.endswith(".py") and entry != "__init__.py":
            agents.add(entry[:-3])
        elif os.path.isdir(entry_path) and not entry.startswith("__"):
            # Subpacotes como ingestion/, cognition/, etc.
            agents.add(entry)
            for f in os.listdir(entry_path):
                if f.endswith(".py") and f != "__init__.py":
                    agents.add(f"{entry}.{f[:-3]}")
    return agents


# ═══════════════════════════════════════════════════════════════════
# TESTE 1: Todos os nós estão na pasta nodes/
# ═══════════════════════════════════════════════════════════════════

def test_todos_os_arquivos_de_no_estao_em_nodes():
    """Verifica que todos os arquivos no_*.py estão dentro de iaglobal/graphs/nodes/."""
    orphans = _find_all_no_files_outside_nodes()
    assert len(orphans) == 0, (
        f"Arquivos no_*.py encontrados FORA da pasta nodes/: {orphans}. "
        "Mova-os para iaglobal/graphs/nodes/ imediatamente."
    )


# ═══════════════════════════════════════════════════════════════════
# TESTE 2: Convenção de nomenclatura
# ═══════════════════════════════════════════════════════════════════

def test_convencao_de_nomenclatura_dos_nos():
    """Verifica que arquivos de nó seguem a convenção no_<nome>.py ou _<utilitario>.py."""
    for f in _list_node_files():
        assert f.startswith("no_") or f.startswith("_"), (
            f"Arquivo '{f}' não segue a convenção de nomenclatura (no_* ou _*)."
        )


# ═══════════════════════════════════════════════════════════════════
# TESTE 3: Cada arquivo no_*.py tem pelo menos uma função run_*
# ═══════════════════════════════════════════════════════════════════

def test_cada_no_tem_funcao_run():
    """Verifica que cada arquivo no_*.py define pelo menos uma função run_*."""
    for f in _list_node_files():
        if not f.startswith("no_"):
            continue  # Arquivos _*.py podem não ter run_* (utilitários)
        filepath = os.path.join(NODES_DIR, f)
        funcs = _extract_run_functions(filepath)
        assert len(funcs) >= 1, (
            f"Arquivo '{f}' não possui nenhuma função run_*. "
            "Todo nó deve exportar ao menos uma função run_<nome>."
        )


# ═══════════════════════════════════════════════════════════════════
# TESTE 4: Consistência com topology.py e registry.py
# ═══════════════════════════════════════════════════════════════════

def test_nodes_referenciados_existem():
    """Verifica que todos os nós em registry.py e topology.py têm arquivos correspondentes."""
    node_files = {_node_name_from_file(f) for f in _list_node_files() if f.startswith("no_")}
    missing_in_registry = _check_nodes_in_file("registry.py", node_files)
    missing_in_topology = _check_nodes_in_file("topology.py", node_files)
    all_missing = missing_in_registry | missing_in_topology
    assert not all_missing, (
        f"Nós referenciados em registry.py/topology.py sem arquivo correspondente: {all_missing}"
    )


def _check_nodes_in_file(rel_filename: str, existing_nodes: Set[str]) -> Set[str]:
    """Extrai nomes de nós de registry.py ou topology.py e checa se existem."""
    filepath = os.path.join(GRAPHS_DIR, rel_filename)
    if not os.path.isfile(filepath):
        return set()
    referenced = set()
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in existing_nodes or "_" not in node.value:
                pass  # Falso positivo muito comum
        if isinstance(node, ast.List):
            for el in node.elts:
                if isinstance(el, ast.Constant) and isinstance(el.value, str):
                    if "_" in el.value:
                        referenced.add(el.value)
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    if "_" in key.value:
                        referenced.add(key.value)
    # Filtra apenas os que são nomes de nó (não strings genéricas)
    all_node_names_in_codebase = existing_nodes | {
        "architecture_validator", "fix_validator", "sandbox_validator",
        "agentmailbox", "prompt_intake", "prompt_improver", "enhancement",
        "orchestrator_agent", "pm", "requirements", "ingestion",
        "domain_analysis", "business_rules", "local_knowledge", "search",
        "knowledge", "knowledge_analyzer", "dependency", "prompt_builder",
        "technology_selection", "architect", "system_design", "api_design",
        "database_design", "security_design", "threat_modeling",
        "performance_design", "observability_design", "planner",
        "task_breakdown", "execution_plan", "coder", "multi_coder",
        "code_executor", "frontend_builder", "backend_builder", "api_builder",
        "database_builder", "test_generator", "integrator", "reviewer",
        "semantic_validator", "security_audit", "performance_audit",
        "compliance_audit", "qa", "tester", "debugger", "validator",
        "fix_validator", "debug_coder", "failure_analysis", "documentation",
        "deployment_plan", "release", "metrics", "optimization",
        "retrospective", "result_agent", "critic", "knowledge_writer",
        "memory_writer", "memory_cleaner", "evaluator", "gap_analyzer",
        "skill_generator", "evolution_committee", "pipeline_updater",
        "evolution_trigger", "scheduler", "evolution_knowledge",
        "evolution_homocysteine", "evolution_methylation",
        "evolution_skill_executor", "evolution_dynamic_registry",
        "genesis_builder", "artifact_writer", "reflexion", "multi_agent",
        "typing_agent", "interpreter", "web_classifier", "risk_analysis",
        "security", "performance",
    }
    missing = set()
    for ref in referenced:
        if ref in all_node_names_in_codebase and ref not in existing_nodes:
            missing.add(ref)
    return missing


# ═══════════════════════════════════════════════════════════════════
# TESTE 5: Todos os nós em topology.py têm arquivo na pasta
# ═══════════════════════════════════════════════════════════════════

def test_topology_consistency():
    """Verifica que todos os nós listados em PHASES e NODE_DEPENDENCIES em topology.py têm arquivo."""
    node_files = {_node_name_from_file(f) for f in _list_node_files() if f.startswith("no_")}
    sys.path.insert(0, os.path.join(IAGLOBAL_DIR, ".."))
    try:
        from iaglobal.graphs.topology import PHASES, NODE_DEPENDENCIES
    except ImportError:
        pytest.skip("topology.py não importável (dependências externas faltando)")
    finally:
        sys.path.pop(0)

    all_referenced = set()
    for phase_nodes in PHASES.values():
        all_referenced.update(phase_nodes)
    all_referenced.update(NODE_DEPENDENCIES.keys())
    for deps in NODE_DEPENDENCIES.values():
        all_referenced.update(deps)

    missing = all_referenced - node_files
    assert not missing, (
        f"Nós em topology.py sem arquivo correspondente em nodes/: {missing}"
    )


# ═══════════════════════════════════════════════════════════════════
# TESTE 6: Todos os nós em registry.py têm arquivo na pasta
# ═══════════════════════════════════════════════════════════════════

def test_registry_consistency():
    """Verifica que todos os nós registrados em registry.py têm arquivo correspondente."""
    node_files = {_node_name_from_file(f) for f in _list_node_files() if f.startswith("no_")}
    sys.path.insert(0, os.path.join(IAGLOBAL_DIR, ".."))
    try:
        from iaglobal.graphs.registry import NODE_REGISTRY
    except ImportError:
        pytest.skip("registry.py não importável (dependências externas faltando)")
    finally:
        sys.path.pop(0)

    missing = set(NODE_REGISTRY.keys()) - node_files
    assert not missing, (
        f"Nós em registry.py sem arquivo correspondente em nodes/: {missing}"
    )


# ═══════════════════════════════════════════════════════════════════
# TESTE 7: Os agentes referenciados pelos nós existem
# ═══════════════════════════════════════════════════════════════════

def test_agentes_referenciados_existem():
    """Verifica que todos os imports de iaglobal.agents em arquivos de nó referenciam módulos existentes."""
    available_agents = _list_agent_modules()
    checked = 0
    for f in _list_node_files():
        if not f.startswith("no_"):
            continue
        filepath = os.path.join(NODES_DIR, f)
        refs = _extract_agent_imports(filepath)
        for agent_mod in refs:
            checked += 1
            assert agent_mod in available_agents, (
                f"Arquivo '{f}' importa 'iaglobal.agents.{agent_mod}' "
                f"mas o módulo não existe em iaglobal/agents/."
            )
    if checked == 0 and _list_node_files():
        pytest.skip("Nenhum import de agente encontrado (pode ser normal se só há utilitários)")


# ═══════════════════════════════════════════════════════════════════
# TESTE 8: Arquivos _*.py (underscore) estão na pasta nodes/
# ═══════════════════════════════════════════════════════════════════

def test_underscore_files_em_nodes():
    """Verifica que arquivos _*.py (utilitários) estão dentro de nodes/ e não fora."""
    graphs_files = [
        f for f in os.listdir(GRAPHS_DIR)
        if f.startswith("_") and f.endswith(".py") and f != "__init__.py"
    ]
    assert len(graphs_files) == 0, (
        f"Arquivos _*.py encontrados em graphs/ (fora de nodes/): {graphs_files}. "
        "Utilitários de nó devem ficar em iaglobal/graphs/nodes/."
    )


# ═══════════════════════════════════════════════════════════════════
# TESTE 9: Número mínimo de nós esperado
# ═══════════════════════════════════════════════════════════════════

def test_numero_minimo_de_nos():
    """Verifica que a pasta nodes/ contém pelo menos 80 arquivos de nó (no_*)."""
    node_count = sum(1 for f in _list_node_files() if f.startswith("no_"))
    assert node_count >= 80, (
        f"Esperado mínimo de 80 nós (no_*.py), encontrado {node_count}. "
        "Podem faltar nós ou eles foram movidos para fora da pasta."
    )


# ═══════════════════════════════════════════════════════════════════
# TESTE 10: Carregamento dinâmico pelo Nodes singleton
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_carregamento_dinamico_nodes_singleton():
    """Verifica que o singleton Nodes carrega corretamente todas as funções run_*."""
    sys.path.insert(0, os.path.join(IAGLOBAL_DIR, ".."))
    try:
        from iaglobal.graphs.nodes import Nodes
    except ImportError as e:
        pytest.skip(f"Nodes não importável: {e}")
    finally:
        sys.path.pop(0)

    instance = Nodes()
    loaded = 0
    for attr in dir(instance):
        if attr.startswith("run_"):
            loaded += 1

    node_count = sum(1 for f in _list_node_files() if f.startswith("no_"))
    # Cada no_*.py deve ter pelo menos 1 run_*, alguns têm mais
    assert loaded >= node_count, (
        f"Nodes singleton carregou {loaded} funções run_*, "
        f"mas há {node_count} arquivos no_*.py. "
        "Verifique o carregamento dinâmico em nodes.py:_load_dynamic_nodes()."
    )


# ═══════════════════════════════════════════════════════════════════
# TESTE 11: pipeline_definition.py só referencia nós existentes
# ═══════════════════════════════════════════════════════════════════

def test_pipeline_definition_consistency():
    """Verifica que PIPELINE_SKILLS em pipeline_definition.py referencia apenas nós existentes."""
    node_files = {_node_name_from_file(f) for f in _list_node_files() if f.startswith("no_")}
    pipeline_path = os.path.join(GRAPHS_DIR, "pipeline_definition.py")
    if not os.path.isfile(pipeline_path):
        pytest.skip("pipeline_definition.py não encontrado")
    with open(pipeline_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Extrai nomes de skills do PIPELINE_SKILLS via string matching simples
    import re
    matches = re.findall(r'^\s*\(\s*"(\w+)"', content, re.MULTILINE)
    missing = set(matches) - node_files
    # Remove falsos positivos (palavras-chave que não são nomes de nó)
    known_exceptions = {"name", "strategy", "depends_on", "input", "task", "output"}
    missing = missing - known_exceptions
    assert not missing, (
        f"Nós em pipeline_definition.py sem arquivo correspondente em nodes/: {missing}"
    )
