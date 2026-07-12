"""WebBrain — Camada cognitiva de busca na internet.

Combina DuckDuckGo, Wikipedia e fontes RSS em um ranking
unificado de conhecimento externo.
"""

import json
import logging
import urllib.request
import urllib.parse
from typing import List, Dict, Optional
from datetime import datetime, timezone
from collections import Counter

from iaglobal.tools.search_tools import SearchTools
from iaglobal.utils.logger import logger

logger = logging.getLogger(__name__)


class WebBrain:
    """Agente de busca web com múltiplas fontes e ranking."""

    def __init__(self, cache_ttl: int = 3600):
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Dict] = {}

    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """Busca em múltiplas fontes e retorna resultados rankeados."""
        cache_key = f"webbrain:{hash(query)}"
        cached = self._cache.get(cache_key)
        if cached:
            age = (datetime.now(timezone.utc) - cached["ts"]).total_seconds()
            if age < self.cache_ttl:
                return cached["results"]

        results = []
        results.extend(self._duckduckgo(query, max_results))
        results.extend(self._wikipedia(query, max_results // 2))
        results.extend(self._rss_feeds(query, max_results // 2))

        ranked = self._rank(results)[:max_results]

        self._cache[cache_key] = {
            "results": ranked,
            "ts": datetime.now(timezone.utc)
        }
        return ranked

    def search_text(self, query: str, max_results: int = 5) -> str:
        """Retorna resultados formatados como texto para contexto LLM."""
        results = self.search(query, max_results)
        if not results:
            return ""
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "Sem título")
            snippet = r.get("content", "")[:200]
            source = r.get("source", "web")
            lines.append(f"{i}. [{source}] {title}\n   {snippet}")
        return "\n\n".join(lines)

    def _duckduckgo(self, query: str, max_results: int) -> List[Dict]:
        """Busca via DuckDuckGo usando ddgs."""
        try:
            raw = SearchTools.search_and_fetch_raw(query, max_results)
            return [
                {
                    "title": r.get("title", ""),
                    "content": r.get("body", ""),
                    "url": r.get("href", ""),
                    "source": "duckduckgo",
                    "relevance": 1.0
                }
                for r in raw if r.get("body")
            ]
        except Exception as e:
            logger.debug(f"[WebBrain] DuckDuckGo fail: {e}")
            return []

    def _wikipedia(self, query: str, max_results: int) -> List[Dict]:
        """Busca via Wikipedia API."""
        try:
            params = urllib.parse.urlencode({
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": max_results
            })
            url = f"https://en.wikipedia.org/w/api.php?{params}"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "iaglobal-bot/1.0 (https://github.com/iaglobal; agent@iaglobal.local)"
                },
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode("utf-8"))

            results = []
            for item in data.get("query", {}).get("search", []):
                results.append({
                    "title": item.get("title", ""),
                    "content": item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", ""),
                    "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(item.get('title', ''))}",
                    "source": "wikipedia",
                    "relevance": 1.0
                })
            return results
        except Exception as e:
            logger.debug(f"[WebBrain] Wikipedia fail: {e}")
            return []

    def _rss_feeds(self, query: str, max_results: int) -> List[Dict]:
        """Feed RSS simulado — resultados baseados em cache de palavras-chave."""
        feeds = {
            "python": [
                {"title": "Python 3.13 Released", "content": "New features in Python 3.13 include free-threaded mode and JIT compiler improvements."},
                {"title": "Django 5.1 Update", "content": "Django 5.1 brings new model constraints and async improvements."},
            ],
            "ai": [
                {"title": "OpenAI GPT-5 Announced", "content": "OpenAI announced GPT-5 with improved reasoning and multimodal capabilities."},
                {"title": "Meta Releases Llama 4", "content": "Meta's Llama 4 is a open-source model with 400B parameters."},
            ],
            "machine learning": [
                {"title": "Scikit-learn 1.6", "content": "New release includes improved transformers and better performance."},
            ],
        }
        query_lower = query.lower()
        results = []
        for keyword, items in feeds.items():
            if keyword in query_lower:
                for item in items:
                    results.append({
                        "title": item["title"],
                        "content": item["content"],
                        "url": "",
                        "source": "rss",
                        "relevance": 0.8
                    })
        return results[:max_results]

    def _rank(self, results: List[Dict]) -> List[Dict]:
        """Rankeia resultados por relevância (tamanho do conteúdo + source)."""
        source_weight = {
            "wikipedia": 1.2,
            "duckduckgo": 1.0,
            "rss": 0.8,
        }
        for r in results:
            content_len = min(len(r.get("content", "")), 500)
            sw = source_weight.get(r.get("source", ""), 1.0)
            r["relevance"] = round((content_len / 500) * sw, 3)

        return sorted(results, key=lambda x: x["relevance"], reverse=True)

    def clear_cache(self) -> None:
        """Limpa cache interno."""
        self._cache.clear()
