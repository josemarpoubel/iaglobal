# iaglobal/graphs/nodes/no_integrator.py

from __future__ import annotations
import logging
import time
import pkgutil
import importlib
from typing import Dict, Any, Callable, Optional

from iaglobal.evolution.skills.skill_registry import SkillRegistry
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.graphs.node import Node
from iaglobal.graphs.pipeline_definition import PIPELINE_SKILLS
from iaglobal.graphs.artifact import SolutionArtifact
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger("ia-global")

_default_registry = SkillRegistry()
_FALLBACK_RUN_FN_CACHE: Dict[str, Callable] = {}

# =====================================================================
# HANDLER PRINCIPAL DO NÓ (Exportado para carregamento dinâmico)
# =====================================================================

async def run_integrator(ctx: dict) -> dict:
    """
    Nó executor de integração. Mapeado dinamicamente para o Singleton central.
    Injeta telemetria estrita para o JointOptimizationLoop de forma passiva.
    """
    start_time = time.time()
    
    # Busca ajudantes de contexto do Singleton (Nodes)
    task = ctx.get("task", "") or ctx.get("input", {}).get("task", "")
    memory = ctx.get("memory", {})

    code_parts = []
    files = {}
    source_count = 0
    last_artifact = None

    sources = [
        ("frontend_builder", "frontend"),
        ("backend_builder", "backend"),
        ("database_builder", "database"),
        ("api_builder", "api"),
    ]

    for source_key, source_label in sources:
        artifact = memory.get(source_key, {}).get("output")
        if artifact is None:
            continue

        last_artifact = artifact
        source_count += 1

        if isinstance(artifact, str) and artifact.strip():
            code_parts.append(f"# === {source_label.upper()} ===\n{artifact}")
            files[f"{source_label}.py"] = artifact
        elif hasattr(artifact, "code") and artifact.code:
            code_parts.append(f"# === {source_label.upper()} ===\n{artifact.code}")
            files[f"{source_label}.py"] = artifact.code
        elif isinstance(artifact, dict):
            for key in ("code", "output", "content"):
                val = artifact.get(key)
                if val and isinstance(val, str) and val.strip():
                    code_parts.append(f"# === {source_label.upper()} ===\n{val}")
                    files[f"{source_label}.py"] = val
                    break

    if last_artifact and hasattr(last_artifact, "files") and last_artifact.files:
        files.update(last_artifact.files)

    integrated_code = "\n\n".join(code_parts) if code_parts else ""
    latency_ms = (time.time() - start_time) * 1000.0

    logger.info("[INTEGRATOR] Integrados %d fontes, total de %d caracteres", source_count, len(integrated_code))

    # Retorno estruturado cumprindo estritamente a seção 3 do AGENTS.md
    return {
        "output": {"code": integrated_code, "files": files, "source_count": source_count},
        "integrated_code": integrated_code,
        "files": files,
        "source_count": source_count,
        "execution_metrics": {
            "model": "deterministic_integrator",
            "success": True,
            "latency": latency_ms,
            "cost": 0.0  # Processamento local em memória
        }
    }

# =====================================================================
# ECOSSISTEMA DE REGISTRO E GRAFO DE SKILLS
# =====================================================================

def register_all(orchestrator):
    """
    Auto-registra nós para o orquestrador legado evitando colisões com a raiz.
    """
    logger.info("🧩 [INTEGRATOR] Analisando registros legados de nós...")
    import iaglobal.graphs.nodes as nodes_pkg
    
    registered_nodes = getattr(orchestrator, "registered_nodes", set())
    
    for _, name, _ in pkgutil.iter_modules(nodes_pkg.__path__):
        if name.startswith("_") or name == "no_integrator":
            continue
            
        if name in registered_nodes:
            continue
            
        try:
            module_path = f"iaglobal.graphs.nodes.{name}"
            module = importlib.import_module(module_path)
            register_fn = getattr(module, f"register_{name}", getattr(module, "register", None))
            
            if register_fn and callable(register_fn):
                register_fn(orchestrator)
                if hasattr(orchestrator, "registered_nodes"):
                    orchestrator.registered_nodes.add(name)
        except Exception as e:
            logger.error(f"❌ [INTEGRATOR] Ignorando falha controlada no arquivo {name}: {e}")


def build_graph_from_skills(orchestrator: Any, registry: Optional[SkillRegistry] = None) -> ExecutionGraph:
    """
    Gera o DAG de execução a partir das propriedades de PIPELINE_SKILLS de forma isolada.
    """
    registry = registry or _default_registry
    graph = ExecutionGraph()
    missing_skills: list[str] = []
    fallback_skills: list[str] = []

    logger.info("[SKILL-GRAPH] Construindo DAG com %d skills...", len(PIPELINE_SKILLS))

    from iaglobal.immunity.emergent_behavior_detector import EmergentBehaviorDetector
    _emergence = EmergentBehaviorDetector()

    for skill_name, opts in PIPELINE_SKILLS:
        try:
            skill = registry.get(skill_name)
            run_fn = skill.run_fn if skill and skill.run_fn else _get_fallback_run_fn(skill_name, orchestrator)

            if run_fn is None:
                missing_skills.append(skill_name)
                continue

            node_name = opts.get("name", skill_name)
            depends_on = list(opts.get("depends_on", []))
            strategy = opts.get("strategy", "general")
            critical = bool(opts.get("critical", False))

            # Filtros de imunidade cognitiva contra código malicioso
            dep_check = _emergence.check_dependencies(node_name, depends_on)
            if dep_check["has_issues"]:
                for issue in dep_check["issues"]:
                    logger.warning("[IMMUNITY] Falha detectada: %s", issue.get("chain", node_name))

            if skill and skill.run_fn:
                # Transforma a skill em nó e anexa ao grafo do pipeline
                node = skill.to_node(name=node_name, depends_on=depends_on, strategy=strategy, critical=critical)
                graph.add_node(node)
        except Exception as e:
            logger.error("[SKILL-GRAPH] Fail-safe ativado para a skill %s: %s", skill_name, e)

    return graph

def _get_fallback_run_fn(skill_name: str, orchestrator: Any) -> Optional[Callable]:
    if skill_name in _FALLBACK_RUN_FN_CACHE:
        return _FALLBACK_RUN_FN_CACHE[skill_name]
    return None


