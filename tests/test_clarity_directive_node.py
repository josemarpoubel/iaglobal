# tests/test_clarity_directive_node.py
"""Testes para no_clarity_directive.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from iaglobal.graphs.nodes.no_clarity_directive import ClarityDirectiveNode


@pytest.mark.asyncio
async def test_run_clarity_directive_marcado():
    """Testa se tarefa com IVM baixo é marcada para clareamento."""
    ctx = {"agent_id": "test_agent", "ivm": 0.05}
    node = ClarityDirectiveNode()
    node.clarity.avaliar_tarefa = AsyncMock(return_value=True)
    node.clarity.marcar_para_clareamento = AsyncMock()

    result = await node.run_clarity_directive(ctx)
    assert result["clareance_status"] == "marked"
    node.clarity.marcar_para_clareamento.assert_called_once_with("test_agent")


@pytest.mark.asyncio
async def test_run_clarity_directive_ativo():
    """Testa se tarefa com IVM alto permanece ativa."""
    ctx = {"agent_id": "test_agent", "ivm": 0.5}
    node = ClarityDirectiveNode()
    mock_marcar = AsyncMock()
    node.clarity.marcar_para_clareamento = mock_marcar
    node.clarity.avaliar_tarefa = AsyncMock(return_value=False)

    result = await node.run_clarity_directive(ctx)
    assert result["clareance_status"] == "active"
    assert mock_marcar.call_count == 0