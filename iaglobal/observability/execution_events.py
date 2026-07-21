# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ExecutionEvents — barramento leve de eventos de execução.

Desacopla a pipeline dos consumidores de observabilidade (relatórios, dashboards, etc).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ExecutionEvent:
    event_type: str
    execution_id: str
    node_id: str
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)


class ExecutionEventBus:
    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable[[ExecutionEvent], None]]] = {}

    def subscribe(
        self, event_type: str, callback: Callable[[ExecutionEvent], None]
    ) -> None:
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def emit(
        self, event_type: str, execution_id: str, node_id: str, **payload: Any
    ) -> None:
        event = ExecutionEvent(
            event_type=event_type,
            execution_id=execution_id,
            node_id=node_id,
            payload=payload,
        )
        for callback in self._listeners.get(event_type, []):
            try:
                callback(event)
            except Exception:
                pass  # Silencioso para não quebrar a pipeline


# Singleton global
_event_bus: Optional[ExecutionEventBus] = None


def get_event_bus() -> ExecutionEventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = ExecutionEventBus()
    return _event_bus


def emit(event_type: str, execution_id: str, node_id: str, **payload: Any) -> None:
    get_event_bus().emit(event_type, execution_id, node_id, **payload)


# Tipos de eventos padronizados
NODE_STARTED = "node_started"
NODE_FINISHED = "node_finished"
PROVIDER_SELECTED = "provider_selected"
FALLBACK = "fallback"
RETRY = "retry"
