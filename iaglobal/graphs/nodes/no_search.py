"""Search consolidado — 9+ fontes em sequência com disk swap."""
from typing import Dict, Any, Callable, List, Tuple
import asyncio
import logging

from iaglobal.tools.search import async_search_tool
from iaglobal.tools.web_brain import WebBrain
from iaglobal.agents.search_agent import SearchAgent
from iaglobal.graphs.nodes._search_wikipedia import _wikipedia_async
from iaglobal.graphs.nodes._search_sources import (
    github_search, stackoverflow_search, grokipedia_search,
    brave_search, startpage_search, mojeek_search, qwant_search,
    searxng_search,
)
from iaglobal.graphs.nodes._search_router import run_search_router
from iaglobal.graphs.nodes._disk_swap import save_search, load_search
from iaglobal.memory.memory_error import record_error

logger = logging.getLogger(__name__)
SOURCE = "search"
_web_brain = WebBrain()
_search_agent = SearchAgent()


async def _try_source(name: str, fn: Callable, task: str, timeout: int = 12) -> str:
    try:
        candidate = fn(task)
        if asyncio.iscoroutine(candidate):
            r = await asyncio.wait_for(candidate, timeout=timeout)
        else:
            r = await asyncio.wait_for(
                asyncio.to_thread(fn, task), timeout=timeout
            )
        result_str = str(r) if r else ""
        if len(result_str) > 30:
            logger.info("[SEARCH] %s OK: %d chars", name, len(result_str))
            return result_str
    except Exception as e:
        logger.debug("[SEARCH] %s: %s", name, e)
    return ""


SOURCES: List[Tuple[str, Callable, int]] = [
    ("searxng", searxng_search, 20),
    ("router", lambda t: run_search_router(t), 20),
    ("duckduckgo", lambda t: async_search_tool(t), 15),
    ("search_agent", lambda t: _search_agent.process_task(t), 12),
    ("web_brain", lambda t: _web_brain.search_text(t, max_results=5), 12),
    ("brave", brave_search, 10),
    ("startpage", startpage_search, 10),
    ("mojeek", mojeek_search, 10),
    ("qwant", qwant_search, 10),
    ("github", github_search, 10),
    ("stackoverflow", stackoverflow_search, 10),
    ("grokipedia", grokipedia_search, 10),
    ("wikipedia", lambda t: _wikipedia_async(t), 10),
]

_SEARCH_DELAY = 3.0  # segundos entre cada fonte para evitar rate limit


async def run_search(ctx: Dict[str, Any]) -> Dict[str, Any]:
    task = str(ctx.get("input", {}).get("task", ""))
    if not task or len(task) < 5:
        record_error(SOURCE, "Empty task", {"task": task})
        return {**ctx, "output": "", "search_results": "", "success": False}

    cached = load_search(SOURCE, task)
    if cached:
        logger.info("[SEARCH] Disk cache hit: %d chars", len(cached))
        return {**ctx, "output": cached, "search_results": cached, "success": True}

    all_results = []
    for i, (name, fn, timeout) in enumerate(SOURCES):
        if i > 0:
            await asyncio.sleep(_SEARCH_DELAY)
        result = await _try_source(name, fn, task, timeout)
        if result:
            save_search(name, task, result)
            all_results.append(f"=== {name.upper()} ===\n{result}")

    combined = "\n\n".join(all_results)

    if combined:
        save_search(SOURCE, task, combined)
        logger.info("[SEARCH] Total: %d chars de %d/%d fontes", len(combined), len(all_results), len(SOURCES))
        return {**ctx, "output": combined, "search_results": combined, "success": True}

    record_error(SOURCE, "All 9 sources empty", {"task": task[:100]})
    return {**ctx, "output": "", "search_results": "", "success": False}
