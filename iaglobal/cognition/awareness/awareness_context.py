# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
AwarenessContext v3.1.5 — Contexto compartilhado entre engines.

Centraliza dependências que todos os engines precisam, eliminando imports diretos
de sqlite3, time.time() e AwarenessCache dos engines.

Nenhum engine conhece outro engine, a facade, ou implementações concretas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from iaglobal.cognition.awareness.time_provider import ClockProvider
from iaglobal.cognition.awareness.storage_backend import PersistenceBackend

if TYPE_CHECKING:
    from asyncio import Lock


@runtime_checkable
class EventBus(Protocol):
    """Interface mínima para publicação de eventos no barramento."""

    async def emit(self, event: str, payload: object) -> None:
        """Publica evento com payload. Fire-and-forget, nunca bloqueia."""
        ...


@runtime_checkable
class MetricsCollector(Protocol):
    """Interface para coleta de métricas de observabilidade."""

    def record(
        self, name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """Registra métrica.Implementações podem ser no-ops em testes."""
        ...


class NullEventBus:
    """EventBus no-op — não emite eventos."""

    async def emit(self, event: str, payload: object) -> None:
        return None


class NullMetrics:
    """MetricsCollector no-op — não registra métricas."""

    def record(
        self, name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        return None


class AwarenessContext:
    """
    Contexto injetado em todos os engines.

    Nenhum engine importa sqlite3, time.time(), AwarenessCache ou outro engine.
    Todos os acessos a dados passam por:
    - repository (StorageRepository) — operações semânticas (sem SQL cru)
    - clock (ClockProvider) — tempo determinístico
    - event_bus (EventBus) — notificações externas
    - metrics (MetricsCollector) — observabilidade
    - lock (asyncio.Lock) — concorrência (mediado pela facade)
    """

    def __init__(
        self,
        repository: "StorageRepository",
        clock: ClockProvider,
        lock: "Lock",
        event_bus: EventBus | None = None,
        metrics: MetricsCollector | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.lock = lock
        self.event_bus = event_bus
        self.metrics = metrics
