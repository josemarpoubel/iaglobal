"""  
Nodes registry glue for IAGlobal v3 pipeline.

Exports registry and fallback utilities to integrate individual node files 
with the rest of the system.
"""

from typing import Dict, Callable, Any, List
import os
import asyncio

# manter referência pra compatibilidade graph_builder_v2/registry
NODE_REGISTRY = {}
ALL_NODE_NAMES: List[str] = [
    "agentmailbox", "prompt_intake", "prompt_improver", "enhancement", "orchestrator_agent", "pm", "requirements",
    "domain_analysis", "business_rules", "local_knowledge", "search", "knowledge", "knowledge_analyzer", "prompt_builder", "dependency",
    "technology_selection", "architect", "system_design", "api_design",
    "database_design", "security_design", "threat_modeling",
    "performance_design", "observability_design", "architecture_validator",
    "planner", "task_breakdown", "execution_plan",
    "coder", "code_executor", "frontend_builder", "backend_builder", "api_builder", "database_builder",
    "test_generator", "integrator", "reviewer", "semantic_validator",
    "security_audit", "performance_audit", "compliance_audit",
    "qa", "tester", "debugger", "validator", "fix_validator", "debug_coder",
    "documentation", "deployment_plan", "release", "metrics", "optimization",
    "retrospective", "result_agent", "critic", "memory_writer", "memory_cleaner",
    "evaluator", "gap_analyzer", "skill_generator", "sandbox_validator",
    "evolution_committee", "pipeline_updater", "evolution_trigger",
    "multi_coder"
]

# Preencher NODE_REGISTRY para compatibilidade
for node_name in ALL_NODE_NAMES:
    NODE_REGISTRY[node_name] = None

__all__ = ["NODE_REGISTRY", "create_skill_node"]

def create_skill_node(name: str, depends_on: list = None):
    """
    Creates a skill node with execution handler.
    
    Args:
        name: Node name
        depends_on: List of dependency node names (passed through to Node)
    
    Returns:
        ExecutionNode compatible object with run method
    """
    from ..execution_graph import Node
    handler = None
    
    # Try to load each node from the nodes.py file nodes list handlers
    try:
        root = __import__('iaglobal.graphs.nodes.nodes', fromlist=[name])
        nodes_obj = getattr(root, 'Nodes', None)
        if nodes_obj:
            handler = getattr(nodes_obj, f'run_{name}', None)
    except Exception:
        pass
    
    # If not found, use a noop handler to prevent crash
    if handler is None:
        async def _noop(ctx: dict):
            return {"output": f"Node {name} executed (handler missing from nodes.py)"}
        handler = _noop
    
    # Wrap sync handlers to async for ExecutionGraph compatibility
    if not asyncio.iscoroutinefunction(handler):
        original = handler
        async def async_wrapper(ctx):
            return original(ctx)
        handler = async_wrapper
    
    # Create node with depends_on for graph_builder_v2 compatibility
    node = Node(
        name=name,
        run=handler,
        depends_on=depends_on or [],
    )
    return node

def get_registry():
    return NODE_REGISTRY

# Fake orchestrators for compatibility
nodes_director_singleton = object()
