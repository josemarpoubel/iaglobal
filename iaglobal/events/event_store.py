import json
import threading
from typing import Optional, Dict, Any, List

from iaglobal.memory.db_manager import db
from iaglobal.utils.logger import logger


class DecisionEventStore:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._subscribed = False
                    cls._instance._stats = {"inserted": 0, "failed": 0}
        return cls._instance

    def start(self):
        if self._subscribed:
            return
        from iaglobal.models.event_bus import bus, EventType
        bus.subscribe(EventType.PIPELINE_STAGE, self._on_pipeline_event)
        self._subscribed = True
        logger.info("📝 [DECISION_STORE] Auto-persist ativo (ouvindo PIPELINE_STAGE)")

    def stop(self):
        if not self._subscribed:
            return
        bus.unsubscribe(EventType.PIPELINE_STAGE, self._on_pipeline_event)
        self._subscribed = False

    def _on_pipeline_event(self, event):
        from iaglobal.models.event_bus import Event
        if not isinstance(event, Event):
            return
        data = event.data or {}
        decision = data.get("decision_event")
        step = data.get("step") or (decision.get("step") if isinstance(decision, dict) else "")

        if not decision or not step:
            return

        if isinstance(decision, dict):
            execution_id = decision.get("execution_id", "unknown")
            timestamp = decision.get("timestamp", "")
            event_json = json.dumps(decision, ensure_ascii=False, default=str)
        else:
            execution_id = getattr(decision, "execution_id", "unknown")
            timestamp = getattr(decision, "timestamp", "")
            event_json = json.dumps(decision.to_dict(), ensure_ascii=False, default=str)

        try:
            db.insert_decision_event(execution_id, step, timestamp, event_json)
            self._stats["inserted"] += 1
        except Exception as e:
            self._stats["failed"] += 1
            logger.error(f"❌ [DECISION_STORE] Falha ao persistir {step}/{execution_id}: {e}")

    def query(
        self,
        execution_id: Optional[str] = None,
        step: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return db.query_decision_events(
            execution_id=execution_id,
            step=step,
            limit=limit,
            offset=offset,
        )

    def count(
        self,
        execution_id: Optional[str] = None,
        step: Optional[str] = None,
    ) -> int:
        return db.count_decision_events(execution_id=execution_id, step=step)

    def replay(self, execution_id: str) -> List[Dict[str, Any]]:
        rows = db.query_decision_events(execution_id=execution_id, limit=1000)
        for row in rows:
            try:
                row["_parsed"] = json.loads(row["event_data"])
            except Exception:
                row["_parsed"] = None
        return rows

    def stats(self) -> Dict[str, int]:
        return dict(self._stats)


store = DecisionEventStore()
