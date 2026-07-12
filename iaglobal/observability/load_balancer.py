# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
PhospholipidLoadBalancer — Weighted Round-Robin com Adaptive Decay.

Seleciona serviços saudáveis proporcionalmente ao peso.
Adaptive decay: falhas reduzem peso em 20%, sucessos aumentam 5%.
Integrado com Chappie (IVM como peso inicial) e GlutathionePool (falhas).
"""

import asyncio
import logging
import time
from typing import Any, Optional

from iaglobal.observability.registry import PhospholipidRegistry, ServiceInstance, registry as default_registry
from iaglobal.immunity.glutathione_pool import GlutathionePool
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.observability.load_balancer")

DECAY_ON_FAILURE = 0.8
BOOST_ON_SUCCESS = 1.05
WEIGHT_MIN = 0.1
WEIGHT_MAX = 1.0


class PhospholipidLoadBalancer:
    """Weighted round-robin com adaptive decay e integração imunológica."""

    def __init__(self, registry: Optional[PhospholipidRegistry] = None):
        self.registry = registry or default_registry
        self._pool = GlutathionePool()
        self._index = 0

    async def select(self, service_type: str = "") -> Optional[ServiceInstance]:
        """Seleciona serviço via weighted round-robin."""
        self.registry.check_timeouts()
        services = self.registry.healthy_services()

        if service_type:
            services = [s for s in services if s.name.startswith(service_type)]

        if not services:
            return None

        services.sort(key=lambda s: s.weight, reverse=True)

        self._index %= len(services)
        selected = services[self._index]
        self._index = (self._index + 1) % len(services)
        return selected

    async def request(self, service_name: str, timeout: float = 10.0) -> dict[str, Any]:
        """Executa requisição a um serviço com monitoramento de falha."""
        instance = self.registry.get(service_name)
        if instance is None:
            return {"success": False, "error": "Serviço não registrado"}

        if instance.active_requests >= instance.capacity:
            return {"success": False, "error": "Capacidade excedida"}

        instance.active_requests += 1
        start = time.time()
        success = False

        try:
            result = await self._call_service(instance)
            success = True
            return result
        except Exception as e:
            self._handle_failure(instance, e)
            return {"success": False, "error": str(e)}
        finally:
            latency = (time.time() - start) * 1000
            instance.active_requests -= 1
            self.registry.report_health(service_name, latency_ms=latency, error=not success)

    async def _call_service(self, instance: ServiceInstance) -> dict[str, Any]:
        """Chamada real ao endpoint do serviço."""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                instance.endpoint,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status >= 500:
                    raise RuntimeError(f"HTTP {resp.status}")
                data = await resp.json()
                return {"success": True, "status": resp.status, "data": data}

    def _handle_failure(self, instance: ServiceInstance, error: Exception):
        """Registra falha no GlutathionePool e aplica adaptive decay."""
        logger.warning("[PHOSPHOLIPID] Falha em %s: %s", instance.name, error)

        self._pool.respond("service_failure", {
            "service": instance.name,
            "error": str(error),
            "consecutive_failures": instance.consecutive_failures,
        })

        instance.consecutive_failures += 1
        instance.weight = max(WEIGHT_MIN, instance.weight * DECAY_ON_FAILURE)
        instance.error_rate = min(1.0, instance.error_rate + 0.1)

        if instance.weight < 0.2:
            instance.health = False
            logger.warning("[PHOSPHOLIPID] Serviço removido do pool: %s (peso=%.4f)", instance.name, instance.weight)

    def report_success(self, service_name: str):
        """Registra sucesso e aumenta peso."""
        instance = self.registry.get(service_name)
        if instance is None:
            return
        instance.consecutive_failures = 0
        instance.error_rate = max(0.0, instance.error_rate - 0.05)
        instance.weight = min(WEIGHT_MAX, instance.weight * BOOST_ON_SUCCESS)

    @staticmethod
    def ivm_to_weight(ivm: float) -> float:
        """Converte IVM (0-1) em peso inicial (0.1-1.0)."""
        return max(WEIGHT_MIN, min(WEIGHT_MAX, ivm))


load_balancer = PhospholipidLoadBalancer()