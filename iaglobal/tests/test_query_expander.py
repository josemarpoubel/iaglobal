# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do QueryExpander — Fase 2 do RAG Autônomo.

Cobertura:
  - expand() gera 2-3 queries relacionadas
  - _parse_json_response extrai queries do JSON
  - _filter_queries remove duplicatas e inválidas
  - Cache funciona corretamente
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from iaglobal.search.query_expander import (
    QueryExpander,
    ExpandedQuery,
    get_query_expander,
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
            model_used="ollama/qwen2.5:0.5b",
            timestamp=1234567890.0,
        )
        assert eq.original == "Python API tutorial"
        assert len(eq.expanded) == 2
        assert eq.model_used == "ollama/qwen2.5:0.5b"

    def test_expanded_query_to_dict(self):
        """to_dict deve serializar corretamente."""
        eq = ExpandedQuery(
            original="test",
            expanded=["q1", "q2"],
            model_used="test_model",
            timestamp=1234567890.0,
        )
        data = eq.to_dict()
        assert data["original"] == "test"
        assert data["expanded"] == ["q1", "q2"]


class TestQueryExpander:
    """Testes do QueryExpander."""

    @pytest.fixture
    def expander(self):
        """Cria expander com mock do LLM."""
        return QueryExpander(model="ollama/qwen2.5:0.5b")

    def test_parse_json_response_valid(self, expander):
        """_parse_json_response deve extrair queries de JSON válido."""
        json_text = '{"queries": ["query1", "query2", "query3"]}'
        queries = expander._parse_json_response(json_text)
        assert len(queries) == 3
        assert "query1" in queries

    def test_parse_json_response_markdown(self, expander):
        """_parse_json_response deve extrair de bloco markdown."""
        markdown_text = '''
        Aqui está o JSON:
        ```json
        {"queries": ["flask tutorial", "fastapi exemplos"]}
        ```
        '''
        queries = expander._parse_json_response(markdown_text)
        assert len(queries) == 2

    def test_parse_json_response_fallback(self, expander):
        """_parse_json_response deve fallback para strings entre aspas."""
        text = 'Algumas "queries" aqui: "Python API", "REST tutorial"'
        queries = expander._parse_json_response(text)
        assert len(queries) >= 2

    def test_parse_json_response_empty(self, expander):
        """_parse_json_response deve retornar lista vazia se sem JSON."""
        queries = expander._parse_json_response("")
        assert len(queries) == 0

    def test_filter_queries_removes_duplicates(self, expander):
        """_filter_queries deve remover queries idênticas à original."""
        original = "Python API"
        queries = ["Python API", "Flask tutorial", "Python API"]  # Duplicata
        filtered = expander._filter_queries(queries, original)
        assert len(filtered) == 1
        assert "Flask tutorial" in filtered
        assert "Python API" not in filtered  # Removida por ser idêntica

    def test_filter_queries_removes_short(self, expander):
        """_filter_queries deve remover queries muito curtas."""
        queries = ["ab", "xyz", "Flask REST API tutorial"]
        filtered = expander._filter_queries(queries, "test")
        assert len(filtered) == 1
        assert "Flask REST API tutorial" in filtered

    def test_filter_queries_removes_meta_queries(self, expander):
        """_filter_queries deve remover meta-queries."""
        queries = [
            "como buscar no Google",  # Contém "buscar"
            "query para API",  # Contém "query"
            "Flask tutorial",  # Válida
        ]
        filtered = expander._filter_queries(queries, "test")
        assert len(filtered) == 1
        assert "Flask tutorial" in filtered

    @pytest.mark.asyncio
    async def test_expand_with_mock_llm(self, expander):
        """expand() deve chamar LLM e retornar queries expandidas."""
        mock_response = '''
        {"queries": ["Flask REST API passo a passo", "FastAPI documentação", "exemplo código API Python"]}
        '''

        with patch.object(expander, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            queries = await expander.expand("Python API", max_queries=3)

            assert len(queries) == 3
            assert "Flask REST API passo a passo" in queries
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_expand_with_llm_failure(self, expander):
        """expand() deve retornar query original se LLM falhar."""
        with patch.object(expander, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ""  # LLM falhou

            queries = await expander.expand("criar API Python", max_queries=3)

            assert queries == ["criar API Python"]  # Fallback

    @pytest.mark.asyncio
    async def test_expand_uses_cache(self, expander):
        """expand() deve usar cache se query já foi expandida."""
        # Primeira expansão
        mock_response = '{"queries": ["tutorial Flask passo a passo", "exemplos FastAPI GitHub"]}'
        
        with patch.object(expander, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            queries1 = await expander.expand("criar API Python")
            assert mock_call.call_count == 1
            assert len(queries1) == 2

        # Segunda expansão (deve usar cache)
        with patch.object(expander, "_call_llm", new_callable=AsyncMock) as mock_call:
            queries2 = await expander.expand("criar API Python")
            assert mock_call.call_count == 0  # Não chamou LLM
            assert queries1 == queries2  # Mesmo resultado do cache

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
        with patch("iaglobal.search.query_expander.get_query_expander") as mock_get:
            mock_expander = mock_get.return_value
            mock_expander.expand = AsyncMock(return_value=["q1", "q2"])

            queries = await expand_query("test", max_queries=2)

            assert len(queries) == 2
            mock_expander.expand.assert_called_once()

    def test_get_expansion_stats_wrapper(self):
        """get_expansion_stats wrapper deve funcionar."""
        with patch("iaglobal.search.query_expander.get_query_expander") as mock_get:
            mock_expander = mock_get.return_value
            mock_expander.get_stats.return_value = {"cache_size": 5}

            stats = get_expansion_stats()

            assert stats["cache_size"] == 5


class TestQueryExpanderE2E:
    """Testes end-to-end do QueryExpander."""

    @pytest.mark.asyncio
    async def test_full_expansion_pipeline(self):
        """Pipeline completo: expand → filter → cache."""
        expander = QueryExpander()

        # Mock LLM response
        mock_response = '''
        {"queries": [
            "Flask REST API tutorial 2024",
            "FastAPI vs Flask comparação",
            "exemplo código Python API GitHub"
        ]}
        '''

        with patch.object(expander, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            # Primeira expansão
            queries1 = await expander.expand("Python API", max_queries=3)
            assert len(queries1) == 3
            assert all(len(q) > 5 for q in queries1)  # Queries não vazias

            # Segunda expansão (cache)
            queries2 = await expander.expand("Python API", max_queries=3)
            assert queries1 == queries2  # Mesmo resultado

            # Stats
            stats = expander.get_stats()
            assert stats["cache_size"] == 1
            assert stats["total_expansions"] == 3