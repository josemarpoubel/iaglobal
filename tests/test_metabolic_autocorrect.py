# tests/test_metabolic_autocorrect.py
"""Testes para MetabolicAutocorrect."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from iaglobal.metabolism.metabolic_autocorrect import MetabolicAutocorrect


@pytest.fixture
async def mock_autocorrect():
    """Cria instancia mockada de MetabolicAutocorrect."""
    # Mockar omni_mind globalmente
    from iaglobal.metabolism import metabolic_autocorrect
    original_omni = metabolic_autocorrect.omni_mind
    metabolic_autocorrect.omni_mind = AsyncMock()
    
    with patch("iaglobal.metabolism.metabolic_autocorrect.MetabolicInvariants") as mock_invariants:
        with patch("iaglobal.metabolism.metabolic_autocorrect.DeltaSleepSync") as mock_delta:
            with patch("iaglobal.metabolism.metabolic_autocorrect.BanditPolicy") as mock_bandit:
                autocorrect = MetabolicAutocorrect()
                autocorrect.invariants = mock_invariants.return_value
                autocorrect.delta_sleep = mock_delta.return_value
                autocorrect.bandit = mock_bandit.return_value
                
                mock_invariants.return_value.check_all = AsyncMock(return_value={
                    "vault": {"status": "VIOLADA", "alert": "Vault cheio"},
                    "latency": {"status": "OK"},
                    "toxins": {"status": "OK"},
                    "ivm": {"status": "OK"},
                })
                
                yield autocorrect, mock_invariants, mock_delta, mock_bandit, metabolic_autocorrect
                
                # Restaurar omni_mind
                metabolic_autocorrect.omni_mind = original_omni


@pytest.mark.asyncio
async def test_verificar_e_corrigir_vault(mock_autocorrect):
    """Testa correção automática para vault cheio."""
    autocorrect, _, mock_delta, _, metabolic_autocorrect = mock_autocorrect
    
    # Simular vault violado
    autocorrect.invariants.check_all.return_value = {
        "vault": {"status": "VIOLADA"},
        "latency": {"status": "OK"},
        "toxins": {"status": "OK"},
        "ivm": {"status": "OK"},
    }
    
    mock_delta.return_value.limpar_toxinas = AsyncMock(return_value={"toxinas_removidas": 5})
    
    result = await autocorrect.verificar_e_corrigir()
    assert result["correcoes"]["vault"]["acao"] == "delta_sleep_acionado"
    mock_delta.return_value.limpar_toxinas.assert_called_once()
    assert metabolic_autocorrect.omni_mind.registrar_violação_lei.called


@pytest.mark.asyncio
async def test_verificar_e_corrigir_fugue_latency(mock_autocorrect):
    """Testa correção para latência do FugueCompartment."""
    autocorrect, _, mock_delta, _, metabolic_autocorrect = mock_autocorrect
    
    # Simular latência violada
    autocorrect.invariants.check_all.return_value = {
        "vault": {"status": "OK"},
        "latency": {"status": "AVISO"},
        "toxins": {"status": "OK"},
        "ivm": {"status": "OK"},
    }
    
    result = await autocorrect.verificar_e_corrigir()
    assert result["correcoes"]["latency"]["acao"] == "fugue_compactado"
    assert metabolic_autocorrect.omni_mind.registrar_violação_lei.called


@pytest.mark.asyncio
async def test_verificar_e_corrigir_toxinas(mock_autocorrect):
    """Testa correção para toxinas estagnadas."""
    autocorrect, _, mock_delta, _, metabolic_autocorrect = mock_autocorrect
    
    # Simular toxinas estagnadas
    autocorrect.invariants.check_all.return_value = {
        "vault": {"status": "OK"},
        "latency": {"status": "OK"},
        "toxins": {"status": "AVISO"},
        "ivm": {"status": "OK"},
    }
    
    mock_delta.return_value.limpar_toxinas = AsyncMock(return_value={"toxinas_removidas": 3})
    
    result = await autocorrect.verificar_e_corrigir()
    assert result["correcoes"]["toxins"]["acao"] == "limpeza_forcada"
    mock_delta.return_value.limpar_toxinas.assert_called_once()
    assert metabolic_autocorrect.omni_mind.registrar_violação_lei.called


@pytest.mark.asyncio
async def test_verificar_e_corrigir_ivm(mock_autocorrect):
    """Testa correção para IVM baixo."""
    autocorrect, _, _, mock_bandit, metabolic_autocorrect = mock_autocorrect
    
    # Simular IVM violado
    autocorrect.invariants.check_all.return_value = {
        "vault": {"status": "OK"},
        "latency": {"status": "OK"},
        "toxins": {"status": "OK"},
        "ivm": {"status": "VIOLADA"},
    }
    
    mock_bandit.return_value.ajustar_por_ivm = AsyncMock()
    
    result = await autocorrect.verificar_e_corrigir()
    assert result["correcoes"]["ivm"]["acao"] == "bandit_ajustado"
    mock_bandit.return_value.ajustar_por_ivm.assert_called_once()
    assert metabolic_autocorrect.omni_mind.registrar_violação_lei.called


@pytest.mark.asyncio
async def test_sem_correcoes(mock_autocorrect):
    """Testa quando nenhuma correção é necessária."""
    autocorrect, _, _, _, _ = mock_autocorrect
    
    # Todas invariantes OK
    autocorrect.invariants.check_all.return_value = {
        "vault": {"status": "OK"},
        "latency": {"status": "OK"},
        "toxins": {"status": "OK"},
        "ivm": {"status": "OK"},
    }
    
    result = await autocorrect.verificar_e_corrigir()
    assert result["correcoes"] == {}