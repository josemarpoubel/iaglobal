"""Long-term memory storage with semantic search, importance ranking, and consolidation."""

import sqlite3
import cbor2
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from collections import Counter


class LongTermMemory:
    """Stores important information for long-term retrieval with scoring."""

    def __init__(self, max_size: int = 1000, db_path: Optional[Path] = None):
        self.max_size = max_size
        self._memories: List[Dict] = []
        self.db_path = db_path
        self._lock = threading.Lock()
        if self.db_path:
            self._init_db()
            self._load()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ltm_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data BLOB,
                    created_at TEXT,
                    last_accessed TEXT
                )
            """)
            conn.commit()

    def store(self, content: str, metadata: Optional[Dict] = None, source: str = "internal") -> None:
        memory = {
            "id": len(self._memories),
            "content": content,
            "metadata": metadata or {},
            "source": source,
            "importance": 0.5,
            "usage_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_accessed": datetime.now(timezone.utc).isoformat()
        }
        self._memories.append(memory)
        if len(self._memories) > self.max_size:
            self._prune()
        self._save_entry(memory)

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        query_lower = query.lower()
        results = []
        for m in self._memories:
            score = self._match_score(m["content"], query_lower)
            adjusted = score * (0.5 + 0.5 * m["importance"])
            if adjusted > 0:
                results.append((adjusted, m))

        results.sort(key=lambda x: x[0], reverse=True)
        top = results[:top_k]

        for _, m in top:
            m["usage_count"] += 1
            m["last_accessed"] = datetime.now(timezone.utc).isoformat()

        if top and self.db_path:
            self._update_access(top)
        return [m for _, m in top]

    def consolidate(self, new_content: str, metadata: Optional[Dict] = None) -> bool:
        for m in self._memories:
            sim = self._match_score(m["content"], new_content.lower())
            if sim > 0.7:
                m["content"] = f"{m['content']}\n---\n{new_content}"
                m["importance"] = min(1.0, m["importance"] + 0.1)
                m["last_accessed"] = datetime.now(timezone.utc).isoformat()
                if metadata:
                    m["metadata"].update(metadata)
                if self.db_path:
                    self._update_entry(m)
                return True
        self.store(new_content, metadata)
        return False

    def get_stats(self) -> Dict:
        if not self._memories:
            return {"count": 0, "avg_importance": 0, "top_sources": []}
        avg_imp = sum(m["importance"] for m in self._memories) / len(self._memories)
        sources = Counter(m["source"] for m in self._memories)
        total = sum(m["usage_count"] for m in self._memories)
        return {
            "count": len(self._memories),
            "avg_importance": round(avg_imp, 3),
            "top_sources": sources.most_common(5),
            "total_usage": total
        }

    def get_all(self) -> List[Dict]:
        return list(self._memories)

    def clear(self) -> None:
        self._memories.clear()
        if self.db_path:
            with self._lock:
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    conn.execute("DELETE FROM ltm_entries")
                    conn.commit()

    def _match_score(self, content: str, query: str) -> float:
        if not query or not content:
            return 0.0
        content_lower = content.lower()
        words = query.split()
        if not words:
            return 0.0
        matches = sum(1 for w in words if w in content_lower)
        return matches / len(words) if words else 0.0

    def _prune(self) -> None:
        self._memories.sort(key=lambda m: (m["importance"], m["usage_count"]))
        keep = self._memories[-(self.max_size // 2):]
        keep_ids = {id(m) for m in keep}
        removed = [m for m in self._memories if id(m) not in keep_ids]
        self._memories = keep
        if removed and self.db_path:
            self._sync_db()

    def _save_entry(self, memory: dict) -> None:
        if not self.db_path:
            return
        with self._lock:
            try:
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    conn.execute(
                        "INSERT INTO ltm_entries (data, created_at, last_accessed) VALUES (?, ?, ?)",
                        (cbor2.dumps(memory), memory["created_at"], memory["last_accessed"])
                    )
                    conn.commit()
            except Exception:
                pass

    def _update_entry(self, memory: dict) -> None:
        with self._lock:
            try:
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    conn.execute(
                        "UPDATE ltm_entries SET data=?, last_accessed=? WHERE id=?",
                        (cbor2.dumps(memory), memory["last_accessed"], memory.get("db_id"))
                    )
                    conn.commit()
            except Exception:
                pass

    def _update_access(self, top: List) -> None:
        with self._lock:
            try:
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    now = datetime.now(timezone.utc).isoformat()
                    for _, m in top:
                        conn.execute(
                            "UPDATE ltm_entries SET data=?, last_accessed=? WHERE id=?",
                            (cbor2.dumps(m), now, m.get("db_id"))
                        )
                    conn.commit()
            except Exception:
                pass

    def _sync_db(self) -> None:
        if not self.db_path:
            return
        with self._lock:
            try:
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    conn.execute("DELETE FROM ltm_entries")
                    for m in self._memories:
                        conn.execute(
                            "INSERT INTO ltm_entries (data, created_at, last_accessed) VALUES (?, ?, ?)",
                            (cbor2.dumps(m), m["created_at"], m["last_accessed"])
                        )
                    conn.commit()
            except Exception:
                pass

    def _load(self) -> None:
        if not self.db_path or not self.db_path.exists():
            return
        with self._lock:
            try:
                with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                    cursor = conn.execute(
                        "SELECT id, data FROM ltm_entries ORDER BY id ASC"
                    )
                    rows = cursor.fetchall()
                self._memories.clear()
                for db_id, blob in rows:
                    memory = cbor2.loads(blob)
                    memory["db_id"] = db_id
                    self._memories.append(memory)
                if len(self._memories) > self.max_size:
                    self._prune()
            except Exception:
                pass
