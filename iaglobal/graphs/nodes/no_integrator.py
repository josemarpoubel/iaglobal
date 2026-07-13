# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_integrator.py

from __future__ import annotations
import logging
import time
import pkgutil
import importlib
from typing import Dict, Any, Callable, Optional

from iaglobal.evolution.skills.native.skill_registry import (
    SkillRegistry,
    skill_registry as _global_registry,
)
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.graphs.pipeline_definition import PIPELINE_SKILLS

logger = logging.getLogger("ia-global")

_default_registry = _global_registry
_FALLBACK_RUN_FN_CACHE: Dict[str, Callable] = {}

from iaglobal.evolution.skills.native.skill import register_builtin_skills

register_builtin_skills()


async def run_integrator(ctx: dict) -> dict:
    start_time = time.time()
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
    return {
        "output": {
            "code": integrated_code,
            "files": files,
            "source_count": source_count,
        },
        "integrated_code": integrated_code,
        "files": files,
        "source_count": source_count,
        "execution_metrics": {
            "model": "deterministic_integrator",
            "success": True,
            "latency": latency_ms,
            "cost": 0.0,
        },
    }


def register_all(orchestrator):
    import iaglobal.graphs.nodes as nodes_pkg
    from iaglobal.genesis.lineage_gate import get_expected_token

    lineage_token = get_expected_token("integrator")

    registered_nodes = getattr(orchestrator, "registered_nodes", set())
    for _, name, _ in pkgutil.iter_modules(nodes_pkg.__path__):
        if name.startswith("_") or name == "no_integrator":
            continue
        if name in registered_nodes:
            continue
        try:
            module = importlib.import_module(f"iaglobal.graphs.nodes.{name}")
            register_fn = getattr(
                module, f"register_{name}", getattr(module, "register", None)
            )
            if register_fn and callable(register_fn):
                # Injeta o token de lineage no orquestrador para que cada nó
                # registrado herde a credencial genômica do Genesis.
                if not hasattr(orchestrator, "_lineage_token"):
                    orchestrator._lineage_token = lineage_token
                register_fn(orchestrator)
            if hasattr(orchestrator, "registered_nodes"):
                orchestrator.registered_nodes.add(name)
        except Exception as e:
            logger.error(f"❌ [INTEGRATOR] Erro no nó {name}: {e}")


def build_graph_from_skills(
    orchestrator: Any, registry: Optional[SkillRegistry] = None
) -> ExecutionGraph:
    from iaglobal.evolution.skills.native.skill_registry import (
        skill_registry as _used_registry,
    )

    registry = registry or _used_registry
    graph = ExecutionGraph()
    from iaglobal.immunity.emergent_behavior_detector import EmergentBehaviorDetector

    _emergence = EmergentBehaviorDetector()
    for skill_name, opts in PIPELINE_SKILLS:
        try:
            # CORREÇÃO: Desempacotamento de SkillEntry
            entry = registry.get(skill_name)
            skill = getattr(entry, "skill", entry)

            if not skill or not getattr(skill, "run_fn", None):
                # Fallback: cria nó dinâmico a partir de no_{skill_name}.py
                from iaglobal.graphs.nodes import (
                    create_skill_node as _create_skill_node,
                )

                node = _create_skill_node(
                    skill_name, depends_on=list(opts.get("depends_on", []))
                )
                if node:
                    graph.add_node(node)
                continue

            node_name = opts.get("name", skill_name)
            node = skill.to_node(
                name=node_name,
                depends_on=list(opts.get("depends_on", [])),
                strategy=opts.get("strategy", "general"),
                critical=bool(opts.get("critical", False)),
            )
            graph.add_node(node)
        except Exception as e:
            logger.error(f"[SKILL-GRAPH] Erro ao criar nó {skill_name}: {e}")
    return graph


def build_default_graph(*args, **kwargs):
    return build_graph_from_skills(*args, **kwargs)
