# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Shared utilities for search nodes — retry with backoff + cache exclusivamente em disco."""
import time
import random
import asyncio
import logging
import urllib.parse
import aiohttp
from typing import Callable, Optional

from iaglobal.graphs.nodes._disk_swap import load_search, save_search

logger = logging.getLogger(__name__)


async def wikipedia_search(query: str) -> str:
    """Busca centralizada na Wikipedia para nós de busca conceitual."""
    params = urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": query,
        "format": "json", "srlimit": 3
    })
    url = f"https://en.wikipedia.org/w/api.php?{params}"
    headers = {"User-Agent": "IAGlobal/1.0"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return ""
            data = await resp.json()
    results = []
    for item in data.get("query", {}).get("search", []):
        results.append({
            "title": item.get("title", ""),
            "snippet": item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", ""),
            "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(item.get('title', ''))}",
        })
    if not results:
        return ""
    lines = [f"• {r['title']}\n  {r['url']}\n  {r['snippet']}" for r in results]
    return "\n\n".join(lines)


async def retry_call(fn: Callable, task: str, max_retries: int = 2, base_delay: float = 1.0, stagger: float = 0.0) -> str:
    """Call a sync/async search function with retry + exponential backoff."""
    if stagger > 0:
        await asyncio.sleep(random.uniform(0, stagger))

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(fn):
                result = await fn(task)
            else:
                result = await asyncio.get_running_loop().run_in_executor(None, fn, task)
            if result and len(result) > 10:
                return result
        except Exception as e:
            last_error = str(e)
            logger.debug("[SEARCH] Attempt %d/%d failed: %s", attempt + 1, max_retries + 1, e)
        if attempt < max_retries:
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            logger.info("[SEARCH] Retry %d/%d in %.1fs...", attempt + 1, max_retries, delay)
            await asyncio.sleep(delay)
    if last_error:
        logger.warning("[SEARCH] All %d attempts failed: %s", max_retries + 1, last_error)
    return ""
