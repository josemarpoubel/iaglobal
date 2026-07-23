# iaglobal/metabolism/bucket_manager.py
# Sistema Endócrino — Regula a liberação de ATP (tokens) por tier cognitivo.
# BucketManager (singleton) gerencia três TokenBuckets independentes,
# um para cada papel cognitivo (JUIZ, OPERARIO, SENTINELA).

import asyncio
import time
from typing import ClassVar

from iaglobal.providers.provider_config import ProviderConfig, CognitiveRole
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.metabolism.bucket_manager")


_ROLE_TO_ROUTE: dict[CognitiveRole, str] = {
    CognitiveRole.JUIZ: "ollama",
    CognitiveRole.OPERARIO: "ollama",
    CognitiveRole.SENTINELA: "ollama",
}

_ROUTE_TO_ROLE: dict[str, CognitiveRole] = {v: k for k, v in _ROLE_TO_ROUTE.items()}


class TokenBucket:
    """Bucket de tokens com controle de concorrência e refill temporal.

    Diferencia do TokenBucket em execution/token_bucket.py por usar
    limites absolutos (capacity, max_concurrent) vindos do ProviderConfig,
    em vez de rate + burst adaptativo.
    """

    def __init__(
        self,
        capacity: int,
        fill_rate: float,
        max_concurrent: int,
    ) -> None:
        self.capacity = float(capacity)
        self.fill_rate = fill_rate
        self.max_concurrent = max_concurrent

        self.tokens = self.capacity
        self.current_concurrent = 0
        self._rejections = 0  # Contador de negações para métricas JOL
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
        self._last_refill = now

    async def acquire(self, estimated_tokens: int = 100, timeout: float = 0.0) -> bool:
        """Tenta consumir *estimated_tokens* do bucket.

        timeout=0 → non-blocking (retorna False imediatamente se insuficiente).
        timeout>0 → espera até N segundos por um slot + tokens.
        """
        deadline = time.monotonic() + timeout if timeout > 0 else None

        while True:
            async with self._lock:
                self._refill()
                if (
                    self.current_concurrent < self.max_concurrent
                    and self.tokens >= estimated_tokens
                ):
                    self.current_concurrent += 1
                    self.tokens -= estimated_tokens
                    logger.debug(
                        "[BUCKET] acquired tokens=%d concurrent=%d/%d remaining=%.0f",
                        estimated_tokens,
                        self.current_concurrent,
                        self.max_concurrent,
                        self.tokens,
                    )
                    return True

            if deadline is not None and time.monotonic() < deadline:
                await asyncio.sleep(0.05)
                continue

            logger.debug(
                "[BUCKET] acquire rejected (concurrent=%d/%d tokens=%.0f)",
                self.current_concurrent,
                self.max_concurrent,
                self.tokens,
            )
            self._rejections += 1  # Contabilizar rejeição para métricas JOL
            return False

    async def release(self) -> None:
        """Libera um slot de concorrência."""
        async with self._lock:
            self.current_concurrent = max(0, self.current_concurrent - 1)

    @property
    def utilization(self) -> float:
        """0.0 (vazio) a 1.0 (cheio/ocioso)."""
        return max(0.0, min(1.0, self.tokens / max(self.capacity, 1)))

    @property
    def rejections(self) -> int:
        """Total de negações deste bucket (para JOLMetricsCollector)."""
        return self._rejections


class BucketManager:
    """Sistema Endócrino — regula a liberação de ATP (tokens) por tier.

    Singleton global acessado via BucketManager.get_instance().
    Cada rota cognitiva tem seu próprio TokenBucket com os limites
    definidos em ProviderConfig.COGNITIVE_MODELS.
    """

    _instance: ClassVar["BucketManager | None"] = None
    _instance_lock = asyncio.Lock()

    def __init__(self) -> None:
        self.buckets: dict[str, TokenBucket] = {}
        self._initialize_buckets()

    def _initialize_buckets(self) -> None:
        for role, config in ProviderConfig.COGNITIVE_MODELS.items():
            route = _ROLE_TO_ROUTE.get(role)
            if not route:
                continue
            self.buckets[route] = TokenBucket(
                capacity=config["tokens_per_minute_limit"],
                fill_rate=config["tokens_per_minute_limit"] / 60.0,
                max_concurrent=config["max_concurrent_requests"],
            )
        logger.info(
            "[ENDÓCRINO] Buckets inicializados: %s",
            {
                r: {"max_conc": b.max_concurrent, "cap": b.capacity}
                for r, b in self.buckets.items()
            },
        )

    @classmethod
    async def get_instance(cls) -> "BucketManager":
        async with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def _get_bucket(self, route_name: str) -> TokenBucket | None:
        return self.buckets.get(route_name)

    @classmethod
    def route_for_role(cls, role: CognitiveRole) -> str:
        return _ROLE_TO_ROUTE.get(role, "ollama")

    @classmethod
    def role_for_route(cls, route: str) -> CognitiveRole | None:
        return _ROUTE_TO_ROLE.get(route)

    async def acquire(
        self, route_name: str, estimated_tokens: int = 100, timeout: float = 0.0
    ) -> bool:
        """Tenta adquirir recursos do bucket da rota.

        Se timeout=0 (default), retorna False imediatamente se o bucket
        não puder atender.  timeout>0 espera até N segundos (fila curta).
        """
        bucket = self._get_bucket(route_name)
        if not bucket:
            logger.warning("[ENDÓCRINO] Rota '%s' sem bucket registrado", route_name)
            return False
        return await bucket.acquire(estimated_tokens=estimated_tokens, timeout=timeout)

    async def release(self, route_name: str) -> None:
        """Libera slot de concorrência após inferência."""
        bucket = self._get_bucket(route_name)
        if bucket:
            await bucket.release()

    async def acquire_with_fallback(
        self,
        route_name: str,
        estimated_tokens: int = 100,
        timeout: float = 0.5,
    ) -> str | None:
        """Tenta rota principal; se falhar, tenta fallback_role do ProviderConfig.

        Returns:
            Nome da rota que concedeu o recurso, ou None se ambas falharem.
        """
        if await self.acquire(route_name, estimated_tokens, timeout):
            return route_name

        role = self.role_for_route(route_name)
        if role:
            config = ProviderConfig.get_model_config(role)
            if config and config.get("fallback_role"):
                fb_role: CognitiveRole = config["fallback_role"]
                fb_route = self.route_for_role(fb_role)
                if await self.acquire(fb_route, estimated_tokens, 0.0):
                    logger.info(
                        "[ENDÓCRINO] Fallback %s → %s (tokens=%d)",
                        route_name,
                        fb_route,
                        estimated_tokens,
                    )
                    return fb_route

        return None

    @property
    def summary(self) -> dict:
        """Relatório de status de todos os buckets."""
        return {
            route: {
                "tokens": bucket.tokens,
                "capacity": bucket.capacity,
                "utilization_pct": round(bucket.utilization * 100, 1),
                "concurrent": bucket.current_concurrent,
                "max_concurrent": bucket.max_concurrent,
            }
            for route, bucket in self.buckets.items()
        }

    async def print_summary(self) -> None:
        s = self.summary
        for route, info in s.items():
            logger.info(
                "[ENDÓCRINO] %s: tokens=%.0f/%.0f (%s%%) conc=%d/%d",
                route,
                info["tokens"],
                info["capacity"],
                info["utilization_pct"],
                info["concurrent"],
                info["max_concurrent"],
            )
