# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Tests for TokenBucket + LocalModelGate — rate limiting e priorização."""

import asyncio
import time

import pytest

from iaglobal.execution.token_bucket import LocalModelGate, TokenBucket


class TestTokenBucket:
    """Valida rate limiting com burst, prioridade e empréstimo."""

    @pytest.mark.asyncio
    async def test_burst_accepts_all_tokens(self):
        tb = TokenBucket(rate=10.0, burst=5, max_debt=0)
        for i in range(5):
            assert await tb.acquire(priority=0.5), f"Burst token {i} should pass"

    @pytest.mark.asyncio
    async def test_empty_bucket_rejects_low_priority(self):
        tb = TokenBucket(rate=0.0, burst=1, max_debt=0)
        await tb.acquire(priority=0.5)  # consome o único token
        assert not await tb.acquire(priority=0.3), "Low priority should be rejected"

    @pytest.mark.asyncio
    async def test_empty_bucket_accepts_high_priority_borrow(self):
        tb = TokenBucket(rate=0.0, burst=1, max_debt=1)
        await tb.acquire(priority=0.5)  # consome o único token
        assert await tb.acquire(priority=0.9), "High priority should borrow"

    @pytest.mark.asyncio
    async def test_high_priority_cannot_exceed_max_debt(self):
        tb = TokenBucket(rate=0.0, burst=1, max_debt=1)
        await tb.acquire(priority=0.5)
        await tb.acquire(priority=0.9)  # empresta 1
        assert not await tb.acquire(priority=0.9), "Should reject — max debt exceeded"

    @pytest.mark.asyncio
    async def test_refill_after_time(self):
        tb = TokenBucket(rate=10.0, burst=3, max_debt=0)
        await tb.acquire(priority=0.5)
        await tb.acquire(priority=0.5)
        await tb.acquire(priority=0.5)
        assert not await tb.acquire(priority=0.5), "Empty bucket"
        await asyncio.sleep(0.15)
        assert await tb.acquire(priority=0.5), "Should have refilled"

    @pytest.mark.asyncio
    async def test_utilization_full(self):
        tb = TokenBucket(rate=1.0, burst=2, max_debt=0)
        assert tb.utilization == 1.0

    @pytest.mark.asyncio
    async def test_utilization_empty(self):
        tb = TokenBucket(rate=0.0, burst=2, max_debt=0)
        await tb.acquire(priority=0.5)
        await tb.acquire(priority=0.5)
        assert tb.utilization == 0.0


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
        assert LocalModelGate.get_priority("") == 0.3

    def test_is_degraded_fresh(self):
        gate = LocalModelGate()
        assert not gate.is_degraded

    def test_is_degraded_after_high_latency(self):
        gate = LocalModelGate()
        gate.report_latency(1200.0)
        assert gate.is_degraded

    def test_report_latency_updates_average(self):
        gate = LocalModelGate()
        gate.report_latency(200.0)
        gate.report_latency(300.0)
        assert gate._avg_latency == 250.0

    def test_report_latency_triggers_circuit_breaker(self):
        gate = LocalModelGate()
        gate.report_latency(1500.0)
        assert gate._circuit_until > time.monotonic()

    def test_report_latency_adjusts_rate_high(self):
        gate = LocalModelGate()
        gate.report_latency(1200.0)
        assert gate.bucket.rate == 1.0

    def test_report_latency_adjusts_rate_low(self):
        gate = LocalModelGate()
        gate.report_latency(200.0)
        assert gate.bucket.rate == 4.0

    def test_report_latency_adjusts_rate_nominal(self):
        gate = LocalModelGate()
        gate.report_latency(500.0)
        assert gate.bucket.rate == 2.0

    @pytest.mark.asyncio
    async def test_try_acquire_critic_allowed(self):
        gate = LocalModelGate()
        allowed = await gate.try_acquire("no_critic")
        assert allowed

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_low_priority(self):
        gate = LocalModelGate()
        gate._avg_latency = 1500.0
        gate._circuit_until = time.monotonic() + 30.0
        allowed = await gate.try_acquire("no_scheduler")
        assert not allowed, "Low priority should be rejected under circuit breaker"
        allowed = await gate.try_acquire("no_critic")
        assert allowed, "Critic should pass even under circuit breaker"

    @pytest.mark.asyncio
    async def test_get_instance_returns_singleton(self):
        g1 = await LocalModelGate.get_instance()
        g2 = await LocalModelGate.get_instance()
        assert g1 is g2
