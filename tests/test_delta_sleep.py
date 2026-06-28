# tests/test_delta_sleep.py
"""Testes para DeltaSleepSync."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from iaglobal.subconscious.delta_sleep import DeltaSleepSync
import time


@pytest.mark.asyncio
async def test_eh_toxina():
    """Testa identificação de memórias tóxicas."""
    delta_sleep = DeltaSleepSync()
    
    # Memória recente (não tóxica)
    recent = time.time() - 86400  # 1 dia atrás
    assert delta_sleep._eh_toxina(recent) is False
    
    # Memória antiga (tóxica)
    old = time.time() - (8 * 86400)  # 8 dias atrás
    assert delta_sleep._eh_toxina(old) is True


@pytest.mark.asyncio
async def test_limpar_toxinas():
    """Testa remoção de toxinas do vault."""
    delta_sleep = DeltaSleepSync()
    delta_sleep.subconscious = AsyncMock()
    
    # Simular tarefas com algumas tóxicas
    delta_sleep.subconscious.buscar_tarefas.return_value = [
        {
            "task_id": "task_1",
            "metadados": {"timestamp": time.time() - (8 * 86400)},  # Tóxica
        },
        {
            "task_id": "task_2",
            "metadados": {"timestamp": time.time()},  # Recente
        },
    ]
    
    result = await delta_sleep.limpar_toxinas()
    assert result["toxinas_removidas"] == 1
    delta_sleep.subconscious.remover_tarefa.assert_called_once_with("task_1")


@pytest.mark.asyncio
async def test_compactar_memoria():
    """Testa compactação de memórias de um agente."""
    delta_sleep = DeltaSleepSync()
    delta_sleep.subconscious = AsyncMock()
    
    # Simular tarefas de um agente
    delta_sleep.subconscious.buscar_tarefas.return_value = [
        {"task_type": "critical", "metadados": {"agent_id": "agent_1"}},
        {"task_type": "critical", "metadados": {"agent_id": "agent_1"}},
        {"task_type": "general", "metadados": {"agent_id": "agent_1"}},
    ]
    
    result = await delta_sleep.compactar_memoria("agent_1")
    assert result["total_tarefas"] == 3
    assert "critical" in result["tipos_consolidados"]
    delta_sleep.subconscious.registrar_tarefa.assert_called_once_with(
        origem="delta_sleep",
        tipo="summary",
        metadados={
            "agent_id": "agent_1",
            "total_tarefas": 3,
            "tipos_consolidados": ["critical", "general"],
            "status": "compactado",
        },
    )