"""Short-term memory for immediate context and conversation history."""

import sqlite3
import cbor2
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import deque
from datetime import datetime, timezone


class ShortTermMemory:
    """Manages short-term memory with limited capacity and auto-expire."""

    def __init__(self, max_size: int = 100, ttl_seconds: Optional[int] = 3600, db_path: Optional[Path] = None):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.db_path = db_path
        self._lock = threading.Lock()
        self._buffer: deque = deque(maxlen=max_size)
        self._timestamps: deque = deque(maxlen=max_size)
        if self.db_path:
            self._init_db()
            self._load()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stm_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data BLOB,
                    created_at TEXT
                )
            """)
            conn.commit()

    def add(self, item: Any, metadata: Optional[Dict] = None) -> None:
        entry = {
            "content": item,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self._buffer.append(entry)
        self._timestamps.append(datetime.now(timezone.utc))
        self._save_entry(entry)

    def get_recent(self, n: int = 10) -> List[Any]:
        self._expire()
        return [entry["content"] for entry in list(self._buffer)[-n:]]

    def get_recent_with_metadata(self, n: int = 10) -> List[Dict]:
        self._expire()
        return list(self._buffer)[-n:]

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        self._expire()
        query_lower = query.lower()
        results = []
        for entry in self._buffer:
            if query_lower in entry["content"].lower():
                results.append(entry)
        return results[:top_k]

    def clear(self) -> None:
        self._buffer.clear()
        self._timestamps.clear()
        if self.db_path:
            with self._lock:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    conn.execute("DELETE FROM stm_entries")
                    conn.commit()

    def is_full(self) -> bool:
        return len(self._buffer) == self.max_size

    def count(self) -> int:
        return len(self._buffer)

    def _expire(self) -> None:
        now = datetime.now(timezone.utc)
        expired = False
        while self._timestamps and (now - self._timestamps[0]).total_seconds() > self.ttl_seconds:
            self._timestamps.popleft()
            self._buffer.popleft()
            expired = True
        if expired and self.db_path:
            with self._lock:
                try:
                    with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                        conn.execute("""
                            DELETE FROM stm_entries
                            WHERE datetime(created_at) < datetime('now', ?)
                        """, (f"-{self.ttl_seconds} seconds",))
                        conn.commit()
                except Exception:
                    pass

    def _save_entry(self, entry: dict) -> None:
        if not self.db_path:
            return
        with self._lock:
            try:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    conn.execute(
                        "INSERT INTO stm_entries (data, created_at) VALUES (?, ?)",
                        (cbor2.dumps(entry), entry["timestamp"])
                    )
                    conn.commit()
            except Exception:
                pass

    def _load(self) -> None:
        if not self.db_path or not self.db_path.exists():
            return
        with self._lock:
            try:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    cursor = conn.execute(
                        "SELECT data FROM stm_entries ORDER BY id DESC LIMIT ?",
                        (self.max_size,)
                    )
                    rows = cursor.fetchall()
                self._buffer.clear()
                self._timestamps.clear()
                for row in reversed(rows):
                    entry = cbor2.loads(row[0])
                    self._buffer.append(entry)
                    ts = datetime.fromisoformat(entry["timestamp"]) if "timestamp" in entry else datetime.now(timezone.utc)
                    self._timestamps.append(ts)
            except Exception:
                pass