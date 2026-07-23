# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
SemaphoreTracker — telemetria de concorrência dos semáforos do Bandit.

Para cada tentativa de acquire/release, registra:
  - model_name
  - node_id (quem está solicitando)
  - timestamp
  - latency de espera
  - resultado (acquired / timeout / gate_rejected / released)

Mantém contadores acumulados para diagnóstico de starvation e leak.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from iaglobal.observability.execution_events import emit as emit_exec_event


@dataclass
class SemaphoreEvent:
    """Um único evento de semáforo (acquire, release, timeout, etc.)."""

    event_type: (
        str  # "acquire_start", "acquired", "timeout", "gate_rejected", "released"
    )
    model_name: str
    node_id: str
    timestamp: float = field(default_factory=time.time)
    latency_ms: float = 0.0
    retry_round: int = 0
    message: str = ""


@dataclass
class ModelSemaphoreMetrics:
    """Métricas acumuladas por modelo."""

    acquires: int = 0
    releases: int = 0
    timeouts: int = 0
    gate_rejections: int = 0
    starvations: int = 0
    total_wait_ms: float = 0.0
    max_wait_ms: float = 0.0
    last_event_ts: float = 0.0
    recent_events: List[SemaphoreEvent] = field(default_factory=list)

    @property
    def avg_wait_ms(self) -> float:
        if self.acquires == 0:
            return 0.0
        return round(self.total_wait_ms / self.acquires, 1)

    @property
    def leak_ratio(self) -> float:
        if self.acquires == 0:
            return 0.0
        return round(abs(self.acquires - self.releases) / self.acquires, 4)

    @property
    def timeout_rate(self) -> float:
        total = self.acquires + self.timeouts
        if total == 0:
            return 0.0
        return round(self.timeouts / total, 4)


