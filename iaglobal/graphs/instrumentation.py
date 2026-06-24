# iaglobal/graphs/instrumentation.py

import time
import copy
from typing import Dict, Any, Optional
from iaglobal.utils.logger import logger

def trace_node_execution(node_name: str, ctx: Dict[str, Any]) -> Dict:
    """PATCH: Instrumentação obrigatória de transições."""
    return {
        "node": node_name,
        "before": copy.deepcopy(ctx.get("memory", {})),
        "input_keys": list(ctx.get("input", {}).keys()),
        "start_time": time.time(),
    }

def trace_node_completed(trace: Dict, result: Any, ctx: Dict[str, Any]) -> Dict:
    """Finaliza o trace com after e diff."""
    trace["end_time"] = time.time()
    trace["duration_ms"] = (trace["end_time"] - trace["start_time"]) * 1000
    trace["after"] = copy.deepcopy(ctx.get("memory", {}))
    trace["output_present"] = bool(result and isinstance(result, dict) and result.get("output"))
    trace["output_keys"] = list(result.keys()) if isinstance(result, dict) else []

    node_name = trace.get("node", "")
    # PATCH: Detector de silent drop
    if not trace["output_present"] and node_has_contract(node_name):
        logger.warning("[TRACE] Silent drop detectado em %s - nó sem output válido", node_name)
        trace["silent_drop"] = True

    # Integração com diff_memory: registra diferenças entre estado antes e depois
    before = trace.get("before", {})
    after = trace.get("after", {})
    if before or after:
        trace["memory_diff"] = diff_memory(before, after)

    return trace

def node_has_contract(node_name: str) -> bool:
    """Alguns nós devem ter output."""
    required_output_nodes = {"coder", "php_script", "html_form", "search", "reviewer"}
    return node_name in required_output_nodes

def diff_memory(old: Dict, new: Dict) -> Dict:
    """Diff automático de memória entre nós."""
    old_keys = set(old.keys())
    new_keys = set(new.keys())
    return {
        "added": list(new_keys - old_keys),
        "removed": list(old_keys - new_keys),
        "unchanged": list(old_keys & new_keys),
    }