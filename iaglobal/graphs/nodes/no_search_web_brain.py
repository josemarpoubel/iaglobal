"""Search node — query prática (exemplos, código, github)."""
from typing import Dict, Any
import logging

from iaglobal.tools.web_brain import WebBrain
from iaglobal.memory.memory_error import record_error
from iaglobal.graphs.nodes._search_shared import retry_call
from iaglobal.graphs.nodes._search_queries import generate_queries

logger = logging.getLogger(__name__)
SOURCE = "search_web_brain"
_web_brain = WebBrain()


def _web_brain_search(task: str) -> str:
    return _web_brain.search_text(task, max_results=5)


async def run_search_web_brain(ctx: Dict[str, Any]) -> Dict[str, Any]:
    task = str(ctx.get("input", {}).get("task", ""))
    if not task or len(task) < 5:
        record_error(SOURCE, "Empty task", {"task": task})
        return {**ctx, "output": "", "success": False}

    queries = generate_queries(task)
    candidates = [queries["practical"], queries["general"], queries["technical"]]

    for q in candidates:
        result = await retry_call(_web_brain_search, q, max_retries=1, base_delay=0.5, stagger=1.2)
        if result:
            logger.info("[WEB_BRAIN] Prático OK: %d chars (q: %.50s)", len(result), q)
            return {**ctx, "output": result, "success": True}

    record_error(SOURCE, "Empty after all queries", {"task": task[:100]})
    return {**ctx, "output": "", "success": False}
