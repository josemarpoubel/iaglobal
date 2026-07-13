# iaglobal/evolution/homeostasis_controller.py

"""HomeostasisController — mantém SLA via loop fechado de feedback."""

import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from iaglobal.evolution.epigenetic import set_flag, get_flag

logger = logging.getLogger(__name__)


# SLA Thresholds (configurable via env)
MAX_LATENCY_MS = float(
    getattr(__import__("os"), "environ", {}).get("MAX_LATENCY_MS", "5000")
)
MAX_ERROR_RATE = float(
    getattr(__import__("os"), "environ", {}).get("MAX_ERROR_RATE", "0.3")
)
MAX_COST_USD_PER_TASK = float(
    getattr(__import__("os"), "environ", {}).get("MAX_COST_USD_PER_TASK", "0.50")
)


@dataclass
class SLAMetrics:
    """Métricas de SLA coletadas no ciclo."""

    total_executions: int = 0
    successful: int = 0
    total_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    start_time: float = field(default_factory=lambda: time.time())

    @property
    def error_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return 1.0 - (self.successful / self.total_executions)

    @property
    def avg_latency_ms(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.total_latency_ms / self.total_executions

    @property
    def avg_cost_per_task(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.total_cost_usd / self.total_executions


class HomeostasisController:
    """Controlador de homeostase — ajusta políticas baseado em SLA."""

    _instance: Optional["HomeostasisController"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.metrics = SLAMetrics()

    @classmethod
    def get_instance(cls) -> "HomeostasisController":
        return cls()

    def record_execution(self, success: bool, latency_ms: float, cost_usd: float):
        """Registra métrica de execução."""
        self.metrics.total_executions += 1
        if success:
            self.metrics.successful += 1
        self.metrics.total_latency_ms += latency_ms
        self.metrics.total_cost_usd += cost_usd

    def check_sla(self) -> Dict[str, Any]:
        """Verifica se SLA está sendo violado."""
        violations = []

        if self.metrics.avg_latency_ms > MAX_LATENCY_MS:
            violations.append(
                {
                    "type": "latency",
                    "value": self.metrics.avg_latency_ms,
                    "threshold": MAX_LATENCY_MS,
                }
            )

        if self.metrics.error_rate > MAX_ERROR_RATE:
            violations.append(
                {
                    "type": "error_rate",
                    "value": self.metrics.error_rate,
                    "threshold": MAX_ERROR_RATE,
                }
            )

        if self.metrics.avg_cost_per_task > MAX_COST_USD_PER_TASK:
            violations.append(
                {
                    "type": "cost",
                    "value": self.metrics.avg_cost_per_task,
                    "threshold": MAX_COST_USD_PER_TASK,
                }
            )

        return {
            "in_compliance": len(violations) == 0,
            "violations": violations,
            "metrics": {
                "error_rate": self.metrics.error_rate,
                "avg_latency_ms": self.metrics.avg_latency_ms,
                "avg_cost_per_task": self.metrics.avg_cost_per_task,
                "total_executions": self.metrics.total_executions,
            },
        }

    def apply_adjustments(
        self, sla_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Ajusta politicas (flags epigeneticas) com base em violacoes de SLA.

        Returns o resumo dos ajustes aplicados.
        """
        sla = sla_result if sla_result else self.check_sla()
        if sla["in_compliance"]:
            return {"adjusted": False, "changes": []}

        current_epsilon = get_flag("bandit_epsilon")
        new_epsilon = current_epsilon
        changes: List[Dict[str, Any]] = []
        penalty = 1.0

        for v in sla["violations"]:
            vtype = v["type"]
            ratio = v["value"] / v["threshold"] if v["threshold"] > 0 else 1.0
            severity = min(ratio - 1.0, 2.0)

            if vtype == "latency":
                factor = max(0.5, 1.0 - severity * 0.3)
                new_epsilon *= factor
                changes.append(
                    {
                        "type": "latency",
                        "reason": f"avg={v['value']:.0f}ms > threshold={v['threshold']:.0f}ms",
                        "epsilon_factor": round(factor, 3),
                        "severity": round(severity, 2),
                    }
                )

            elif vtype == "error_rate":
                factor = max(0.4, 1.0 - severity * 0.4)
                new_epsilon *= factor
                changes.append(
                    {
                        "type": "error_rate",
                        "reason": f"rate={v['value']:.2f} > threshold={v['threshold']:.2f}",
                        "epsilon_factor": round(factor, 3),
                        "severity": round(severity, 2),
                    }
                )

            elif vtype == "cost":
                factor = max(0.6, 1.0 - severity * 0.2)
                new_epsilon *= factor
                sam_mult = get_flag("sam_budget_multiplier", 1.0)
                set_flag("sam_budget_multiplier", max(0.5, sam_mult * 0.9))
                changes.append(
                    {
                        "type": "cost",
                        "reason": f"avg=${v['value']:.4f} > threshold=${v['threshold']:.2f}",
                        "epsilon_factor": round(factor, 3),
                        "severity": round(severity, 2),
                        "sam_budget_multiplier_adjusted": True,
                    }
                )

            penalty *= factor

        new_epsilon = max(0.05, min(0.5, new_epsilon))
        set_flag("bandit_epsilon", new_epsilon)

        if abs(new_epsilon - current_epsilon) > 0.001:
            logger.info(
                "[HOMEOSTASIS] SLA violado — epsilon ajustado: %.3f → %.3f (penalty=%.3f, %d violacao(oes))",
                current_epsilon,
                new_epsilon,
                penalty,
                len(sla["violations"]),
            )
            for c in changes:
                logger.info(
                    "[HOMEOSTASIS]   → %(type)s: %(reason)s (epsilon x%(epsilon_factor).3f)",
                    c,
                )

        return {
            "adjusted": True,
            "epsilon_before": current_epsilon,
            "epsilon_after": new_epsilon,
            "penalty_factor": round(penalty, 3),
            "violations": len(sla["violations"]),
            "changes": changes,
        }


# Singleton instance
homeostasis_controller = HomeostasisController()
