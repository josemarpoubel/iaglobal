# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ColonyFitness — Seleção de Fitness da Colônia.

Avalia IVM independente por organismo, executa apoptose para IVM < threshold
e mitose para organismos saudáveis (IVM ≥ 0.7).
"""

import time
from dataclasses import dataclass
from typing import Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.communication.fitness")

IVM_EXCELENTE = 0.7
IVM_CRITICO = 0.3


@dataclass
class OrganismMetrics:
    """Métricas de fitness de um organismo."""

    organism_id: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_latency_ms: float = 0.0
    skills_exchanged: int = 0
    last_seen: float = 0.0

    @property
    def productivity(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return self.tasks_completed / total if total > 0 else 0.0

    @property
    def energy_efficiency(self) -> float:
        if self.total_latency_ms <= 0:
            return 0.5
        normalized = min(self.total_latency_ms / 5000.0, 1.0)
        return 1.0 - normalized

    @property
    def cooperation(self) -> float:
        return min(self.skills_exchanged / 10.0, 1.0)

    @property
    def ivm(self) -> float:
        return (
            self.productivity * 0.4
            + self.energy_efficiency * 0.4
            + self.cooperation * 0.2
        )


class ColonyFitness:
    """Avalia e gerencia fitness de múltiplos organismos na colônia."""

    def __init__(self):
        self._organisms: dict[str, OrganismMetrics] = {}

    def register_organism(self, organism_id: str):
        if organism_id not in self._organisms:
            self._organisms[organism_id] = OrganismMetrics(
                organism_id=organism_id, last_seen=time.time()
            )
            logger.info("[FITNESS] Organismo registrado: %s", organism_id)

    def record_task(self, organism_id: str, success: bool, latency_ms: float = 0.0):
        metrics = self._organisms.get(organism_id)
        if metrics is None:
            return
        if success:
            metrics.tasks_completed += 1
        else:
            metrics.tasks_failed += 1
        metrics.total_latency_ms += latency_ms
        metrics.last_seen = time.time()

    def record_skill_exchange(self, organism_id: str, count: int = 1):
        metrics = self._organisms.get(organism_id)
        if metrics:
            metrics.skills_exchanged += count
            metrics.last_seen = time.time()

    def get_organism_ivm(self, organism_id: str) -> float:
        metrics = self._organisms.get(organism_id)
        return metrics.ivm if metrics else 0.0

    def rank_organisms(self) -> list[dict]:
        return sorted(
            [
                {
                    "organism_id": o.organism_id,
                    "ivm": round(o.ivm, 4),
                    "productivity": round(o.productivity, 4),
                    "energy_efficiency": round(o.energy_efficiency, 4),
                    "cooperation": round(o.cooperation, 4),
                    "tasks_completed": o.tasks_completed,
                    "tasks_failed": o.tasks_failed,
                }
                for o in self._organisms.values()
            ],
            key=lambda x: x["ivm"],
            reverse=True,
        )

    async def check_apoptosis(self, organism_id: str) -> Optional[dict]:
        """Retorna decisão de apoptose se IVM < threshold crítico."""
        metrics = self._organisms.get(organism_id)
        if not metrics:
            return None

        if metrics.ivm < IVM_CRITICO:
            logger.warning(
                "[FITNESS] Apoptose: %s IVM=%.4f < %.2f",
                organism_id,
                metrics.ivm,
                IVM_CRITICO,
            )
            lessons = await self._extract_lessons(organism_id)
            del self._organisms[organism_id]
            return {
                "action": "apoptosis",
                "organism_id": organism_id,
                "ivm": round(metrics.ivm, 4),
                "lessons": lessons,
            }
        return None

    async def check_mitosis(
        self, organism_id: str, specialization: str = ""
    ) -> Optional[str]:
        """Gera novo organismo a partir de um saudável (IVM ≥ 0.7)."""
        metrics = self._organisms.get(organism_id)
        if not metrics or metrics.ivm < IVM_EXCELENTE:
            return None

        child_id = (
            f"{organism_id}-{specialization or 'child'}-{int(time.time()) % 1000}"
        )
        self.register_organism(child_id)

        child_metrics = self._organisms[child_id]
        child_metrics.tasks_completed = metrics.tasks_completed // 2
        child_metrics.skills_exchanged = max(metrics.skills_exchanged - 1, 0)

        logger.info(
            "[FITNESS] Mitose: %s → %s (IVM pai=%.4f)",
            organism_id,
            child_id,
            metrics.ivm,
        )
        return child_id

    async def _extract_lessons(self, organism_id: str) -> dict:
        """Extrai lições do organismo antes da apoptose."""
        metrics = self._organisms.get(organism_id)
        return {
            "organism_id": organism_id,
            "total_tasks": (metrics.tasks_completed + metrics.tasks_failed)
            if metrics
            else 0,
            "success_rate": metrics.productivity if metrics else 0.0,
            "ivm_final": metrics.ivm if metrics else 0.0,
        }

    def organism_count(self) -> int:
        return len(self._organisms)

    def get_all_ivms(self) -> dict[str, float]:
        return {oid: m.ivm for oid, m in self._organisms.items()}

    def average_ivm(self) -> float:
        if not self._organisms:
            return 0.0
        return sum(m.ivm for m in self._organisms.values()) / len(self._organisms)
