# tests/test_fugue_compartment.py
"""Testes para FugueCompartment e no_fugue_compartment."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from iaglobal.subconscious.fugue_compartment import FugueCompartment


@pytest.mark.asyncio
async def test_processar_em_segundo_plano():
    """Testa se tarefas são registradas no vault e processadas."""
    fugue = FugueCompartment()
    fugue.subconscious = AsyncMock()
    fugue._simular_processamento = AsyncMock()

    agent_id = "test_agent"
    task_data = {"key": "value"}
    task_type = "critical"

    fugue_id = await fugue.processar_em_segundo_plano(agent_id, task_data, task_type)
    assert fugue_id.startswith("fugue_test_agent_critical")
    fugue.subconscious.registrar_tarefa.assert_called_once()


@pytest.mark.asyncio
async def test_buscar_tarefas_por_tipo():
    """Testa busca de tarefas no vault."""
    fugue = FugueCompartment()
    fugue.subconscious = AsyncMock()
    fugue.subconscious.buscar_tarefas.return_value = [
        {"task_type": "critical", "agent_id": "test_agent"}
    ]

    tasks = await fugue.buscar_tarefas_por_tipo("critical")
    assert len(tasks) == 1
    assert tasks[0]["task_type"] == "critical"


@pytest.mark.asyncio
async def test_get_status():
    """Testa consulta de status de tarefas."""
    fugue = FugueCompartment()
    # Desativar processamento automático para teste
    fugue._simular_processamento = AsyncMock()
    
    agent_id = "test_agent"
    task_data = {"key": "value"}
    task_type = "critical"

    fugue_id = await fugue.processar_em_segundo_plano(agent_id, task_data, task_type)
    status = await fugue.get_status(fugue_id)
    assert status == "processing"