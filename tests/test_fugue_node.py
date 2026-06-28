# tests/test_fugue_node.py
"""Testes para no_fugue_compartment.py."""

import pytest
from unittest.mock import AsyncMock
from iaglobal.graphs.nodes.no_fugue_compartment import FugueCompartmentNode


@pytest.mark.asyncio
async def test_run_fugue_compartment():
    """Testa encaminhamento de tarefas para o FugueCompartment."""
    ctx = {
        "agent_id": "test_agent",
        "task_data": {"key": "value"},
        "task_type": "critical",
    }
    node = FugueCompartmentNode()
    node.fugue.processar_em_segundo_plano = AsyncMock(return_value="fugue_123")

    result = await node.run_fugue_compartment(ctx)
    assert result["fugue_id"] == "fugue_123"
    assert result["fugue_status"] == "processing"


@pytest.mark.asyncio
async def test_run_fugue_compartment_sem_tarefa():
    """Testa comportamento quando não há tarefa para processar."""
    ctx = {"agent_id": "test_agent"}
    node = FugueCompartmentNode()
    node.fugue.processar_em_segundo_plano = AsyncMock()

    result = await node.run_fugue_compartment(ctx)
    assert "fugue_id" not in result
    node.fugue.processar_em_segundo_plano.assert_not_called()