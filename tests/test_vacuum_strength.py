# tests/test_vacuum_strength.py
"""Testes para o nó no_vacuum_strength."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from iaglobal.graphs.nodes.no_vacuum_strength import VacuumStrength


@pytest.mark.asyncio
async def test_vacuum_strength_applied():
    """Testa se o nó aplica a Lei do Vácuo quando 'vacuum_required' é True."""
    ctx = {"vacuum_required": True, "context_effects": "dummy"}
    mock_omni_mind = MagicMock()
    mock_omni_mind.emitir_gatilho_vacio = AsyncMock()

    # Instancia a classe real
    vacuum = VacuumStrength()
    mock_omni_mind.emitir_gatilho_vacio = AsyncMock()
    vacuum.omni_mind = mock_omni_mind
    vacuum._limpar_contexto = MagicMock(return_value={"vacuum_required": True})
    vacuum._injetar_nutrientes = MagicMock(return_value={"nutrients_injected": True})

    result = await vacuum.run_vacuum_strength(ctx)
    assert result == {"nutrients_injected": True}
    mock_omni_mind.emitir_gatilho_vacio.assert_called_once_with("tarefa_vaciada")


@pytest.mark.asyncio
async def test_vacuum_strength_not_applied():
    """Testa se o nó não altera o contexto quando 'vacuum_required' é False."""
    ctx = {"vacuum_required": False}

    # Instancia a classe real
    vacuum = VacuumStrength()
    vacuum.omni_mind = MagicMock()
    vacuum.omni_mind.emitir_gatilho_vacio = AsyncMock()
    vacuum._limpar_contexto = MagicMock()
    vacuum._injetar_nutrientes = MagicMock()

    result = await vacuum.run_vacuum_strength(ctx)
    assert result == ctx
    vacuum._limpar_contexto.assert_not_called()
    vacuum._injetar_nutrientes.assert_not_called()