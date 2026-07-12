# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
PhospholipidDashboard — dashboard de métricas do PhospholipidRegistry.

Exibe: serviços ativos/inativos, requests/s estimados, latência p95,
error rate, e eventos recentes do audit trail.
"""

import json
import time
from pathlib import Path
from typing import Any

from iaglobal._paths import PROJECT_ROOT
from iaglobal.observability.registry import PhospholipidRegistry, AUDIT_PATH, registry as default_registry
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.dashboard.phospholipid")

AUDIT_PATH = Path(PROJECT_ROOT) / "iaglobal" / "memory" / "data" / "json" / "phospholipid_audit.json"


class PhospholipidDashboard:
    """Dashboard de métricas do PhospholipidRegistry."""

    def __init__(self, registry: PhospholipidRegistry = None):
        self.registry = registry or default_registry

    def summary(self) -> dict[str, Any]:
        """Retorna resumo das métricas atuais."""
        services = self.registry._services.values()
        healthy = self.registry.healthy_services()

        total_latency = sum(s.latency_p95_ms for s in services if s.latency_p95_ms > 0)
        latency_count = sum(1 for s in services if s.latency_p95_ms > 0)
        avg_latency = total_latency / latency_count if latency_count > 0 else 0.0

        error_rates = [s.error_rate for s in services]
        avg_error_rate = sum(error_rates) / len(error_rates) if error_rates else 0.0

        active_reqs = sum(min(s.active_requests, s.capacity) for s in healthy)
        total_capacity = sum(s.capacity for s in healthy)
        utilization = active_reqs / total_capacity if total_capacity > 0 else 0.0

        return {
            "total_services": len(services),
            "healthy_services": len(healthy),
            "unhealthy_services": len(services) - len(healthy),
            "avg_latency_p95_ms": round(avg_latency, 2),
            "avg_error_rate": round(avg_error_rate, 4),
            "utilization_percent": round(utilization * 100, 1),
            "active_requests": active_reqs,
            "total_capacity": total_capacity,
        }

    def service_table(self) -> list[dict[str, Any]]:
        """Tabela detalhada de todos os serviços."""
        return [
            {
                "name": s.name,
                "endpoint": s.endpoint,
                "weight": round(s.weight, 4),
                "health": "✅" if s.health else "❌",
                "active/capacity": f"{s.active_requests}/{s.capacity}",
                "latency_p95_ms": round(s.latency_p95_ms, 2) if s.latency_p95_ms else "-",
                "error_rate": round(s.error_rate, 4),
                "failures": s.consecutive_failures,
            }
            for s in sorted(
                self.registry._services.values(),
                key=lambda x: x.weight,
                reverse=True,
            )
        ]

    def recent_events(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retorna últimos eventos do audit trail."""
        try:
            if AUDIT_PATH.exists():
                data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
                return data["events"][-limit:]
        except Exception as e:
            logger.warning("Erro ao ler audit trail: %s", e)
        return []

    def render_text(self) -> str:
        """Renderiza dashboard em formato texto para CLI."""
        s = self.summary()
        lines = [
            "╔══════════════════════════════════════════════╗",
            "║      PhospholipidRegistry Dashboard          ║",
            "╚══════════════════════════════════════════════╝",
            "",
            f"  Serviços:     {s['total_services']} total · {s['healthy_services']} saudáveis · {s['unhealthy_services']} unhealthy",
            f"  Latência p95: {s['avg_latency_p95_ms']}ms",
            f"  Error rate:   {s['avg_error_rate']:.2%}",
            f"  Utilização:   {s['utilization_percent']}%",
            f"  Ativos/cap:   {s['active_requests']}/{s['total_capacity']}",
            "",
            "── Serviços ──────────────────────────────────",
        ]

        for svc in self.service_table():
            lines.append(
                f"  {svc['health']} {svc['name']:20s} "
                f"peso={svc['weight']:.3f} "
                f"ativos={svc['active/capacity']:>5s} "
                f"lat={svc['latency_p95_ms']}ms "
                f"err={svc['error_rate']:.3f}"
            )

        events = self.recent_events(5)
        if events:
            lines.extend([
                "",
                "── Eventos Recentes ─────────────────────────",
            ])
            for e in events:
                lines.append(f"  {e.get('timestamp', '')[:19]} | {e.get('event', ''):25s} | {e.get('service', '')}")

        return "\n".join(lines)