"""Search node — query técnica (tutoriais, documentação)."""
from typing import Dict, Any
import logging

from iaglobal.agents.search_agent import SearchAgent
from iaglobal.memory.memory_vector import store
from iaglobal.memory.memory_error import record_error
from iaglobal.graphs.nodes._search_shared import retry_call
from iaglobal.graphs.nodes._search_queries import generate_queries

logger = logging.getLogger(__name__)
SOURCE = "search_agent"
_search_agent = SearchAgent()


def _process_task(task: str) -> str:
    return _search_agent.process_task(task)


async def run_search_agent(ctx: Dict[str, Any]) -> Dict[str, Any]:
    task = str(ctx.get("input", {}).get("task", ""))
    if not task or len(task) < 5:
        record_error(SOURCE, "Empty task", {"task": task})
        return {**ctx, "output": "", "search_results": "", "success": False}

    queries = generate_queries(task)
    candidates = [queries["technical"], queries["general"], queries["practical"]]

    for q in candidates:
        result = await retry_call(_process_task, q, max_retries=1, base_delay=0.5, stagger=0.6)
        if result:
            try:
                _search_agent.pesquisar_e_aprender(q)
            except Exception:
                pass
            logger.info("[SEARCH_AGENT] Técnico OK: %d chars (q: %.50s)", len(result), q)
            return {**ctx, "output": result, "search_results": result, "success": True}

    record_error(SOURCE, "Empty after all queries", {"task": task[:100]})
    return {**ctx, "output": "", "search_results": "", "success": False}