class SemaphoreTracker:
    """
    Coletor central de telemetria de semáforos.

    Uso:
        tracker = SemaphoreTracker()
        tracker.record_acquire_start("groq/llama", "critic")
        # ... aguarda semáforo ...
        if acquired:
            tracker.record_acquired("groq/llama", "critic", latency_ms=12.5)
        else:
            tracker.record_timeout("groq/llama", "critic", latency_ms=3000.0)
    """

    def __init__(self, max_recent_per_model: int = 20) -> None:
        self._models: Dict[str, ModelSemaphoreMetrics] = defaultdict(
            ModelSemaphoreMetrics
        )
        self._max_recent = max_recent_per_model

    def get_metrics(self, model_name: str) -> ModelSemaphoreMetrics:
        return self._models[model_name]

    def all_metrics(self) -> Dict[str, ModelSemaphoreMetrics]:
        return dict(self._models)

    def record_acquire_start(
        self, model_name: str, node_id: str, execution_id: str = ""
    ) -> None:
        """Chamado antes de tentar acquire (para medir latência de espera)."""
        ev = SemaphoreEvent(
            event_type="acquire_start",
            model_name=model_name,
            node_id=node_id,
        )
        mm = self._models[model_name]
        mm.last_event_ts = ev.timestamp
        mm.recent_events.append(ev)
        self._trim(mm)

    def record_acquired(
        self,
        model_name: str,
        node_id: str,
        latency_ms: float,
        retry_round: int = 0,
        execution_id: str = "",
    ) -> None:
        """Semáforo adquirido com sucesso."""
        mm = self._models[model_name]
        mm.acquires += 1
        mm.total_wait_ms += latency_ms
        mm.max_wait_ms = max(mm.max_wait_ms, latency_ms)
        mm.last_event_ts = time.time()

        ev = SemaphoreEvent(
            event_type="acquired",
            model_name=model_name,
            node_id=node_id,
            latency_ms=round(latency_ms, 1),
            retry_round=retry_round,
            message=f"acquired after {latency_ms:.0f}ms wait",
        )
        mm.recent_events.append(ev)
        self._trim(mm)

        emit_exec_event(
            "semaphore_acquired",
            execution_id,
            node_id,
            model=model_name,
            wait_ms=round(latency_ms, 1),
            retry_round=retry_round,
        )

    def record_timeout(
        self, model_name: str, node_id: str, latency_ms: float, execution_id: str = ""
    ) -> None:
        """Timeout no acquire do semáforo."""
        mm = self._models[model_name]
        mm.timeouts += 1
        mm.last_event_ts = time.time()

        ev = SemaphoreEvent(
            event_type="timeout",
            model_name=model_name,
            node_id=node_id,
            latency_ms=round(latency_ms, 1),
            message=f"timeout after {latency_ms:.0f}ms",
        )
        mm.recent_events.append(ev)
        self._trim(mm)

        emit_exec_event(
            "semaphore_timeout",
            execution_id,
            node_id,
            model=model_name,
            wait_ms=round(latency_ms, 1),
        )

    def record_gate_rejected(
        self, model_name: str, node_id: str, execution_id: str = ""
    ) -> None:
        """Rejeitado pelo LocalModelGate (token bucket) antes do semáforo."""
        mm = self._models[model_name]
        mm.gate_rejections += 1
        mm.last_event_ts = time.time()

        ev = SemaphoreEvent(
            event_type="gate_rejected",
            model_name=model_name,
            node_id=node_id,
            message="rejected by LocalModelGate",
        )
        mm.recent_events.append(ev)
        self._trim(mm)

        emit_exec_event(
            "semaphore_gate_rejected",
            execution_id,
            node_id,
            model=model_name,
        )

    def record_released(
        self, model_name: str, node_id: str, execution_id: str = ""
    ) -> None:
        """Semáforo liberado."""
        mm = self._models[model_name]
        mm.releases += 1
        mm.last_event_ts = time.time()

        ev = SemaphoreEvent(
            event_type="released",
            model_name=model_name,
            node_id=node_id,
            message="released",
        )
        mm.recent_events.append(ev)
        self._trim(mm)

        emit_exec_event(
            "semaphore_released",
            execution_id,
            node_id,
            model=model_name,
        )

    def record_starvation(
        self,
        node_id: str,
        candidates: List[str],
        retry_rounds: int,
        execution_id: str = "",
    ) -> None:
        """Todos os candidatos falharam após N retries (starvation)."""
        for model_name in candidates:
            mm = self._models[model_name]
            mm.starvations += 1
            mm.last_event_ts = time.time()

        emit_exec_event(
            "semaphore_starvation",
            execution_id,
            node_id,
            candidates=candidates,
            retry_rounds=retry_rounds,
        )

    def health_report(self) -> Dict[str, Dict[str, float]]:
        """Relatório de saúde dos semáforos."""
        report: Dict[str, Dict[str, float]] = {}
        for model_name, mm in self._models.items():
            report[model_name] = {
                "acquires": mm.acquires,
                "releases": mm.releases,
                "timeouts": mm.timeouts,
                "gate_rejections": mm.gate_rejections,
                "starvations": mm.starvations,
                "avg_wait_ms": mm.avg_wait_ms,
                "max_wait_ms": round(mm.max_wait_ms, 1),
                "timeout_rate": mm.timeout_rate,
                "leak_ratio": mm.leak_ratio,
            }
        return report

    def _trim(self, mm: ModelSemaphoreMetrics) -> None:
        """Mantém apenas os N eventos mais recentes."""
        if len(mm.recent_events) > self._max_recent:
            mm.recent_events = mm.recent_events[-self._max_recent :]


# Singleton global
_semaphore_tracker: Optional[SemaphoreTracker] = None


def get_semaphore_tracker() -> SemaphoreTracker:
    global _semaphore_tracker
    if _semaphore_tracker is None:
        _semaphore_tracker = SemaphoreTracker()
    return _semaphore_tracker


__all__ = [
    "SemaphoreTracker",
    "SemaphoreEvent",
    "ModelSemaphoreMetrics",
    "get_semaphore_tracker",
]
