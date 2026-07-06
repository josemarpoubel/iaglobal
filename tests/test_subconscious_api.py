# tests/test_subconscious_api.py
"""Testes para SubconsciousAPI com integração real ao vault."""

import pytest
from unittest.mock import patch, AsyncMock
from iaglobal.subconscious.subconscious_api import SubconsciousAPI

@pytest.fixture
async def mock_vault():
    """Mock para o vault durante os testes."""
    with patch("iaglobal.subconscious.subconscious_api.ObsidianSubconscious") as mock:
        mock_vault = mock.return_value
        mock_vault.escrever_nota = AsyncMock(return_value="test_id_123")
        mock_vault.escrever_longo_prazo = AsyncMock(return_value="test_id_123")
        mock_vault.buscar_notas = AsyncMock(return_value=[{
            "id": "test_id_123",
            "origem": "busca_test",
            "tipo": "general",
            "metadados": {"agent_id": "test_agent", "status": "processing"},
        }])
        mock_vault.ler_nota = AsyncMock(return_value={
            "metadados": {"agent_id": "test_agent"}
        })
        mock_vault.remover_nota = AsyncMock(return_value=True)
        yield mock_vault


@pytest.mark.asyncio
async def test_registrar_tarefa(mock_vault):
    """Testa se tarefas são registradas via SubconsciousAPI."""
    api = SubconsciousAPI()
    task_id = await api.registrar_tarefa(
        origem="test",
        tipo="critical",
        metadados={
            "agent_id": "test_agent",
            "fugue_id": "test_fugue_id",
        },
    )
    assert task_id == "test_fugue_id"
    api.vault.escrever_longo_prazo.assert_called_once()


@pytest.mark.asyncio
async def test_buscar_tarefas(mock_vault):
    """Testa busca de tarefas via SubconsciousAPI."""
    api = SubconsciousAPI()
    tarefas = await api.buscar_tarefas(
        origem="busca_test",
        filtro={"status": "processing"},
    )
    assert len(tarefas) == 1
    assert tarefas[0]["metadados"]["agent_id"] == "test_agent"


@pytest.mark.asyncio
async def test_remover_tarefa(mock_vault):
    """Testa remoção de tarefas via SubconsciousAPI."""
    api = SubconsciousAPI()
    success = await api.remover_tarefa("test_id_123")
    assert success is True
    api.vault.remover_nota.assert_called_once_with("test_id_123")