# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Search node — query conceitual (Wikipedia: definições, conceitos)."""
import json
import time
import urllib.parse
import aiohttp
from typing import Dict, Any
import logging

from iaglobal.memory.memory_error import record_error
from iaglobal.graphs.nodes._search_shared import retry_call, wikipedia_search
from iaglobal.graphs.nodes._search_queries import generate_queries

logger = logging.getLogger(__name__)
SOURCE = "search_wikipedia"


async def _wikipedia_async(query: str) -> str:
    return await wikipedia_search(query)


async def run_search_wikipedia(ctx: Dict[str, Any]) -> Dict[str, Any]:
    start = time.time()
    task = str(ctx.get("input", {}).get("task", ""))
    if not task or len(task) < 5:
        record_error(SOURCE, "Empty task", {"task": task})
        return {**ctx, "output": "", "success": False}

    queries = generate_queries(task)
    candidates = [queries["conceptual"], queries["general"], queries["technical"]]

    for q in candidates:
        result = await retry_call(_wikipedia_async, q, max_retries=1, base_delay=0.5, stagger=0.9)
        if result:
            logger.info("[WIKIPEDIA] Conceitual OK: %d chars (q: %.50s)", len(result), q)
            return {
                **ctx, "output": result, "success": True,
                "execution_metrics": {"success": True, "latency": time.time() - start, "cost": 0.0, "model": "local"},
            }

    record_error(SOURCE, "Empty after all queries", {"task": task[:100]})
    return {
        **ctx, "output": "", "success": False,
        "execution_metrics": {"success": False, "latency": time.time() - start, "cost": 0.0, "model": "local"},
    }
