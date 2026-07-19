# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes de regressão para gasto único de SAMe no evolution_trigger.

Garante que:
1. spend() é chamado exatamente uma vez por ciclo
2. Reentrância não causa gasto duplo
3. Exceções após spend() não causam retry
4. Concorrência não causa race condition
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from iaglobal.evolution.same_engine import same_pool, COST_CREATE_SKILL, RECHARGE_RATE
from iaglobal.evolution.metacognition.evolution_trigger import EvolutionTrigger


class TestEvolutionTriggerSAMeSpending:
    """Testes para gasto único de SAMe no evolution_trigger."""

    def _make_ctx(self, score: int, graph=None) -> dict:
        """Cria contexto mínimo para o trigger."""
        return {
            "memory": {"evaluator": {"output": {"score": score}}},
            "graph": graph if graph is not None else MagicMock(),
        }

    @pytest.fixture(autouse=True)
    def _reset_samе(self):
        """Reseta SAMe antes de cada teste usando API pública."""
        # Recarrega até atingir saldo conhecido
        while same_pool.balance("evolution_trigger") < 100:
            same_pool.recharge("evolution_trigger")
        # Se estiver acima, zera e recarrega
        if same_pool.balance("evolution_trigger") > 100:
            with same_pool._io_lock:
                same_pool.accounts["evolution_trigger"].balance = 0
            while same_pool.balance("evolution_trigger") < 100:
                same_pool.recharge("evolution_trigger")
        yield

    @pytest.mark.asyncio
    async def test_single_spend_on_trigger(self):
        """Gasto único de SAMe quando trigger dispara evolução."""
        balance_before = same_pool.balance("evolution_trigger")
        
        with patch.object(EvolutionTrigger, "_record_outcome"):
            result = await EvolutionTrigger.trigger(self._make_ctx(score=30))
        
        balance_after = same_pool.balance("evolution_trigger")
        
        assert result["evolution_triggered"] is True
        assert balance_before - balance_after == COST_CREATE_SKILL
        assert result["same_used"] == COST_CREATE_SKILL

    @pytest.mark.asyncio
    async def test_no_spend_when_score_high(self):
        """Sem gasto de SAMe quando score é alto (>= 70)."""
        balance_before = same_pool.balance("evolution_trigger")
        
        result = await EvolutionTrigger.trigger(self._make_ctx(score=85))
        balance_after = same_pool.balance("evolution_trigger")
        
        assert result["evolution_triggered"] is False
        # Deve ter recharge, não gasto
        assert balance_after > balance_before
        assert balance_after - balance_before == RECHARGE_RATE

    @pytest.mark.asyncio
    async def test_spend_occurs_once_even_on_exception(self):
        """Exceção após spend() não causa gasto duplo."""
        balance_before = same_pool.balance("evolution_trigger")
        
        with patch.object(EvolutionTrigger, "_record_outcome"):
            with patch("iaglobal.evolution.metacognition.evolution_trigger.EvolutionEngine") as MockEngine:
                instance = AsyncMock()
                instance.evolve = AsyncMock(side_effect=RuntimeError("Falha simulada"))
                MockEngine.return_value = instance
                result = await EvolutionTrigger.trigger(self._make_ctx(score=30))
        
        balance_after = same_pool.balance("evolution_trigger")
        
        assert result["evolution_triggered"] is False
        assert "Falha na evolução" in result["reason"]
        # spend() ocorreu (gasto pelo attempt), mas não houve segundo gasto
        assert balance_before - balance_after == COST_CREATE_SKILL

    @pytest.mark.asyncio
    async def test_concurrent_triggers_no_overspend(self):
        """Múltiplos triggers concorrentes não causam gasto além do esperado."""
        balance_before = same_pool.balance("evolution_trigger")
        
        async def trigger_once(score: int):
            ctx = self._make_ctx(score=score)
            with patch.object(EvolutionTrigger, "_record_outcome"):
                return await EvolutionTrigger.trigger(ctx)
        
        # Dispara 3 triggers concorrentes
        results = await asyncio.gather(
            trigger_once(30),
            trigger_once(25),
            trigger_once(35),
            return_exceptions=True,
        )
        
        balance_after = same_pool.balance("evolution_trigger")
        actual_spend = balance_before - balance_after
        
        # 3 triggers × 10 = 30 (máximo esperado)
        assert actual_spend <= 3 * COST_CREATE_SKILL
        assert actual_spend > 0

    @pytest.mark.asyncio
    async def test_inhibitor_blocks_when_insufficient_samе(self):
        """Inhibitor bloqueia evolução quando SAMe é insuficiente."""
        # Força saldo baixo
        with same_pool._io_lock:
            same_pool.accounts["evolution_trigger"].balance = 5
        
        result = await EvolutionTrigger.trigger(self._make_ctx(score=30))
        
        assert result["evolution_triggered"] is False
        assert "SAMe insuficiente" in result["reason"]
        # Não gasta o pouco que tem
        assert same_pool.balance("evolution_trigger") == 5

    @pytest.mark.asyncio
    async def test_recharge_on_high_score(self):
        """Recarga de SAMe ocorre quando score é alto."""
        balance_before = same_pool.balance("evolution_trigger")
        
        result = await EvolutionTrigger.trigger(self._make_ctx(score=85))
        balance_after = same_pool.balance("evolution_trigger")
        
        assert result["evolution_triggered"] is False
        assert balance_after - balance_before == RECHARGE_RATE
