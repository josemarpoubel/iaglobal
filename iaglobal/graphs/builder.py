# iaglobal/graphs/builder.py

"""
Builder: Translates per-node files into ExecutionGraph nodes.

Responsible for constructing the DAG from the 55 individual node handlers
in iaglobal.graphs.nodes package.

Dependencies: nodes package exposing a registry/or list of node names
             execution_graph module with ExecutionNode/Graph
             topology for dependencies

Updated per leiame.md:
- context_weaver added after prompt_intake
- mini_evaluator gates added
- critic moved before release
- Quality + Correction unified
"""

import asyncio
from typing import Dict, List, Callable, Any
import importlib
import os
import traceback
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.graphs.node import Node
from iaglobal.memory.memory_error import record_error
import iaglobal.graphs.topology as topology

import logging

from iaglobal.utils.logger import logger

logger = logging.getLogger("ia-global")

# List of node names in canonical order (7 phases from ROADMAP)
# Updated per leiame.md: context_weaver + mini_evaluator + critic reordering
RUN_NODE_NAMES: List[str] = [
    # Messaging (2) — roda antes de tudo para ativar mailboxes e corrigir claim
    "agentmailbox",
    "scheduler",
    # Definition (20)
    "prompt_intake", "context_weaver", "prompt_improver", "enhancement", "orchestrator_agent", "pm", "requirements",
    "domain_analysis", "business_rules", "local_knowledge", "search", "knowledge", "knowledge_analyzer", "prompt_builder", "dependency",
    "technology_selection", "architect", "system_design", "api_design",
    "database_design", "security_design", "threat_modeling",
    "performance_design", "observability_design", "architecture_validator", "mini_evaluator_post_arch",
    # Immune Check - verificação anti-parasitas
    "immune_check",
    # Planning (3)
    "planner", "task_breakdown", "execution_plan",
    # Construction (6) — ordem correta: coder → multi_coder → frontend_builder → code_executor
    "coder", "multi_coder", "frontend_builder", "code_executor", "immune_check_build", "backend_builder", "database_builder", "api_builder", "mini_evaluator_post_build",
    # Quality + Correction (unified - ciclo interno com retry)
    "test_generator", "integrator", "reviewer", "semantic_validator",
    "security_audit", "performance_audit", "compliance_audit",
    "debug_coder", "fix_validator", "failure_analysis",
    # Delivery (critic antes do release)
    "documentation", "deployment_plan", "critic", "release", "metrics", "optimization",
    "retrospective", "result_agent", "knowledge_writer", "memory_writer", "memory_cleaner",
# Metacognition (7)
     "evaluator", "gap_analyzer", "skill_generator", "sandbox_validator",
     "evolution_committee", "pipeline_updater", "evolution_trigger",
     "darwin_harness",
     "entropy_sentinel",   # Vigilância de integridade genética (FIRST!)
     "auditor_sentinel",   # Auditoria em tempo real de genesis
     "metabolic_pruning",  # Poda de fingerprints SHA3_512
     "immune_monitor",   
     "apoptosis_kill"     # Apoptose programada para parasitas
    # Evolution Core (5)
    "evolution_knowledge", "evolution_homocysteine", "evolution_methylation",
    "evolution_skill_executor", "evolution_dynamic_registry",
    "multi_coder",  # Special construction node
    "failure_analysis",  # Coleta e analisa falhas do sistema (errors.json, metrics, logs)
]


def _try_import_handler(name: str) -> Callable:
    """Attempts to import module iaglobal.graphs.nodes.<name> and return async run function.

    Expected: node files define `run_<name>` function.
    """
    try:
        mod = importlib.import_module(f"iaglobal.graphs.nodes.no_{name}")
        fn = getattr(mod, f"run_{name}", None)
        if callable(fn):
            return fn  # type: ignore
    except Exception:
        pass
    record_error("builder", f"Handler not found for node: {name}", {"node": name})
    return _noop_fn()  # type: ignore


def _noop_fn():
    async def _inner(ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": "", "success": True}
    return _inner


def build_pipeline_from_nodes(topology_spec: Any = None) -> ExecutionGraph:
    """
    Main entrypoint: build 55-node deterministic execution graph.

    Returns ExecutionGraph with nodes wired per topology dependencies.
    """
    g = ExecutionGraph("IAGlobal_v3_full_pipeline")

    # Add all 55 nodes
    def _wrap_handler(name: str, h: Callable) -> Callable:
        async def _run_handler(ctx: Dict[str, Any]) -> Dict[str, Any]:
            try:
                result = h(ctx)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except Exception as e:
                tb = traceback.format_exc()
                record_error(name, str(e), {"traceback": tb[-500:]})
                return {**ctx, "output": ""}
        return _run_handler

    for node_name in RUN_NODE_NAMES:
        handler = _try_import_handler(node_name)
        node_obj = Node(
            name=node_name,
            run=_wrap_handler(node_name, handler),
            depends_on=[],
        )
        node_obj.phase = topology.get_node_phase(node_name)
        g.add_node(node_obj)

    # Add edges according to topology
    for node_name, deps in topology.NODE_DEPENDENCIES.items(): # type: ignore
        if node_name in g.nodes:
            dst_node = g.nodes[node_name]
            for dep in deps:
                if dep in g.nodes:
                    if dep not in dst_node.depends_on:
                        dst_node.depends_on.append(dep)

    return g


__all__ = ["build_pipeline_from_nodes", "RUN_NODE_NAMES"]