# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do QueryExpander — Fase 2 do RAG Autônomo.

Cobertura:
  - expand() gera queries relacionadas via heurísticas
  - _expand_heuristic gera variações
  - _filter_queries remove duplicatas e inválidas
  - Cache funciona corretamente
"""

import pytest

from iaglobal.search.query_expander import (
    QueryExpander,
    ExpandedQuery,
    expand_query,
    get_expansion_stats,
)


class TestExpandedQuery:
    """Testes da dataclass ExpandedQuery."""

    def test_expanded_query_creation(self):
        """ExpandedQuery deve criar com campos obrigatórios."""
        eq = ExpandedQuery(
            original="Python API tutorial",
            expanded=["Flask REST API", "FastAPI exemplos"],
            method="heuristic",
            timestamp=1234567890.0,
        )
        assert eq.original == "Python API tutorial"
        assert len(eq.expanded) == 2
        assert eq.method == "heuristic"

    def test_expanded_query_to_dict(self):
        """to_dict deve serializar corretamente."""
        eq = ExpandedQuery(
            original="test",
            expanded=["q1", "q2"],
            method="heuristic",
            timestamp=1234567890.0,
        )
        data = eq.to_dict()
        assert data["original"] == "test"
        assert data["expanded"] == ["q1", "q2"]


class TestQueryExpander:
    """Testes do QueryExpander."""

    @pytest.fixture
    def expander(self):
        """Cria expander."""
        return QueryExpander()

    def test_expand_heuristic(self, expander):
        """_expand_heuristic deve gerar variações."""
        queries = expander._expand_heuristic("Python API")
        assert len(queries) > 0
        assert all(isinstance(q, str) for q in queries)
        assert all(len(q) > 5 for q in queries)

    def test_expand_heuristic_short_query(self, expander):
        """_expand_heuristic deve lidar com query curta."""
        queries = expander._expand_heuristic("API")
        assert isinstance(queries, list)
        assert len(queries) > 0

    def test_expand_heuristic_empty(self, expander):
        """_expand_heuristic deve retornar lista vazia para string vazia."""
        assert expander._expand_heuristic("") == []
        assert expander._expand_heuristic("   ") == []

    def test_expand_heuristic_no_duplicate_original(self, expander):
        """_expand_heuristic não deve gerar query igual à original."""
        queries = expander._expand_heuristic("Python API")
        assert all(q.lower() != "python api" for q in queries)

    def test_filter_queries_removes_duplicates(self, expander):
        """_filter_queries deve remover queries idênticas à original."""
        original = "Python API"
        queries = ["Python API", "Flask tutorial", "Python API"]
        filtered = expander._filter_queries(queries, original)
        assert len(filtered) == 1
        assert "Flask tutorial" in filtered

    def test_filter_queries_removes_short(self, expander):
        """_filter_queries deve remover queries muito curtas."""
        queries = ["ab", "xyz", "Flask REST API tutorial"]
        filtered = expander._filter_queries(queries, "test")
        assert len(filtered) == 1
        assert "Flask REST API tutorial" in filtered

    def test_filter_queries_removes_same_words(self, expander):
        """_filter_queries deve remover queries com mesmas palavras."""
        queries = ["API Python", "Flask tutorial"]
        filtered = expander._filter_queries(queries, "Python API")
        assert "API Python" not in filtered

    @pytest.mark.asyncio
    async def test_expand_returns_queries(self, expander):
        """expand() deve retornar queries expandidas."""
        queries = await expander.expand("Python API", max_queries=3)
        assert len(queries) >= 1
        assert all(isinstance(q, str) for q in queries)

    @pytest.mark.asyncio
    async def test_expand_short_query(self, expander):
        """expand() deve funcionar com query curta."""
        queries = await expander.expand("AI", max_queries=3)
        assert len(queries) >= 1

    @pytest.mark.asyncio
    async def test_expand_uses_cache(self, expander):
        """expand() deve usar cache se query já foi expandida."""
        await expander.expand("criar API Python")
        size_before = len(expander._cache)
        await expander.expand("criar API Python")
        assert len(expander._cache) == size_before

    def test_get_stats(self, expander):
        """get_stats() deve retornar estatísticas de uso."""
        expander._cache["test1"] = ["q1", "q2"]
        expander._cache["test2"] = ["q3"]

        stats = expander.get_stats()
        assert stats["cache_size"] == 2
        assert stats["total_expansions"] == 3

    def test_clear_cache(self, expander):
        """clear_cache() deve limpar cache."""
        expander._cache["test"] = ["q1"]
        expander.clear_cache()
        assert len(expander._cache) == 0


class TestQueryExpanderIntegration:
    """Testes de integração com SearchMiddleware."""

    @pytest.mark.asyncio
    async def test_expand_query_wrapper(self):
        """expand_query wrapper deve funcionar."""
        from iaglobal.search import query_expander as qe_mod

        expander = qe_mod.QueryExpander()
        original_get = qe_mod.get_query_expander
        qe_mod.get_query_expander = lambda: expander

        try:
            queries = await qe_mod.expand_query("test", max_queries=2)
            assert len(queries) >= 1
        finally:
            qe_mod.get_query_expander = original_get

    def test_get_expansion_stats_wrapper(self):
        """get_expansion_stats wrapper deve funcionar."""
        from iaglobal.search import query_expander as qe_mod

        expander = qe_mod.QueryExpander()
        expander._cache["x"] = ["a", "b"]
        original_get = qe_mod.get_query_expander
        qe_mod.get_query_expander = lambda: expander

        try:
            stats = qe_mod.get_expansion_stats()
            assert stats["cache_size"] >= 1
        finally:
            qe_mod.get_query_expander = original_get


class TestQueryExpanderE2E:
    """Testes end-to-end do QueryExpander."""

    @pytest.mark.asyncio
    async def test_full_expansion_pipeline(self):
        """Pipeline completo: expand → filter → cache."""
        expander = QueryExpander()

        queries1 = await expander.expand("Python API", max_queries=3)
        assert len(queries1) >= 1
        assert all(len(q) > 5 for q in queries1)

        queries2 = await expander.expand("Python API", max_queries=3)
        assert queries1 == queries2

        stats = expander.get_stats()
        assert stats["cache_size"] >= 1
        assert stats["total_expansions"] >= len(queries1)
