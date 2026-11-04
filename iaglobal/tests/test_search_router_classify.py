# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
test_search_router_classify.py — Regressão de classificação do SearchRouter.

Bug corrigido (2026-07-31): o `classify_task` matcheava keywords por substring
pura (`kw in task_lower`). Isso produzia falsos positivos em palavras comuns:

    - "pais"   → dentro de "principais"    (query de PageRank caía em economia)
    - "sol"    → dentro de "solução"
    - "autor"  → dentro de "autoridade"
    - "capital"→ dentro de "capitalismo"

Consequência: queries de conhecimento geral ("cite as principais fontes") NÃO
caíam no fallback SearXNG do `_general_knowledge_search`. O matching agora usa
fronteira de palavra (`\\b...\\b`) e os plurais "paises"/"países" foram
adicionados à categoria economia para não regredir.

Estes testes são puros de classificação (sem rede, sem arquivos).
"""

from unittest import mock

import pytest

from iaglobal.graphs.nodes import _search_router
from iaglobal.graphs.nodes import _search_sources


class TestClassifyTaskWordBoundaries:
    def test_principais_nao_matcheia_pais(self):
        """'pais' não pode ser substring de 'principais' (falso positivo)."""
        sources = _search_router.classify_task(
            "Explique o algoritmo PageRank e cite as principais fontes."
        )
        assert sources == []

    @pytest.mark.asyncio
    async def test_general_knowledge_cai_no_searxng(self):
        """Query geral (sem categoria especializada) usa o fallback SearXNG."""
        with mock.patch.object(
            _search_sources, "searxng_search", return_value="resultado searxng " * 10
        ) as m_searxng:
            out = await _search_router.run_search_router(
                "Explique o algoritmo PageRank e cite as principais fontes."
            )
        m_searxng.assert_called_once()
        assert "=== SEARXNG ===" in out

    @pytest.mark.parametrize(
        "query",
        [
            "qual a população dos países da Europa?",
            "qual o PIB dos paises da America Latina?",
        ],
    )
    def test_plural_paises_continua_em_economia(self, query):
        """Plural 'países'/'paises' mantém a rota de economia (sem regressão)."""
        sources = _search_router.classify_task(query)
        assert sources
        assert sources[0][0].startswith("economia_")

    @pytest.mark.parametrize(
        "query",
        [
            "a autoridade competente emitiu parecer",
            "preciso de uma solução para o bug",
            "o capitalismo e suas falhas",
        ],
    )
    def test_palavras_com_prefixo_comum_nao_classificam(self, query):
        """'autor', 'sol' e 'capital' não matcheiam 'autoridade', 'solução', 'capitalismo'."""
        assert _search_router.classify_task(query) == []

    @pytest.mark.parametrize(
        "query,expected_prefix",
        [
            ("clima temperatura cidade", "clima_"),
            ("última notícia de tecnologia", "noticias_"),
            ("qual a capital do Brasil e o país mais populoso", "economia_"),
        ],
    )
    def test_categorias_especializadas_mantidas(self, query, expected_prefix):
        """Queries com palavras reais da categoria seguem roteando normal."""
        sources = _search_router.classify_task(query)
        assert sources
        assert sources[0][0].startswith(expected_prefix)
