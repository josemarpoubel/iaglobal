# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
QueryExpander — Gera queries relacionadas via heurísticas para expandir busca.

Funcionalidades:
1. expand(query) → gera queries relacionadas usando regras locais
2. Sem dependência de LLM ou BanditPolicy
3. Cache de resultados para evitar recomputação

Integra com:
- SearchMiddleware (chama antes de buscar)
"""

import time
from typing import List, Optional
from dataclasses import dataclass

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.search.query_expander")

STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "has",
        "have",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "can",
        "could",
        "shall",
        "should",
        "may",
        "might",
        "must",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "about",
        "between",
        "under",
        "over",
        "how",
        "what",
        "why",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "and",
        "or",
        "but",
        "not",
        "so",
        "if",
        "than",
        "that",
        "this",
        "these",
        "those",
    }
)


@dataclass
class ExpandedQuery:
    """Query expandida com metadados."""

    original: str
    expanded: List[str]
    method: str
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "expanded": self.expanded,
            "method": self.method,
            "timestamp": self.timestamp,
        }


class QueryExpander:
    """Gera queries relacionadas usando heurísticas locais."""

    PREFIX_TEMPLATES = [
        "how to {q}",
        "{q} tutorial",
        "{q} guide",
        "{q} example",
        "{q} documentation",
        "learn {q}",
    ]

    def __init__(self):
        self._cache: dict[str, List[str]] = {}

    async def expand(self, query: str, max_queries: int = 3) -> List[str]:
        if query in self._cache:
            logger.debug("[QUERY_EXPAND] Cache hit: %s", query[:40])
            return self._cache[query][:max_queries]

        try:
            queries = self._expand_heuristic(query)

            if not queries:
                return [query]

            filtered = self._filter_queries(queries, query)

            if not filtered:
                return [query]

            self._cache[query] = filtered

            logger.info(
                "[QUERY_EXPAND] %s → %d queries: %s",
                query[:40],
                len(filtered),
                filtered[:2],
            )

            return filtered[:max_queries]

        except Exception as e:
            logger.warning("[QUERY_EXPAND] Falha: %s → retornando query original", e)
            return [query]

    def _expand_heuristic(self, query: str) -> List[str]:
        """Generate related queries using heuristic rules (no LLM)."""
        query = query.strip()
        if not query:
            return []

        results = []
        q_lower = query.lower()

        for template in self.PREFIX_TEMPLATES:
            expanded = template.format(q=query)
            if expanded.lower() != q_lower:
                results.append(expanded)

        words = query.split()
        if len(words) > 1:
            keywords = [w for w in words if w.lower() not in STOP_WORDS]
            if keywords and len(keywords) < len(words):
                kw_query = " ".join(keywords)
                if kw_query.lower() != q_lower:
                    results.append(kw_query)

        return results

    def _filter_queries(self, queries: List[str], original: str) -> List[str]:
        """Filtra queries inválidas ou duplicadas."""
        filtered = []
        original_lower = original.lower()
        original_words = set(original_lower.split())

        for q in queries:
            q_stripped = q.strip()
            q_lower = q_stripped.lower()

            if len(q_stripped) < 5:
                continue

            if q_lower == original_lower:
                continue

            q_words = set(q_lower.split())
            if len(q_words) > 0 and q_words == original_words:
                continue

            filtered.append(q_stripped)

        return filtered

    def get_stats(self) -> dict:
        """Retorna estatísticas de uso."""
        return {
            "cache_size": len(self._cache),
            "total_expansions": sum(len(v) for v in self._cache.values()),
        }

    def clear_cache(self):
        """Limpa cache de queries."""
        self._cache.clear()
        logger.info("[QUERY_EXPAND] Cache limpo")


_query_expander: Optional[QueryExpander] = None


def get_query_expander() -> QueryExpander:
    """Retorna singleton do QueryExpander."""
    global _query_expander
    if _query_expander is None:
        _query_expander = QueryExpander()
    return _query_expander


async def expand_query(query: str, max_queries: int = 3) -> List[str]:
    """Wrapper para QueryExpander.expand()."""
    expander = get_query_expander()
    return await expander.expand(query, max_queries)


def get_expansion_stats() -> dict:
    """Wrapper para QueryExpander.get_stats()."""
    return get_query_expander().get_stats()
