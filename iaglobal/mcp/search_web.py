# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/mcp/search_web.py
"""
WebSearchTool — busca web com cache e fallback para ferramentas externas MCP.
"""

import time
from typing import Any

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.mcp.search_web")


class WebSearchTool:
    """Tool MCP para busca web com cache interno."""

    def __init__(self, cache_ttl: int = 300):
        self._cache: dict[str, dict] = {}
        self._cache_ttl = cache_ttl

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Busca web usando duckduckgo-search com fallback a aiohttp."""
        cache_key = f"search:{query}:{max_results}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        results = await self._try_duckduckgo(query, max_results)
        if not results:
            results = await self._try_aiohttp_fallback(query, max_results)

        self._set_cache(cache_key, results)
        return results

    async def fetch_page(self, url: str, timeout: int = 15) -> str | None:
        """Fetch do conteúdo de uma URL."""
        cache_key = f"fetch:{url}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached[0]["content"] if cached else None

        content = await self._fetch_url(url, timeout)
        if content:
            self._set_cache(cache_key, [{"content": content}])
        return content

    async def _try_duckduckgo(
        self, query: str, max_results: int
    ) -> list[dict[str, Any]]:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                results = []
                for r in ddgs.text(query, max_results=max_results):
                    results.append(
                        {
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", ""),
                            "source": "duckduckgo",
                        }
                    )
                return results
        except Exception as e:
            logger.warning("DuckDuckGo falhou: %s", e)
            return []

    async def _try_aiohttp_fallback(
        self, query: str, max_results: int
    ) -> list[dict[str, Any]]:
        try:
            import aiohttp

            url = f"https://lite.duckduckgo.com/lite/?q={query.replace(' ', '+')}"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        return self._parse_html_results(text, max_results)
        except Exception as e:
            logger.warning("Fallback aiohttp falhou: %s", e)
        return []

    async def _fetch_url(self, url: str, timeout: int) -> str | None:
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    if resp.status == 200:
                        return await resp.text()
        except Exception as e:
            logger.warning("Fetch de URL falhou: %s %s", url, e)
        return None

    def _parse_html_results(self, html: str, max_results: int) -> list[dict[str, Any]]:
        results = []
        import re

        links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', html)
        snippets = re.findall(r'<td class="result-snippet">([^<]+)</td>', html)
        for i, (url, title) in enumerate(links[:max_results]):
            results.append(
                {
                    "title": title.strip(),
                    "url": url,
                    "snippet": snippets[i].strip() if i < len(snippets) else "",
                    "source": "duckduckgo-lite",
                }
            )
        return results

    def _get_from_cache(self, key: str) -> list[dict[str, Any]] | None:
        entry = self._cache.get(key)
        if entry:
            age = time.time() - entry["timestamp"]
            if age < self._cache_ttl:
                return entry["data"]
            del self._cache[key]
        return None

    def _set_cache(self, key: str, data: list[dict[str, Any]]):
        self._cache[key] = {"data": data, "timestamp": time.time()}
        if len(self._cache) > 100:
            self._evict_oldest()

    def _evict_oldest(self):
        oldest = min(self._cache.keys(), key=lambda k: self._cache[k]["timestamp"])
        del self._cache[oldest]
