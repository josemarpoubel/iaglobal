# iaglobal/memory/memory_storage.py

import sqlite3
import cbor2
import hashlib
import threading

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from iaglobal import _paths
from iaglobal.utils.logger import logger

class MemoryStorage:
    """Motor de armazenamento unificado usando o Core Database (thread-safe)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(_paths.CORE_DB, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_tables(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS success_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_hash TEXT UNIQUE,
                    data BLOB
                )
            """)
            conn.commit()

    @staticmethod
    def _get_task_hash(task: str) -> str:
        return hashlib.sha256(task.strip().lower().encode('utf-8')).hexdigest()

    def store(self, task: str, codigo: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        task_hash = self._get_task_hash(task)
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "task": task.strip(),
            "codigo": codigo.strip(),
            "metadata": metadata or {}
        }
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute("INSERT OR REPLACE INTO success_registry (task_hash, data) VALUES (?, ?)", 
                                 (task_hash, cbor2.dumps(data)))
                    conn.commit()
            except Exception as e:
                logger.error(f"💥 Falha ao salvar memória: {e}")

    def retrieve(self, task: str) -> Optional[Dict[str, Any]]:
        task_hash = self._get_task_hash(task)
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT data FROM success_registry WHERE task_hash = ?", (task_hash,))
                row = cursor.fetchone()
                return cbor2.loads(row[0]) if row else None

    def delete(self, task: str) -> None:
        task_hash = self._get_task_hash(task)
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM success_registry WHERE task_hash = ?", (task_hash,))
                    conn.commit()
            except Exception as e:
                logger.error(f"💥 Falha ao deletar memória: {e}")

# --- INSTÂNCIA ÚNICA ---
storage = MemoryStorage()

# --- FUNÇÕES PONTE (Legado - Mantém o sistema rodando enquanto refatoramos) ---
def store_success(task: str, codigo: str, metadata: Optional[Dict[str, Any]] = None):
    return storage.store(task, codigo, metadata)

def get_success_by_task(task: str):
    return storage.retrieve(task)

def get_task_hash(task: str) -> str:
    return MemoryStorage._get_task_hash(task)

def delete_success(task: str) -> None:
    return storage.delete(task)

def init_storage(clear: bool = False) -> None:
    if clear:
        with storage._lock:
            try:
                with storage._get_connection() as conn:
                    conn.execute("DELETE FROM success_registry")
                    conn.commit()
            except Exception:
                pass
    storage._init_tables()
