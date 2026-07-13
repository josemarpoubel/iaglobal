"""Short-term memory for immediate context and conversation history."""

import sqlite3
import cbor2
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import deque
from datetime import datetime, timezone

from iaglobal._paths import MEMORY_SWAP_DIR


def _get_memory_percent() -> float:
    """Get system memory usage percentage."""
    try:
        with open("/proc/meminfo", "r") as f:
            meminfo = f.read()
        available = total = 0
        for line in meminfo.split("\n"):
            if line.startswith("MemAvailable:"):
                available = int(line.split()[1])
            elif line.startswith("MemTotal:"):
                total = int(line.split()[1])
        if total > 0:
            return (total - available) / total * 100
    except Exception:
        pass
    return 0.0


class ShortTermMemory:
    """Manages short-term memory with limited capacity and auto-expire."""

    MAX_SWAP_SIZE_MB = 500
    _USED_SWAP_SIZE = 0
    RAM_THRESHOLD_PERCENT = 50

    def __init__(
        self,
        max_size: int = 100,
        ttl_seconds: Optional[int] = 3600,
        db_path: Optional[Path] = None,
    ):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.db_path = db_path
        self._lock = threading.Lock()
        self._buffer: deque = deque(maxlen=max_size)
        self._timestamps: deque = deque(maxlen=max_size)
        self._swap_dir = MEMORY_SWAP_DIR
        self._swap_dir.mkdir(parents=True, exist_ok=True)
        self._swap_index: Dict[int, Path] = {}
        self._swap_seq = 0
        if self.db_path:
            self._init_db()
            self._load()

    def _should_swap_to_disk(self, content: Any) -> bool:
        ram_percent = _get_memory_percent()
        if ram_percent > self.RAM_THRESHOLD_PERCENT:
            return True
        if not self.is_full():
            return False
        estimated_size = len(str(content).encode("utf-8"))
        return estimated_size > 1000

    def _swap_to_disk(self, entry: dict) -> None:
        self._swap_seq += 1
        swap_file = self._swap_dir / f"stm_{self._swap_seq}.cbor2"
        try:
            swap_file.write_bytes(cbor2.dumps(entry))
            entry_size = swap_file.stat().st_size
            ShortTermMemory._USED_SWAP_SIZE += entry_size
            self._swap_index[id(entry)] = swap_file
        except Exception:
            pass

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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._buffer.append(entry)
        self._timestamps.append(datetime.now(timezone.utc))
        if self._should_swap_to_disk(item):
            self._swap_to_disk(entry)
        self._save_entry(entry)

    def get_recent(self, n: int = 10) -> List[Any]:
        self._expire()
        return [entry["content"] for entry in list(self._buffer)[-n:]]

    def get_recent_with_metadata(self, n: int = 10) -> List[Dict]:
        self._expire()
        return list(self._buffer)[-n:]

    def get_all_with_metadata(self) -> List[Dict]:
        """Retorna todos os itens com metadata."""
        self._expire()
        return list(self._buffer)

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
        while (
            self._timestamps
            and (now - self._timestamps[0]).total_seconds() > self.ttl_seconds
        ):
            self._timestamps.popleft()
            self._buffer.popleft()
            expired = True
        if expired and self.db_path:
            with self._lock:
                try:
                    with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                        conn.execute(
                            """
                            DELETE FROM stm_entries
                            WHERE datetime(created_at) < datetime('now', ?)
                        """,
                            (f"-{self.ttl_seconds} seconds",),
                        )
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
                        (cbor2.dumps(entry), entry["timestamp"]),
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
                        (self.max_size,),
                    )
                    rows = cursor.fetchall()
                self._buffer.clear()
                self._timestamps.clear()
                for row in reversed(rows):
                    entry = cbor2.loads(row[0])
                    self._buffer.append(entry)
                    ts = (
                        datetime.fromisoformat(entry["timestamp"])
                        if "timestamp" in entry
                        else datetime.now(timezone.utc)
                    )
                    self._timestamps.append(ts)
            except Exception:
                pass

    def clear_swap(self) -> int:
        removed = 0
        with self._lock:
            for f in self._swap_dir.glob("stm_*.cbor2"):
                try:
                    f.unlink()
                    removed += 1
                except Exception:
                    pass
            ShortTermMemory._USED_SWAP_SIZE = 0
            self._swap_index.clear()
            self._swap_seq = 0
        return removed

    def swap_status(self) -> Dict[str, Any]:
        total_files = len(list(self._swap_dir.glob("stm_*.cbor2")))
        total_kb = (
            sum(f.stat().st_size for f in self._swap_dir.glob("stm_*.cbor2")) / 1024
        )
        return {
            "files": total_files,
            "size_kb": round(total_kb, 1),
            "max_size_mb": self.MAX_SWAP_SIZE_MB,
            "used_size_bytes": ShortTermMemory._USED_SWAP_SIZE,
            "ram_threshold_percent": self.RAM_THRESHOLD_PERCENT,
        }
