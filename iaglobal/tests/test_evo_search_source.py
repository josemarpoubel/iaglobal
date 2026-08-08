# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
test_evo_search_source.py — Regressão de atribuição de origem da busca no EvoAgent.

Garante que `EvoAgent.search_web()` NUNCA rotule contexto do SearchMiddleware
como 'searxng' — o SearchMiddleware usa DuckDuckGo + RAG + Obsidian, não o
meta-buscador local. O rótulo 'searxng' fica reservado ao provider real
(`_search_sources.searxng_search`).

Contexto (ADR-0006): antes da correção, todo contexto injetado era rotulado
como source="searxng" (o marcador '[CONTEXTO WEB]' que o código procurava
nunca existia na saída do SearchMiddleware). Isso contaminava métricas de
qualidade e o prompt de metilação.

Execute:
    python -m pytest iaglobal/tests/test_evo_search_source.py -q
"""

from unittest import mock

import pytest

from iaglobal.evolution.evo_agent import EvoAgent
from iaglobal.search.search_middleware import SearchMiddleware


def _bare_agent() -> EvoAgent:
    """Instância mínima sem genesis/apoptose — search_web só usa esses 3 attrs."""
    agent = object.__new__(EvoAgent)
    agent.name = "evo-search-test"
    agent.generation = 0
    agent.lineage_marker = "lineage-test"
    return agent


def _mock_enrich(return_value: str):
    return mock.patch.object(
        SearchMiddleware,
        "enrich",
        new=mock.AsyncMock(return_value=return_value),
    )


WEB_CONTEXT = (
    "[CONTEXTO]\n## Web\n- resultado web\n## Referências\n"
    "- http://exemplo.com\n[INSTRUÇÃO]\nresponda"
)
OBSIDIAN_CONTEXT = "[CONTEXTO]\n## Obsidian (cache persistente)\n- snippet (score=0.9)\n[INSTRUÇÃO]\nresponda"


@pytest.mark.asyncio
async def test_web_context_is_attributed_to_ddg():
    agent = _bare_agent()
    with _mock_enrich(WEB_CONTEXT):
        result = await agent.search_web("crie API Flask com JWT")

    assert result["source"] == "ddg"
    assert result["evolution_impact"] is True
    assert result["results_count"] == 2


@pytest.mark.asyncio
async def test_obsidian_hit_is_attributed_to_memory():
    agent = _bare_agent()
    with _mock_enrich(OBSIDIAN_CONTEXT):
        result = await agent.search_web("crie API Flask com JWT")

    assert result["source"] == "memory"
    assert result["evolution_impact"] is True
    assert result["results_count"] == 1


@pytest.mark.asyncio
async def test_no_context_is_attributed_to_none():
    agent = _bare_agent()
    with _mock_enrich("prompt sem contexto injetado"):
        result = await agent.search_web("crie API Flask com JWT")

    assert result["source"] == "none"
    assert result["evolution_impact"] is False
    assert result["results_count"] == 0


@pytest.mark.asyncio
async def test_search_web_never_claims_searxng():
    """Corpus de saídas possíveis do SearchMiddleware — nenhuma pode virar 'searxng'."""
    agent = _bare_agent()
    corpus = [
        "prompt puro",
        OBSIDIAN_CONTEXT,
        "[CONTEXTO]\n## Memoria Local\n- fato rag\n[INSTRUÇÃO]\nok",
        "[CONTEXTO]\n## Web\n- item\n[INSTRUÇÃO]\nok",
        WEB_CONTEXT,
        "[CONTEXTO]\n## Fatos\n- fato\n## Código Relevante\n```python\nx = 1\n```\n[INSTRUÇÃO]\nok",
        "[CONTEXTO]\nsíntese agregada de snippets sem marcador\n[INSTRUÇÃO]\nok",
    ]
    for sample in corpus:
        with _mock_enrich(sample):
            result = await agent.search_web("query genérica")
        assert result["source"] != "searxng", (
            f"origem indevida 'searxng' para saída: {sample[:40]!r}"
        )


@pytest.mark.asyncio
async def test_evolution_impact_requires_context():
    """Sem contexto injetado → evolution_impact=False (não gera skill)."""
    agent = _bare_agent()
    for sample in ("", "prompt", "outra coisa sem marcador"):
        with _mock_enrich(sample):
            result = await agent.search_web("query")
        assert result["evolution_impact"] is False
        assert result["source"] == "none"
