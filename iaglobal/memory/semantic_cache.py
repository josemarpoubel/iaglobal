"""SemanticCache — Cache semântico inteligente.

Usa embeddings + similaridade de cosseno para encontrar cache hits
mesmo com perguntas reescritas. Não depende de hash exato.

Camadas:
- L1: RAM dict (embedding → response) para acesso rápido
- L2: SQLite persistente para durability
"""

import sqlite3
import json
import time
import hashlib
import struct
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime, timezone

from iaglobal._paths import CORE_DB, get_db_connection as _norm_path
from iaglobal.utils.logger import logger


class SemanticCache:
    """Cache semântico com similaridade de cosseno.

    Args:
        db_path: Caminho do SQLite (default: CORE_DB)
        threshold: Similaridade mínima para cache hit (0.0 a 1.0)
        max_results: Máximo de resultados para considerar
        ttl_seconds: Tempo de vida dos entries em segundos (None = eterno)
    """

    def __init__(
        self,
        db_path: str = CORE_DB,
        threshold: float = 0.92,
        max_results: int = 5,
        ttl_seconds: Optional[int] = 86400,
    ):
        p = Path(db_path) if isinstance(db_path, str) else db_path
        self.db_path = _norm_path(p)
        self.threshold = threshold
        self.max_results = max_results
        self.ttl_seconds = ttl_seconds
        self._ram: Dict[str, Dict] = {}
        self._ram_embeddings: Dict[str, list] = {}
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS semantic_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT UNIQUE,
                    query_text TEXT NOT NULL,
                    response TEXT NOT NULL,
                    embedding BLOB,
                    model TEXT DEFAULT 'all-MiniLM-L6-v2',
                    score REAL DEFAULT 0.0,
                    access_count INTEGER DEFAULT 1,
                    created_at TIMESTAMP,
                    last_access TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sem_cache_hash ON semantic_cache(query_hash)
            """)
            conn.commit()
        finally:
            conn.close()

    def get(self, query: str) -> Optional[str]:
        """Busca response no cache semântico. Retorna None se não achar."""
        start = time.time()
        qvec = self._embed(query)

        # 1. RAM L1 check (full scan nos embeddings em RAM)
        best_score = 0.0
        best_key = None
        for key, emb in self._ram_embeddings.items():
            score = sum(a * b for a, b in zip(qvec, emb))
            if score > best_score:
                best_score = score
                best_key = key

        if best_key and best_score >= self.threshold:
            entry = self._ram.get(best_key)
            if entry:
                if self._is_expired(entry):
                    logger.debug(f"[SEM-CACHE] RAM entry expired: {best_key[:40]}...")
                    del self._ram[best_key]
                    del self._ram_embeddings[best_key]
                else:
                    self._update_access(best_key)
                    elapsed = time.time() - start
                    logger.info(f"[SEM-CACHE] RAM HIT: score={best_score:.3f} "
                                f"query={query[:40]}... elapsed={elapsed:.3f}s")
                    return entry["response"]

        # 2. SQLite L2 check
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT query_text, response, embedding, created_at, access_count, id FROM semantic_cache"
            ).fetchall()
        except sqlite3.OperationalError:
            logger.warning("[SEM-CACHE] L2 query failed (OperationalError)")
            return None
        finally:
            conn.close()

        best_l2_score = 0.0
        best_l2 = None
        for qtext, resp, emb_blob, created, acc, cid in rows:
            if not emb_blob:
                continue
            v = list(struct.unpack(f'{len(emb_blob)//4}f', emb_blob))
            if len(v) != len(qvec):
                logger.debug(f"[SEM-CACHE] Shape mismatch: expected {len(v)}, got {len(qvec)}")
                continue
            score = sum(a * b for a, b in zip(qvec, v))
            if score > best_l2_score:
                best_l2_score = score
                best_l2 = (qtext, resp, emb_blob, created, acc, cid)

        if best_l2 and best_l2_score >= self.threshold:
            qtext, resp, emb_blob, created, acc, cid = best_l2
            if self._is_expired({"created_at": created}):
                logger.debug(f"[SEM-CACHE] L2 entry expired: {qtext[:40]}... (age > TTL)")
                self._delete_entry(cid)
                return None
            # Populate L1
            key = f"sem:{qtext}"
            self._ram[key] = {"response": resp, "created_at": created}
            self._ram_embeddings[key] = list(struct.unpack(f'{len(emb_blob)//4}f', emb_blob))
            self._update_access_sql(cid)
            elapsed = time.time() - start
            logger.info(f"[SEM-CACHE] L2 HIT: score={best_l2_score:.3f} "
                        f"query={query[:40]}... match={qtext[:40]}... elapsed={elapsed:.3f}s")
            return resp

        elapsed = time.time() - start
        logger.debug(f"[SEM-CACHE] MISS: query={query[:40]}... "
                     f"best_ram={best_score:.3f} best_l2={best_l2_score:.3f} elapsed={elapsed:.3f}s")
        return None

    def set(self, query: str, response: str, score: float = 0.0):
        """Armazena query+response no cache semântico."""
        start = time.time()
        qvec = self._embed(query)
        key = f"sem:{query}"
        now = datetime.now(timezone.utc).isoformat()

        self._ram[key] = {"response": response, "created_at": now}
        self._ram_embeddings[key] = qvec

        qhash = hashlib.sha256(query.encode()).hexdigest()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO semantic_cache
                (query_hash, query_text, response, embedding, score, created_at, last_access)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (qhash, query, response, struct.pack(f'{len(qvec)}f', *qvec), score, now, now))
            conn.commit()
        finally:
            conn.close()
        elapsed = time.time() - start
        logger.info(f"[SEM-CACHE] STORED: query={query[:40]}... "
                    f"response_len={len(response)} elapsed={elapsed:.3f}s")

    def clear(self):
        """Limpa cache (RAM + SQLite)."""
        ram_count = len(self._ram)
        self._ram.clear()
        self._ram_embeddings.clear()
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute("DELETE FROM semantic_cache")
            deleted = cur.rowcount
            conn.commit()
        finally:
            conn.close()
        logger.info(f"[SEM-CACHE] CLEAR: {ram_count} RAM + {deleted} SQLite entries removidos")

    def get_stats(self) -> Dict:
        """Estatísticas do cache."""
        conn = sqlite3.connect(self.db_path)
        try:
            total = conn.execute("SELECT COUNT(*) FROM semantic_cache").fetchone()[0]
            total_access = conn.execute(
                "SELECT COALESCE(SUM(access_count), 0) FROM semantic_cache"
            ).fetchone()[0]
            expired = conn.execute(
                "SELECT COUNT(*) FROM semantic_cache WHERE "
                "datetime(last_access, '+' || ? || ' seconds') < datetime('now')",
                (str(self.ttl_seconds or 86400),)
            ).fetchone()[0] if self.ttl_seconds else 0
            stats = {
                "entries": total,
                "total_access": total_access,
                "ram_entries": len(self._ram),
                "threshold": self.threshold,
                "ttl_seconds": self.ttl_seconds,
                "expired_entries": expired,
            }
            logger.debug(f"[SEM-CACHE] Stats: {json.dumps(stats)}")
            return stats
        finally:
            conn.close()

    def _embed(self, text: str) -> list:
        """Gera embedding para o texto."""
        from iaglobal.memory.memory_vector import _get_model
        return list(_get_model().embed(text))[0]

    def _is_expired(self, entry: Dict) -> bool:
        if self.ttl_seconds is None:
            return False
        created = entry.get("created_at")
        if not created:
            return False
        try:
            if isinstance(created, str):
                dt = datetime.fromisoformat(created)
            else:
                dt = created
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - dt).total_seconds()
            return age > self.ttl_seconds
        except Exception:
            return False

    def _update_access(self, key: str):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE semantic_cache SET access_count = access_count + 1, last_access = ? WHERE query_hash = ?",
                (datetime.now(timezone.utc).isoformat(), key)
            )
            conn.commit()
        finally:
            conn.close()

    def _update_access_sql(self, cid: int):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE semantic_cache SET access_count = access_count + 1, last_access = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), cid)
            )
            conn.commit()
        finally:
            conn.close()

    def _delete_entry(self, cid: int):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM semantic_cache WHERE id = ?", (cid,))
            conn.commit()
        finally:
            conn.close()

    def prune_old_embeddings(self, max_age_days: int = 30) -> Dict[str, Any]:
        from iaglobal.recycling.embedding_pruner import EmbeddingPruner
        pruner = EmbeddingPruner(max_age_days=max_age_days)
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT id, query_text, last_access, created_at FROM semantic_cache"
            ).fetchall()
        except sqlite3.OperationalError:
            return {"archived": 0, "error": "OperationalError"}
        finally:
            conn.close()

        embeddings = []
        mapping = {}
        for row_id, qtext, last_access, created_at in rows:
            try:
                ts = datetime.fromisoformat(last_access).timestamp() if last_access else 0
            except Exception:
                ts = 0
            emb = {"id": row_id, "text": qtext, "last_access": ts, "timestamp": ts}
            embeddings.append(emb)
            mapping[row_id] = emb

        result = pruner.prune(embeddings)
        if result["archived"] > 0:
            archived_ids = [e["id"] for e in result.get("archived_entries", []) if e.get("id")]
            if archived_ids:
                conn = sqlite3.connect(self.db_path)
                try:
                    placeholders = ",".join("?" for _ in archived_ids)
                    conn.execute(f"DELETE FROM semantic_cache WHERE id IN ({placeholders})", archived_ids)
                    conn.commit()
                finally:
                    conn.close()
                logger.info("[SEM-CACHE] Pruned %d old embeddings (max_age=%d days)",
                           len(archived_ids), max_age_days)
        return result
