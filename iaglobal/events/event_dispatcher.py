import threading
from typing import Callable, Dict, List, Optional, Any

from iaglobal.events.event_types import PipelineStep
from iaglobal.utils.logger import logger


class DecisionEventDispatcher:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._handlers: Dict[str, List[Callable]] = {}
                    cls._instance._subscribed = False
        return cls._instance

    def start(self):
        if self._subscribed:
            return
        from iaglobal.models.event_bus import bus, EventType
        bus.subscribe(EventType.PIPELINE_STAGE, self._route)
        self._subscribed = True
        logger.info("📬 [DISPATCHER] Roteamento de DecisionEvents ativo")

    def stop(self):
        if not self._subscribed:
            return
        from iaglobal.models.event_bus import bus, EventType
        bus.unsubscribe(EventType.PIPELINE_STAGE, self._route)
        self._subscribed = False

    def on(self, step: str, handler: Callable[[dict], None]):
        if step not in self._handlers:
            self._handlers[step] = []
        self._handlers[step].append(handler)

    def off(self, step: str, handler: Callable):
        if step in self._handlers:
            self._handlers[step] = [h for h in self._handlers[step] if h is not handler]

    def _route(self, event):
        from iaglobal.models.event_bus import Event
        if not isinstance(event, Event):
            return
        data = event.data or {}
        decision = data.get("decision_event")
        step = data.get("step") or (decision.get("step") if isinstance(decision, dict) else "")

        if not step or not decision:
            return

        if not isinstance(decision, dict):
            try:
                decision = decision.to_dict()
            except Exception:
                return

        for handler in self._handlers.get(step, []):
            try:
                handler(decision)
            except Exception as e:
                logger.error(f"❌ [DISPATCHER] Handler falhou para step={step}: {e}")

    def registered_steps(self) -> List[str]:
        return list(self._handlers.keys())

    def handler_count(self, step: str) -> int:
        return len(self._handlers.get(step, []))


dispatcher = DecisionEventDispatcher()
