# iaglobal/events/event_store.py

import os
import json
import asyncio
import sqlite3

from typing import Optional, Dict, Any, List
from iaglobal import _paths
from iaglobal.memory.db_manager import db
from iaglobal.utils.logger import logger

class DecisionEventStore:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # Proteção para garantir que o Singleton não sobrescreva o estado já inicializado
        if getattr(self, "_initialized", False):
            return
            
        self.conn = None
        self.db_path = None  # Inicialização explícita necessária para evitar AttributeError
        self._subscribed = False
        self._stats = {"inserted": 0, "failed": 0}
        self._initialized = True

    # iaglobal/events/event_store.py

    async def connect(self, db_path: str = None):
        """Conexão blindada: desconstrói e reconstrói o caminho se necessário."""
        
        # 1. Tenta pegar o caminho de várias fontes, garantindo que não seja None
        if not db_path:
            # Tenta pegar do _paths, se não existir ou for None, reconstrói na hora
            db_path = getattr(_paths, "CORE_DB", None)
            if db_path is None:
                # Caminho de fallback absoluto (evita o NoneType a todo custo)
                db_path = _paths.DATA_ROOT / "db" / "core.db"

        # 2. Garante que é uma string ou PathLike
        target_path = str(db_path)
        
        async with self._lock:
            if self.conn is None:
                self.db_path = target_path
                logger.debug("[DECISION_STORE] Conectando ao SQLite em: %s (Tipo: %s)", self.db_path, type(self.db_path))
                
                def _connect():
                    return sqlite3.connect(self.db_path)
                
                self.conn = await asyncio.to_thread(_connect)
                logger.debug("[DECISION_STORE] Conectado com sucesso.")

    def start(self):
        # FORÇA A BUSCA DO CAMINHO DIRETAMENTE NO MÓDULO _paths
        # Se _paths.CORE_DB for None, ele constrói o caminho manualmente como backup
        path_from_module = getattr(_paths, "CORE_DB", None)
        
        if path_from_module is None:
            # Fallback de segurança absoluto
            self.db_path = str(_paths.DATA_ROOT / "db" / "core.db")
        else:
            self.db_path = str(path_from_module)

        # Verifica se o caminho final é válido antes de passar pro sqlite3
        if not self.db_path or self.db_path == "None":
            raise ValueError("CRÍTICO: self.db_path não pôde ser definido corretamente.")

        logger.debug("[DECISION_STORE] Conectando no SQLite em: %s", self.db_path)
        self.conn = sqlite3.connect(self.db_path, timeout=30)

        # Inscreve-se no EventBus para persistir PIPELINE_STAGE events
        if not self._subscribed:
            from iaglobal.models.event_bus import bus, EventType
            bus.subscribe(EventType.PIPELINE_STAGE, self._on_pipeline_event)
            self._subscribed = True
            logger.info("[DECISION_STORE] Inscrito em PIPELINE_STAGE para persistência de eventos")

    def stop(self):
        if not self._subscribed:
            return
        from iaglobal.models.event_bus import bus, EventType
        bus.unsubscribe(EventType.PIPELINE_STAGE, self._on_pipeline_event)
        self._subscribed = False

    # Wrapper para lidar com eventos síncronos do barramento de forma assíncrona
    def _on_pipeline_event(self, event):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._on_pipeline_event_sync(event)
            return
        coro = self._async_handle_event(event)
        loop.create_task(coro)

    def _on_pipeline_event_sync(self, event):
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
        else:
            execution_id = getattr(decision, "execution_id", "unknown")
            timestamp = getattr(decision, "timestamp", "")
        event_json = json.dumps(decision if isinstance(decision, dict) else decision.to_dict(),
                                ensure_ascii=False, default=str)
        try:
            db.insert_decision_event(execution_id, step, timestamp, event_json)
            self._stats["inserted"] += 1
        except Exception:
            self._stats["failed"] += 1

    async def _async_handle_event(self, event):
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
            # Aguarda a operação de banco de dados
            await db.insert_decision_event(execution_id, step, timestamp, event_json)
            self._stats["inserted"] += 1
        except Exception as e:
            self._stats["failed"] += 1
            logger.error(f"❌ [DECISION_STORE] Falha ao persistir {step}/{execution_id}: {e}")

    def query(self, execution_id: Optional[str] = None, step: Optional[str] = None, 
              limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        return db.query_decision_events(execution_id=execution_id, step=step, limit=limit, offset=offset)

    def count(self, execution_id: Optional[str] = None, step: Optional[str] = None) -> int:
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
