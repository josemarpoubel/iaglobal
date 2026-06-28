# tests/test_clarity_directive.py
"""Testes para ClarityDirective e no_clarity_directive."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from iaglobal.metabolism.clarity_directive import ClarityDirective


@pytest.mark.asyncio
async def test_avaliar_tarefa_abaixo_threshold():
    """Testa se tarefas com IVM abaixo do threshold são marcadas para clareamento."""
    clarity = ClarityDirective()
    agent_id = "test_agent"

    # IVM abaixo do threshold (0.1)
    result = await clarity.avaliar_tarefa(agent_id, 0.05)
    assert result is True


@pytest.mark.asyncio
async def test_avaliar_tarefa_acima_threshold():
    """Testa se tarefas com IVM acima do threshold não são marcadas."""
    clarity = ClarityDirective()
    agent_id = "test_agent"

    result = await clarity.avaliar_tarefa(agent_id, 0.5)
    assert result is False


@pytest.mark.asyncio
async def test_marcar_para_clareamento():
    """Testa se a marcação para clareamento é registrada."""
    clarity = ClarityDirective()
    clarity.epigenetic_registry = AsyncMock()
    clarity.omni_mind = AsyncMock()
    agent_id = "test_agent"

    await clarity.marcar_para_clareamento(agent_id)
    clarity.epigenetic_registry.salvar_marca_epigenetica.assert_called_once_with(
        chave=f"{agent_id}_clareance_pending",
        valor=True,
        metadata={"motivo": "IVM baixo", "acao": "apoptose"},
    )
    clarity.omni_mind.emitir_gatilho_vacio.assert_called_once_with(agent_id)