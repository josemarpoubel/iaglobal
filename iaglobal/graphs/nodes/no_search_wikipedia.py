"""Search node — query conceitual (Wikipedia: definições, conceitos)."""
import json
import urllib.parse
import aiohttp
from typing import Dict, Any
import logging

from iaglobal.memory.memory_error import record_error
from iaglobal.graphs.nodes._search_shared import retry_call
from iaglobal.graphs.nodes._search_queries import generate_queries

logger = logging.getLogger(__name__)
SOURCE = "search_wikipedia"


async def _wikipedia_async(query: str) -> str:
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


async def run_search_wikipedia(ctx: Dict[str, Any]) -> Dict[str, Any]:
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
            return {**ctx, "output": result, "success": True}

    record_error(SOURCE, "Empty after all queries", {"task": task[:100]})
    return {**ctx, "output": "", "success": False}
