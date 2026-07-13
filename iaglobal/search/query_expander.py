# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
QueryExpander — Gera queries relacionadas via LLM para expandir busca.

Funcionalidades:
1. expand(query) → gera 2-3 queries relacionadas
2. _call_llm(prompt) → chama LLM local via BanditPolicy
3. _parse_json_response(text) → extrai queries do JSON

Integra com:
- SearchMiddleware (chama antes de buscar)
- BanditPolicy (acesso a LLM)
"""

import json
import re
from typing import List, Optional
from dataclasses import dataclass

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.search.query_expander")


@dataclass
class ExpandedQuery:
    """Query expandida com metadados."""

    original: str
    expanded: List[str]
    model_used: str
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "expanded": self.expanded,
            "model_used": self.model_used,
            "timestamp": self.timestamp,
        }


class QueryExpander:
    """Gera queries relacionadas via LLM para expandir busca."""

    PROMPT_TEMPLATE = """
Given this search query: "{query}"

Generate 2-3 related queries that can find complementary information.
Requirements:
1. Each query must be independent and self-contained
2. Avoid obvious synonyms (e.g., "Python" → "Python language")
3. Include different angles (e.g., tutorial, documentation, practical examples)
4. Keep queries in the same language as the original

Output format (strict JSON):
{{
  "queries": [
    "related query 1",
    "related query 2",
    "related query 3"
  ]
}}

Example:
Original query: "how to create REST API in Python"
Response: {{"queries": ["step by step Flask REST API tutorial", "FastAPI endpoints documentation", "Python API code example GitHub"]}}
"""

    def __init__(self, model: str = "ollama/qwen2.5:0.5b"):
        self.model = model
        self._cache: dict[str, List[str]] = {}

    async def expand(self, query: str, max_queries: int = 3) -> List[str]:
        """
        Gera queries relacionadas.

        Args:
            query: Query original
            max_queries: Máximo de queries para retornar (default: 3)

        Returns:
            Lista de queries expandidas (pode ser vazia se LLM falhar)
        """
        # Check cache
        if query in self._cache:
            logger.debug("[QUERY_EXPAND] Cache hit: %s", query[:40])
            return self._cache[query][:max_queries]

        try:
            # Chamar LLM
            prompt = self.PROMPT_TEMPLATE.format(query=query)
            response_text = await self._call_llm(prompt)

            # Se LLM falhou (resposta vazia), retornar query original
            if not response_text or not response_text.strip():
                logger.debug("[QUERY_EXPAND] LLM falhou → fallback para query original")
                return [query]

            # Parse JSON
            queries = self._parse_json_response(response_text)

            # Se não encontrou queries no JSON, retornar original
            if not queries:
                logger.debug("[QUERY_EXPAND] JSON sem queries → fallback")
                return [query]

            # Validar e filtrar
            filtered = self._filter_queries(queries, query)

            # Se todas foram filtradas, retornar original
            if not filtered:
                logger.debug("[QUERY_EXPAND] Todas filtradas → fallback")
                return [query]

            # Cache
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
            return [query]  # Fallback: query original

    async def _call_llm(self, prompt: str) -> str:
        """Chama LLM local via BanditPolicy."""
        try:
            from iaglobal.bandit import BanditPolicy

            bandit = BanditPolicy()
            response = await bandit.generate(
                prompt=prompt,
                model=self.model,
                temperature=0.3,  # Baixa temperatura para JSON consistente
                max_tokens=500,
            )

            return response.get("output", "")

        except ImportError:
            logger.warning("[QUERY_EXPAND] BanditPolicy indisponível")
            return ""
        except Exception as e:
            logger.error("[QUERY_EXPAND] Erro ao chamar LLM: %s", e)
            return ""

    def _parse_json_response(self, text: str) -> List[str]:
        """Extrai lista de queries do JSON da resposta."""
        if not text:
            return []

        # Tentar encontrar JSON entre chaves
        json_match = re.search(r'\{[^{}]*"queries"[^{}]*\}', text, re.DOTALL)
        if not json_match:
            # Tentar bloco markdown
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", text)

        if json_match:
            try:
                data = json.loads(
                    json_match.group(0)
                    if json_match.lastindex is None
                    else json_match.group(1)
                )
                queries = data.get("queries", [])
                if isinstance(queries, list):
                    return [str(q) for q in queries]
            except (json.JSONDecodeError, AttributeError):
                pass

        # Fallback: extrair strings entre aspas
        queries = re.findall(r'"([^"]+)"', text)
        return queries if queries else []

    def _filter_queries(self, queries: List[str], original: str) -> List[str]:
        """Filtra queries inválidas ou duplicadas."""
        filtered = []
        original_lower = original.lower()
        original_words = set(original_lower.split())

        for q in queries:
            q_stripped = q.strip()
            q_lower = q_stripped.lower()

            # Pular se vazia ou muito curta
            if len(q_stripped) < 5:
                continue

            # Pular se idêntica à original (case-insensitive)
            if q_lower == original_lower:
                continue

            # Pular se é exatamente as mesmas palavras (ignorando ordem)
            q_words = set(q_lower.split())
            if len(q_words) > 0 and q_words == original_words:
                continue

            # Pular se é uma meta-query genérica (contém "como buscar" ou "query para")
            if "como buscar" in q_lower or "query para" in q_lower:
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


# Singleton global
_query_expander: Optional[QueryExpander] = None


def get_query_expander(model: str = "ollama/qwen2.5:0.5b") -> QueryExpander:
    """Retorna singleton do QueryExpander."""
    global _query_expander
    if _query_expander is None:
        _query_expander = QueryExpander(model=model)
    return _query_expander


# Funções utilitárias
async def expand_query(query: str, max_queries: int = 3) -> List[str]:
    """Wrapper para QueryExpander.expand()."""
    expander = get_query_expander()
    return await expander.expand(query, max_queries)


def get_expansion_stats() -> dict:
    """Wrapper para QueryExpander.get_stats()."""
    return get_query_expander().get_stats()
