# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
PhospholipidRegistry — registro de serviços com heartbeat e health check.

Cada ServiceInstance carrega endpoint, peso, saúde, capacidade e métricas
de latência/erro para alimentar o load balancer.
"""

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from iaglobal._paths import PROJECT_ROOT
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.observability.registry")

AUDIT_PATH = (
    Path(PROJECT_ROOT)
    / "iaglobal"
    / "memory"
    / "data"
    / "json"
    / "phospholipid_audit.json"
)

HEARTBEAT_INTERVAL = 5.0
HEARTBEAT_TIMEOUT = 15.0
RECOVERY_THRESHOLD = 3


@dataclass
class ServiceInstance:
    name: str
    endpoint: str
    weight: float = 1.0
    health: bool = True
    capacity: int = 10
    active_requests: int = 0
    last_heartbeat: float = 0.0
    latency_p95_ms: float = 0.0
    error_rate: float = 0.0
    consecutive_failures: int = 0
    consecutive_heartbeats_ok: int = 0


class PhospholipidRegistry:
    """Registro central de serviços com heartbeat e health check."""

    def __init__(self):
        self._services: dict[str, ServiceInstance] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None

    def register(
        self, name: str, endpoint: str, weight: float = 1.0, capacity: int = 10
    ) -> ServiceInstance:
        instance = ServiceInstance(
            name=name,
            endpoint=endpoint,
            weight=max(0.1, min(weight, 1.0)),
            capacity=capacity,
            last_heartbeat=time.time(),
        )
        self._services[name] = instance
        logger.info(
            "[PHOSPHOLIPID] Serviço registrado: %s → %s (peso=%.2f, cap=%d)",
            name,
            endpoint,
            weight,
            capacity,
        )
        self._audit(
            "service_registered",
            name,
            {"endpoint": endpoint, "weight": weight, "capacity": capacity},
        )
        return instance

    def unregister(self, name: str):
        if name in self._services:
            del self._services[name]
            logger.info("[PHOSPHOLIPID] Serviço removido: %s", name)
            self._audit("service_unregistered", name, {})

    def get(self, name: str) -> Optional[ServiceInstance]:
        return self._services.get(name)

    def heartbeat(self, name: str):
        instance = self._services.get(name)
        if instance is None:
            return
        instance.last_heartbeat = time.time()
        instance.consecutive_heartbeats_ok += 1

        if (
            not instance.health
            and instance.consecutive_heartbeats_ok >= RECOVERY_THRESHOLD
        ):
            instance.health = True
            instance.weight = 0.5
            instance.consecutive_failures = 0
            logger.info(
                "[PHOSPHOLIPID] Serviço recuperado: %s (peso=%.2f)",
                name,
                instance.weight,
            )
            self._audit("recovery", name, {"new_weight": instance.weight})

    def report_health(self, name: str, latency_ms: float = 0.0, error: bool = False):
        instance = self._services.get(name)
        if instance is None:
            return
        instance.latency_p95_ms = (
            latency_ms if latency_ms > 0 else instance.latency_p95_ms
        )

        if error:
            instance.consecutive_failures += 1
            instance.error_rate = min(1.0, instance.error_rate + 0.1)
            instance.weight = max(0.1, instance.weight * 0.8)
            self._audit(
                "failure_detected",
                name,
                {
                    "consecutive_failures": instance.consecutive_failures,
                    "new_weight": round(instance.weight, 4),
                },
            )
            if instance.weight < 0.2:
                instance.health = False
                logger.warning(
                    "[PHOSPHOLIPID] Serviço unhealthy: %s (peso=%.4f)",
                    name,
                    instance.weight,
                )
                self._audit(
                    "health_changed", name, {"health": False, "weight": instance.weight}
                )
        else:
            instance.consecutive_failures = 0
            instance.error_rate = max(0.0, instance.error_rate - 0.05)
            instance.weight = min(1.0, instance.weight * 1.05)

    def healthy_services(self) -> list[ServiceInstance]:
        now = time.time()
        return [
            s
            for s in self._services.values()
            if s.health and (now - s.last_heartbeat) < HEARTBEAT_TIMEOUT
        ]

    def start_heartbeat_loop(self, name: str):
        """Inicia heartbeat loop em background para um serviço (5s)."""
        instance = self._services.get(name)
        if instance is None:
            return

        async def _loop():
            while name in self._services:
                self.heartbeat(name)
                await asyncio.sleep(HEARTBEAT_INTERVAL)

        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(_loop())

    def check_timeouts(self):
        """Marca como unhealthy serviços sem heartbeat recente."""
        now = time.time()
        for instance in self._services.values():
            if instance.health and (now - instance.last_heartbeat) > HEARTBEAT_TIMEOUT:
                instance.health = False
                logger.warning(
                    "[PHOSPHOLIPID] Heartbeat timeout: %s (%.1fs sem beat)",
                    instance.name,
                    now - instance.last_heartbeat,
                )
                self._audit(
                    "health_changed",
                    instance.name,
                    {"health": False, "reason": "heartbeat_timeout"},
                )

    def _audit(self, event: str, service: str, details: dict):
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": event,
            "service": service,
            "details": details,
        }
        try:
            AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
            if AUDIT_PATH.exists():
                data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
            else:
                data = {"events": []}
            data["events"].append(entry)
            if len(data["events"]) > 1000:
                data["events"] = data["events"][-1000:]
            AUDIT_PATH.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            logger.error("Erro ao escrever audit trail: %s", e)

    def service_count(self) -> int:
        return len(self._services)

    def healthy_count(self) -> int:
        return len(self.healthy_services())


registry = PhospholipidRegistry()
