# tests/test_metabolic_invariants.py
"""Testes para MetabolicInvariants."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import time
from iaglobal.metabolism.metabolic_invariants import MetabolicInvariants


@pytest.fixture
async def mock_invariants():
    """Cria instancia de MetabolicInvariants com dependências mockadas."""
    # Mockar omni_mind globalmente
    from iaglobal.metabolism import metabolic_invariants
    original_omni = metabolic_invariants.omni_mind
    metabolic_invariants.omni_mind = AsyncMock()
    metabolic_invariants.omni_mind.registrar_violação_lei = AsyncMock()
    
    with patch("iaglobal.metabolism.metabolic_invariants.FugueCompartment") as mock_fugue:
        with patch("iaglobal.metabolism.metabolic_invariants.DeltaSleepSync") as mock_delta:
            with patch("iaglobal.metabolism.metabolic_invariants.SubconsciousAPI") as mock_subconscious:
                invariants = MetabolicInvariants()
                invariants.fugue = mock_fugue.return_value
                invariants.delta_sleep = mock_delta.return_value
                invariants.subconscious = mock_subconscious.return_value
                invariants.subconscious.vault_path = MagicMock()
                invariants.last_toxin_check = 0  # Forçar verificação
                
                # Mock de vault_size
                mock_subconscious.return_value.vault_path.glob.return_value = []
                yield invariants, metabolic_invariants
                
                # Restaurar omni_mind
                metabolic_invariants.omni_mind = original_omni


@pytest.mark.asyncio
async def test_check_vault_capacity_ok(mock_invariants):
    """Testa vault com capacidade OK."""
    mock_invariants, _ = mock_invariants
    mock_invariants._mock_vault_size = 500
    with patch("iaglobal.metabolism.metabolic_invariants.time.time", return_value=0):
        result = await mock_invariants._check_vault_capacity()
        assert result["status"] == "OK"
        assert 45 <= result["usage_percent"] <= 55


@pytest.mark.asyncio
async def test_check_vault_capacity_violada(mock_invariants):
    """Testa vault com capacidade violada."""
    mock_invariants, metabolic_invariants = mock_invariants
    mock_invariants._mock_vault_size = 950
    mock_invariants.VAULT_LIMIT_MB = 1000
    result = await mock_invariants._check_vault_capacity()
    assert result["status"] == "VIOLADA"
    assert "alert" in result
    assert metabolic_invariants.omni_mind.registrar_violação_lei.called


@pytest.mark.asyncio
async def test_check_fugue_latency_ok(mock_invariants):
    """Testa latência das tarefas em fuga OK."""
    mock_invariants, _ = mock_invariants
    mock_invariants.fugue._background_tasks = {
        "task_1": {"status": "processing", "timestamp": 0}  # Latência 0s
    }
    with patch("time.time", return_value=0.5):
        result = await mock_invariants._check_fugue_latency()
        assert result["status"] == "OK"


@pytest.mark.asyncio
async def test_check_fugue_latency_aviso(mock_invariants):
    """Testa latência violada."""
    mock_invariants, metabolic_invariants = mock_invariants
    mock_invariants.fugue._background_tasks = {
        "task_1": {"status": "processing", "timestamp": 0}
    }
    with patch("time.time", return_value=1.5):  # Latência >1s
        result = await mock_invariants._check_fugue_latency()
        assert result["status"] == "AVISO"
        assert "slow_tasks" in result
        assert metabolic_invariants.omni_mind.registrar_violação_lei.called


@pytest.mark.asyncio
async def test_check_toxin_removal_ok(mock_invariants):
    """Testa remoção de toxinas OK."""
    mock_invariants, _ = mock_invariants
    mock_invariants.delta_sleep.limpar_toxinas = AsyncMock(return_value={"toxinas_removidas": 3})
    result = await mock_invariants._check_toxin_removal()
    assert result["status"] == "OK"
    assert result["toxinas_removidas"] == 3


@pytest.mark.asyncio
async def test_check_toxin_removal_aviso(mock_invariants):
    """Testa aviso por falta de remoção de toxinas."""
    mock_invariants, metabolic_invariants = mock_invariants
    mock_invariants.delta_sleep.limpar_toxinas = AsyncMock(return_value={"toxinas_removidas": 0})
    result = await mock_invariants._check_toxin_removal()
    assert result["status"] == "AVISO"
    assert result["toxinas_removidas"] == 0
    assert metabolic_invariants.omni_mind.registrar_violação_lei.called


@pytest.mark.asyncio
async def test_check_system_ivm_ok(mock_invariants):
    """Testa IVM saudável."""
    mock_invariants, _ = mock_invariants
    with patch("iaglobal.metabolism.metabolic_invariants.MetabolicInvariants._check_system_ivm",
               return_value={"status": "OK", "avg_ivm": 0.7}):
        result = await mock_invariants._check_system_ivm()
        assert result["status"] == "OK"


@pytest.mark.asyncio
async def test_check_system_ivm_violada(mock_invariants):
    """Testa IVM baixo."""
    mock_invariants, metabolic_invariants = mock_invariants
    with patch("iaglobal.metabolism.metabolic_invariants.MetabolicInvariants._check_system_ivm",
               return_value={"status": "VIOLADA", "avg_ivm": 0.4}):
        result = await mock_invariants._check_system_ivm()
        assert result["status"] == "VIOLADA"