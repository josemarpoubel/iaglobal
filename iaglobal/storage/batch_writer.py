# iaglobal/storage/batch_writer.py

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path
from queue import Queue, Empty

from iaglobal._paths import CORE_DB
from iaglobal.utils.logger import logger


@dataclass
class Event:
    event_type: str
    payload: str
    task_fingerprint: str = ""
    model: str = ""
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    critical: bool = False
    timestamp: float = field(default_factory=time.time)


class BatchWriter:
    """Thread assíncrona que grava eventos em lote no SQLite.

    Política de flush:
    - Crítico → flush imediato
    - Não crítico → batch delay configurável (default 2000ms)
    - Máximo de 100 eventos por lote
    """

    def __init__(self, db_path: Optional[Path] = None, flush_ms: int = 2000, max_batch: int = 100):
        self.db_path = db_path or CORE_DB
        self.flush_ms = flush_ms
        self.max_batch = max_batch
        self._queue: Queue = Queue()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._stats = {"written": 0, "batches": 0, "errors": 0}
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp INTEGER NOT NULL,
                        task_fingerprint TEXT NOT NULL DEFAULT '',
                        event_type TEXT NOT NULL,
                        payload TEXT NOT NULL DEFAULT '',
                        model TEXT NOT NULL DEFAULT '',
                        latency_ms REAL NOT NULL DEFAULT 0,
                        tokens_in INTEGER NOT NULL DEFAULT 0,
                        tokens_out INTEGER NOT NULL DEFAULT 0
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS decisions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id INTEGER NOT NULL,
                        decision_type TEXT NOT NULL,
                        reason TEXT NOT NULL DEFAULT '',
                        actor TEXT NOT NULL DEFAULT '',
                        FOREIGN KEY (event_id) REFERENCES events(id)
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_events_fingerprint ON events(task_fingerprint)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
        except sqlite3.Error as e:
            logger.error(f"[BATCH_WRITER] Erro ao criar tabelas: {e}")
        finally:
            conn.close()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="batch-writer")
        self._thread.start()
        logger.info(f"[BATCH_WRITER] Iniciado: flush_ms={self.flush_ms} max_batch={self.max_batch}")

    def stop(self, timeout: float = 5.0):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        logger.info(f"[BATCH_WRITER] Parado: {self._stats}")

    def emit(self, event: Event):
        """Enfileira um evento para gravação assíncrona."""
        self._queue.put(event)

    def emit_sync(self, event: Event):
        """Grava um evento imediatamente (síncrono). Para eventos críticos."""
        self._write_batch([event])

    def _loop(self):
        buffer: List[Event] = []
        last_flush = time.time()

        while not self._stop_event.is_set():
            remain = self.flush_ms / 1000
            try:
                event = self._queue.get(timeout=min(remain, 1.0))
                buffer.append(event)
            except Empty:
                pass

            now = time.time()
            elapsed_ms = (now - last_flush) * 1000
            should_flush = (
                any(e.critical for e in buffer)
                or elapsed_ms >= self.flush_ms
                or len(buffer) >= self.max_batch
            )

            if buffer and should_flush:
                self._write_batch(buffer)
                self._stats["batches"] += 1
                self._stats["written"] += len(buffer)
                buffer.clear()
                last_flush = now

        # Flush remaining on shutdown
        if buffer:
            self._write_batch(buffer)
            self._stats["batches"] += 1
            self._stats["written"] += len(buffer)

    def _write_batch(self, events: List[Event]):
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                for e in events:
                    conn.execute(
                        """INSERT INTO events
                           (timestamp, task_fingerprint, event_type, payload, model, latency_ms, tokens_in, tokens_out)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            int(e.timestamp),
                            e.task_fingerprint,
                            e.event_type,
                            e.payload[:10000],
                            e.model,
                            e.latency_ms,
                            e.tokens_in,
                            e.tokens_out,
                        )
                    )
        except sqlite3.Error as exc:
            self._stats["errors"] += 1
            logger.error(f"[BATCH_WRITER] Erro ao gravar lote ({len(events)} eventos): {exc}")
        finally:
            conn.close()

    def query(self, event_type: Optional[str] = None, fingerprint: Optional[str] = None,
              limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conditions = []
            params: List[Any] = []
            if event_type:
                conditions.append("event_type = ?")
                params.append(event_type)
            if fingerprint:
                conditions.append("task_fingerprint = ?")
                params.append(fingerprint)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            cursor = conn.execute(
                f"SELECT id, timestamp, task_fingerprint, event_type, payload, model, "
                f"latency_ms, tokens_in, tokens_out FROM events {where} "
                f"ORDER BY id DESC LIMIT ? OFFSET ?",
                params + [limit, offset]
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0], "timestamp": r[1], "task_fingerprint": r[2],
                    "event_type": r[3], "payload": r[4], "model": r[5],
                    "latency_ms": r[6], "tokens_in": r[7], "tokens_out": r[8],
                }
                for r in rows
            ]
        except sqlite3.Error as e:
            logger.error(f"[BATCH_WRITER] Erro ao consultar eventos: {e}")
            return []
        finally:
            conn.close()

    def count(self, event_type: Optional[str] = None) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            if event_type:
                cursor = conn.execute("SELECT COUNT(*) FROM events WHERE event_type = ?", (event_type,))
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM events")
            row = cursor.fetchone()
            return row[0] if row else 0
        except sqlite3.Error:
            return 0
        finally:
            conn.close()

    def stats(self) -> Dict[str, int]:
        return {**self._stats, "queue_size": self._queue.qsize()}


# Instância global singleton
batch_writer = BatchWriter()
