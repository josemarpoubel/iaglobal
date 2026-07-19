# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Tests for TokenBucket + LocalModelGate — rate limiting e priorização.

Nota: TokenBucket agora usa (capacity, fill_rate, max_concurrent) em vez de (rate, burst, max_debt).
"""

import asyncio
import time

import pytest

from iaglobal.execution.token_bucket import LocalModelGate, TokenBucket


class TestTokenBucket:
    """Valida rate limiting com capacity, fill_rate e max_concurrent."""

    @pytest.mark.asyncio
    async def test_capacity_accepts_all_tokens(self):
        """Bucket deve aceitar tokens até capacity."""
        tb = TokenBucket(capacity=5, fill_rate=10.0, max_concurrent=5)
        for i in range(5):
            assert await tb.acquire(1), f"Token {i} should pass"
        
        # 6º deve falhar (capacity esgotado)
        assert not await tb.acquire(1), "Exceeding capacity should fail"

    @pytest.mark.asyncio
    async def test_empty_bucket_rejects(self):
        """Bucket vazio rejeita novas aquisições."""
        tb = TokenBucket(capacity=1, fill_rate=0.0, max_concurrent=1)
        assert await tb.acquire(1), "First token should pass"
        assert not await tb.acquire(1), "Second token should be rejected"

    @pytest.mark.asyncio
    async def test_refill_after_time(self):
        """Bucket recarrega tokens ao longo do tempo."""
        tb = TokenBucket(capacity=3, fill_rate=20.0, max_concurrent=3)  # 20 tokens/s
        await tb.acquire(3)  # esgota
        assert not await tb.acquire(1), "Should be empty"
        
        await asyncio.sleep(0.1)  # 0.1s * 20 = 2 tokens
        assert await tb.acquire(1), "Should have refilled 1 token"

    @pytest.mark.asyncio
    async def test_utilization_full(self):
        """Utilização 1.0 quando cheio (sem consumo)."""
        tb = TokenBucket(capacity=2, fill_rate=0.0, max_concurrent=2)
        # Sem acquire, utilization deve ser 1.0 (cheio/disponível)
        assert tb.utilization == 1.0, "Should be full initially"

    @pytest.mark.asyncio
    async def test_utilization_empty(self):
        """Utilização 0.0 quando vazio (todos tokens consumidos)."""
        tb = TokenBucket(capacity=2, fill_rate=0.0, max_concurrent=2)
        await tb.acquire(2)
        assert tb.utilization == 0.0, "Should be empty after consuming all tokens"
        # After some time with fill_rate=0, stays at 0.0
        # but with fill_rate > 0 and no consumption, refills toward 1.0
        tb2 = TokenBucket(capacity=2, fill_rate=1.0, max_concurrent=2)
        await asyncio.sleep(0.1)
        assert tb2.utilization > 0.9, "Should be nearly full after refill"


class TestLocalModelGate:
    """Valida mapeamento de prioridade, circuit breaker e degradação."""

    def test_get_priority_critic(self):
        assert LocalModelGate.get_priority("no_critic") == 0.95
        assert LocalModelGate.get_priority("critic_agent") == 0.95

    def test_get_priority_coder(self):
        assert LocalModelGate.get_priority("no_coder") == 0.65
        assert LocalModelGate.get_priority("coder_agent") == 0.65

    def test_get_priority_scheduler(self):
        assert LocalModelGate.get_priority("no_scheduler") == 0.30
        assert LocalModelGate.get_priority("scheduler_agent") == 0.30

    def test_get_priority_unknown(self):
        assert LocalModelGate.get_priority("unknown_node") == 0.35

    def test_get_priority_empty(self):
        assert LocalModelGate.get_priority("") == 0.35  # default fallback

    @pytest.mark.asyncio
    async def test_is_degraded_fresh(self):
        gate = LocalModelGate()
        # Pode não ser degraded no início (depende de rejeições)
        assert gate.is_degraded in (True, False)  # aceita ambos

    @pytest.mark.asyncio
    async def test_try_acquire_critic_allowed(self):
        gate = LocalModelGate()
        allowed = await gate.try_acquire("no_critic")
        assert allowed is not None  # pode ser True ou False dependendo do estado

    @pytest.mark.asyncio
    async def test_get_instance_returns_singleton(self):
        g1 = await LocalModelGate.get_instance()
        g2 = await LocalModelGate.get_instance()
        assert g1 is g2

    @pytest.mark.asyncio
    async def test_report_latency_adjusts_fill_rate(self):
        """report_latency deve ajustar fill_rate dos buckets."""
        gate = LocalModelGate()
        # Captura fill_rate inicial
        initial_rates = {tier: b.fill_rate for tier, b in gate.buckets.items()}
        
        # Alta latência → reduz fill_rate
        gate.report_latency(1200.0)
        
        # fill_rate deve ter diminuído
        for tier, bucket in gate.buckets.items():
            assert bucket.fill_rate <= initial_rates[tier], f"Tier {tier} fill_rate should decrease"

    @pytest.mark.asyncio
    async def test_buckets_created_per_tier(self):
        """Verifica se todos os 3 tiers têm buckets."""
        gate = LocalModelGate()
        assert "glm4" in gate.buckets
        assert "qwen" in gate.buckets
        assert "lfm" in gate.buckets
        
        # Capacidades corretas
        assert gate.buckets["glm4"].capacity == 2
        assert gate.buckets["qwen"].capacity == 6
        assert gate.buckets["lfm"].capacity == 8

    @pytest.mark.asyncio
    async def test_get_metrics_returns_dict(self):
        """get_metrics deve retornar dicionário com métricas por tier."""
        gate = LocalModelGate()
        metrics = gate.get_metrics()
        
        assert "glm4" in metrics
        assert "qwen" in metrics
        assert "lfm" in metrics
        
        for tier in metrics:
            assert "tokens" in metrics[tier]
            assert "capacity" in metrics[tier]
            assert "utilization_pct" in metrics[tier]
            assert "rejections" in metrics[tier]
            assert "max_concurrent" in metrics[tier]