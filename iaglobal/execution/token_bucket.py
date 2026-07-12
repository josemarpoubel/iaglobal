# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
TokenBucket — Rate limiter adaptativo com priorização por IVM.

Protege o modelo local (qwen2.5:0.5b) contra thrashing de CPU em
hardware limitado (4 núcleos, sem GPU). Substitui o Semaphore fixo
por um sistema de cadência dinâmica:

  - Burst quando ocioso (até N tokens acumulados)
  - Cadência estrita sob carga (rate controlado por latência)
  - Priorização: agentes de baixo IVM são rejeitados sob pressão
  - Circuit breaker: latência > 1000ms → só agentes críticos passam
"""

import asyncio
import time
from typing import ClassVar

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.token_bucket")


class TokenBucket:
    """Rate limiter token bucket com priorização e empréstimo controlado.

    Parâmetros:
        rate: tokens por segundo (default 2.0 → 500ms entre inferências)
        burst: tokens acumuláveis quando ocioso (default 3 → 3 starts rápidos)
        max_debt: quantos tokens negativos um request de alta prioridade pode
                  tomar emprestado (default 1)
    """

    def __init__(self, rate: float = 2.0, burst: int = 3, max_debt: int = 1) -> None:
        self.rate = rate
        self.burst = float(burst)
        self.max_debt = float(max_debt)
        self._tokens = self.burst
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_refill = now

    async def acquire(self, priority: float = 0.5) -> bool:
        """Tenta consumir um token.

        Retorna True se permitido, False se deve pular (synthetic_success).

        priority: 0.0-1.0, maior = mais importante.
          - Se há tokens → consome e retorna True.
          - Se sem tokens + priority >= 0.7 → toma emprestado (vai a negativo).
          - Se sem tokens + priority < 0.7 → retorna False.
        """
        async with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            if priority >= 0.7 and self._tokens > -self.max_debt:
                self._tokens -= 1.0
                return True
            return False

    @property
    def utilization(self) -> float:
        """0.0 (vazio/sob carga) a 1.0 (cheio/ocioso)."""
        return max(0.0, min(1.0, self._tokens / self.burst))


class LocalModelGate:
    """Portão adaptativo para acesso ao modelo local.

    Combina TokenBucket + mapeamento de prioridade por node_id +
    circuit breaker por latência + ajuste dinâmico de taxa.

    Uso como singleton global via get_local_model_gate().
    """

    _instance: ClassVar['LocalModelGate | None'] = None
    _instance_lock = asyncio.Lock()

    # Mapa de prioridade base — node_id → score 0.0-1.0
    _PRIORITY_MAP: ClassVar[dict[str, float]] = {
        "critic": 0.95,
        "planner": 0.75,
        "architect": 0.72,
        "coder": 0.65,
        "debugger": 0.60,
        "tester": 0.55,
        "validator": 0.50,
        "search": 0.50,
        "pm": 0.50,
        "dependency": 0.45,
        "security": 0.45,
        "enhancement": 0.45,
        "reflexion": 0.60,
        "orchestrator": 0.70,
        "result": 0.40,
        "retrospective": 0.35,
        "scheduler": 0.30,
        "skill": 0.30,
        "evolution": 0.65,
    }

    def __init__(self) -> None:
        self.bucket = TokenBucket(rate=2.0, burst=3, max_debt=1)
        self._latency_samples: list[float] = []
        self._avg_latency = 0.0
        self._circuit_until = 0.0

    @classmethod
    async def get_instance(cls) -> 'LocalModelGate':
        async with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    @classmethod
    def get_priority(cls, node_id: str) -> float:
        """Mapeia node_id para prioridade 0.0-1.0."""
        if not node_id:
            return 0.3
        nid = node_id.lower().replace("_agent", "").replace("agent_", "").replace("no_", "")
        for key, prio in cls._PRIORITY_MAP.items():
            if key in nid:
                return prio
        return 0.35  # default baixo — fail-safe

    async def try_acquire(self, node_id: str) -> bool:
        """Tenta adquirir permissão para inferência local.

        Retorna False → o chamador deve usar synthetic_success (fallback sem LLM).
        """
        now = time.monotonic()
        priority = self.get_priority(node_id)

        if now < self._circuit_until:
            if priority < 0.7:
                logger.info(
                    "[LOCAL_GATE] Circuit breaker aberto — rejeitando %s "
                    "(priority=%.2f, avg_latency=%.0fms)",
                    node_id, priority, self._avg_latency,
                )
                return False

        allowed = await self.bucket.acquire(priority=priority)
        if not allowed:
            logger.info(
                "[LOCAL_GATE] Bucket vazio — rejeitando %s "
                "(priority=%.2f, utilization=%.0f%%)",
                node_id, priority, self.bucket.utilization * 100,
            )
        return allowed

    def report_latency(self, latency_ms: float) -> None:
        """Registra latência e ajusta circuit breaker / taxa dinâmica."""
        self._latency_samples.append(latency_ms)
        if len(self._latency_samples) > 20:
            self._latency_samples.pop(0)
        self._avg_latency = sum(self._latency_samples) / len(self._latency_samples)

        # Circuit breaker: latência alta → abre por 30s
        if self._avg_latency > 1000 and self._circuit_until < time.monotonic():
            self._circuit_until = time.monotonic() + 30.0
            logger.warning(
                "[LOCAL_GATE] Circuit breaker ACIONADO (avg_latency=%.0fms > 1000ms)",
                self._avg_latency,
            )

        # Ajuste dinâmico de taxa
        old_rate = self.bucket.rate
        if self._avg_latency > 1000:
            self.bucket.rate = 1.0  # 1 inferência por segundo
        elif self._avg_latency < 300:
            self.bucket.rate = 4.0  # 4 inferências por segundo (burst)
        else:
            self.bucket.rate = 2.0  # nominal

        if abs(old_rate - self.bucket.rate) > 0.01:
            logger.debug(
                "[LOCAL_GATE] Taxa ajustada: %.1f → %.1f tok/s (latency=%.0fms)",
                old_rate, self.bucket.rate, self._avg_latency,
            )

    @property
    def is_degraded(self) -> bool:
        """True se o sistema está sob estresse (latência > 800ms ou bucket vazio)."""
        return self._avg_latency > 800 or self.bucket.utilization < 0.3
