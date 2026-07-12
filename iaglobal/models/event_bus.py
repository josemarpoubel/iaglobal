# iaglobal/models/event_bus.py

import uuid
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Any, Optional

__all__ = ["bus", "EventType"]

logger = logging.getLogger("ia-global")


# =========================================================
# EVENT MODEL (CANÔNICO)
# =========================================================

@dataclass
class Event:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = ""

    def __str__(self) -> str:
        return f"[{self.type}] src={self.source} data={self.data}"


# =========================================================
# EVENT TYPES (canonical source: iaglobal/events/event_types.py)
# =========================================================

from iaglobal.events.event_types import EventType  # noqa: F401


# =========================================================
# EVENT BUS (SINGLETON + THREAD SAFE)
# =========================================================

class EventBus:
    """
    Sistema nervoso central do Orchestrator V4.
    - Pub/Sub real
    - Singleton seguro
    - Histórico de eventos
    - Thread-safe
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._listeners = {}
                    cls._instance._history = []
                    cls._instance._max_history = 500
        return cls._instance

    # =========================================================
    # SUBSCRIPTION
    # =========================================================

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        if event_type in self._listeners:
            self._listeners[event_type] = [
                h for h in self._listeners[event_type] if h is not handler
            ]

    # =========================================================
    # PUBLISH
    # =========================================================

    def publish(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        source: str = ""
    ) -> Event:

        event = Event(
            type=event_type,
            data=data or {},
            source=source
        )

        # store history (bounded)
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        logger.info(f"[EVENT] {event}")

        # dispatch safely
        for handler in self._listeners.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"[EVENT ERROR] {event_type}: {e}")

        return event

    # =========================================================
    # HISTORY
    # =========================================================

    def history(
        self,
        event_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Event]:

        if event_type:
            filtered = [e for e in self._history if e.type == event_type]
            return filtered[-limit:]
        return self._history[-limit:]

    # =========================================================
    # RESET
    # =========================================================

    def reset(self) -> None:
        self._listeners.clear()
        self._history.clear()


# =========================================================
# GLOBAL BUS INSTANCE
# =========================================================

bus = EventBus()


# =========================================================
# DEFAULT TRACING LAYER (DEBUG MODE)
# =========================================================

def _tracing_handler(event: Event) -> None:
    logger.debug(f"[TRACE] {event}")


# auto-attach tracing for all events
for et in EventType.ALL:
    bus.subscribe(et, _tracing_handler)

# Injetado automaticamente para resolver assinaturas ausentes
class EventType:
    GENERIC = "generic"
    # Eventos do ciclo de reflexão (reflexion_engine)
    REFLECTION_COMPLETED = "reflection_completed"
    EXECUTION_FAILED = "execution_failed"
    MEMORY_SAVED = "memory_saved"
