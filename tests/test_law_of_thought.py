# tests/test_law_of_thought.py
"""Testes para o nó no_law_of_thought_enforcer."""
import pytest
from iaglobal.graphs.nodes.no_law_of_thought_enforcer import run_law_of_thought_enforcer
from iaglobal.exceptions import LawViolation


@pytest.mark.asyncio
async def test_law_of_thought_enforcer_with_reasoning():
    """Testa se o nó permite passagem quando 'reasoning' está presente."""
    ctx = {"reasoning": "Análise completa da tarefa"}
    result = await run_law_of_thought_enforcer(ctx)
    assert result == ctx


@pytest.mark.asyncio
async def test_law_of_thought_enforcer_without_reasoning():
    """Testa se o nó levanta exceção quando 'reasoning' não está presente."""
    ctx = {}  # Sem 'reasoning'
    with pytest.raises(LawViolation) as exc_info:
        await run_law_of_thought_enforcer(ctx)
    assert "Lei do Pensamento: campo 'reasoning' obrigatório" in str(exc_info.value)