# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Short-term memory for immediate context and conversation history."""

import os
import sqlite3
import cbor2
import threading
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import deque
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


def _process_rss_mb() -> int:
    """RSS do PROCESSO (VmRSS), nao a RAM total do sistema.

    O bug original media /proc/meminfo (RAM do sistema) e disparava em
    qualquer desktop ativo. Medir o proprio processo e o que interessa:
    decidir se ESTE processo deve liberar memoria.
    """
    try:
        with open(f"/proc/{os.getpid()}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 0


def _total_ram_mb() -> int:
    """RAM total do sistema em MB (usada so para calcular o threshold default)."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 8192


class ShortTermMemory:
    """Manages short-term memory with limited capacity and auto-expire.

    Persistencia via SQLite (stm_entries) e o unico armazenamento em disco:
    cada add() ja grava a entrada no banco. A memoria de curta duracao e
    mantida como deque bounded em RAM como cache de trabalho.

    Spill-to-disk correto (reimplementacao):
      - Mede o RSS do PROCESSO (nao do sistema).
      - Quando o RSS ultrapassa o threshold (env STM_SPILL_RSS_FRACTION,
        default 0.5 = 50% da RAM total, ou STM_SPILL_RSS_MB absoluto),
        o cache RAM e drenado: as entradas continuam seguras no SQLite,
        apenas saem da RAM.
      - Ao ler, se o cache foi drenado, re-le do SQLite (disco) sob demanda.
      - Quando o RSS volta abaixo do threshold, o cache RAM e re-hidratado
        do SQLite (hysteresis).
      - NENHUM arquivo .cbor2 e criado — o bug historico gravava cbor2
        orfaos que ninguem lia (50k arquivos / 202MB numa maquina).
    """

    def __init__(
        self,
        max_size: int = 100,
        ttl_seconds: Optional[int] = 3600,
        db_path: Optional[Path] = None,
        spill_enabled: Optional[bool] = None,
        spill_rss_threshold_mb: Optional[int] = None,
    ):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.db_path = db_path
        self._lock = threading.Lock()
        self._buffer: deque = deque(maxlen=max_size)
        self._timestamps: deque = deque(maxlen=max_size)
        if spill_enabled is None:
            spill_enabled = os.environ.get("STM_SPILL_ENABLED", "1") != "0"
        self._spill_enabled = spill_enabled
        if spill_rss_threshold_mb is None:
            abs_mb = os.environ.get("STM_SPILL_RSS_MB", "").strip()
            if abs_mb:
                spill_rss_threshold_mb = int(abs_mb)
            else:
                fraction = float(os.environ.get("STM_SPILL_RSS_FRACTION", "0.5"))
                spill_rss_threshold_mb = int(_total_ram_mb() * fraction)
        self._spill_threshold_mb = spill_rss_threshold_mb
        # True quando o cache RAM foi drenado por pressao de memoria
        self._spilled = False
        # Conta writes desde o ultimo trim do SQLite (limita o banco ao max_size)
        self._writes_since_trim = 0
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
                    created_at TEXT,
                    chave TEXT
                )
            """)
            cols = [row[1] for row in conn.execute("PRAGMA table_info(stm_entries)")]
            if "consolidated_at" not in cols:
                conn.execute("ALTER TABLE stm_entries ADD COLUMN consolidated_at TEXT")
            if "chave" not in cols:
                conn.execute("ALTER TABLE stm_entries ADD COLUMN chave TEXT")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_stm_entries_chave "
                    "ON stm_entries(chave)"
                )
            conn.commit()

    def add(self, item: Any, metadata: Optional[Dict] = None) -> None:
        entry = {
            "content": item,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._buffer.append(entry)
        self._timestamps.append(datetime.now(timezone.utc))
        self._save_entry(entry)
        self._trim_db_if_needed()
        self._maybe_spill()

    def get_recent(self, n: int = 10) -> List[Any]:
        self._expire()
        return [entry["content"] for entry in self._read_cached(n)]

    def get_recent_with_metadata(self, n: int = 10) -> List[Dict]:
        self._expire()
        return self._read_cached(n)

    def get_all_with_metadata(self) -> List[Dict]:
        self._expire()
        return self._read_cached(self.max_size)

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        self._expire()
        query_lower = query.lower()
        results = []
        for entry in self._read_cached(self.max_size):
            if query_lower in entry["content"].lower():
                results.append(entry)
        return results[:top_k]

    def clear(self) -> None:
        self._buffer.clear()
        self._timestamps.clear()
        self._spilled = False
        if self.db_path:
            with self._lock:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    conn.execute("DELETE FROM stm_entries")
                    conn.commit()

    def is_full(self) -> bool:
        return len(self._buffer) == self.max_size

    def count(self) -> int:
        return len(self._buffer)

    def spill_status(self) -> Dict[str, Any]:
        """Estado real do spill-to-disk (para observabilidade/IVM)."""
        return {
            "enabled": self._spill_enabled,
            "process_rss_mb": _process_rss_mb(),
            "threshold_mb": self._spill_threshold_mb,
            "spilled": self._spilled,
            "buffer_size": len(self._buffer),
            "max_size": self.max_size,
        }

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

    def _trim_db_if_needed(self) -> None:
        """Limita o SQLite às max_size entradas mais recentes.

        O deque RAM é bounded por maxlen, mas o SQLite acumulava tudo por
        TTL (24h no IVM) — centenas de milhares de snapshots de ~96KB em
        produção. Aqui, a cada `max_size` writes, apaga as entradas mais
        antigas além das max_size mais recentes, mantendo o banco delimitado.
        """
        if not self.db_path:
            return
        self._writes_since_trim += 1
        if self._writes_since_trim < self.max_size:
            return
        self._writes_since_trim = 0
        with self._lock:
            try:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    conn.execute(
                        """
                        DELETE FROM stm_entries
                        WHERE id NOT IN (
                            SELECT id FROM stm_entries
                            ORDER BY id DESC LIMIT ?
                        )
                    """,
                        (self.max_size,),
                    )
                    conn.commit()
            except Exception:
                pass

    def upsert(self, chave: str, item: Any, metadata: Optional[Dict] = None) -> None:
        """Persiste por chave: substitui a entrada anterior com a mesma chave.

        O IVM gravava um snapshot completo (~96KB) a cada atualização de
        métricas, criando um append infinito de duplicatas. Com upsert,
        cada chave (ex: ivm_axiom_historico) mantém apenas a versão mais
        recente — o que _carregar_estado já esperava (merge por chave).
        """
        entry = {
            "content": item,
            "metadata": {**(metadata or {}), "chave": chave},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self.db_path:
            with self._lock:
                try:
                    with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                        conn.execute(
                            "DELETE FROM stm_entries WHERE chave = ?",
                            (chave,),
                        )
                        conn.execute(
                            "INSERT INTO stm_entries (data, created_at, chave) VALUES (?, ?, ?)",
                            (cbor2.dumps(entry), entry["timestamp"], chave),
                        )
                        conn.commit()
                except Exception:
                    pass
        # Mantém apenas uma entrada com a chave no cache RAM
        pares = [
            (e, t)
            for e, t in zip(self._buffer, self._timestamps)
            if e.get("metadata", {}).get("chave") != chave
        ]
        self._buffer = deque((e for e, _ in pares), maxlen=self.max_size)
        self._timestamps = deque((t for _, t in pares), maxlen=self.max_size)
        self._buffer.append(entry)
        self._timestamps.append(datetime.now(timezone.utc))
        self._trim_db_if_needed()
        self._maybe_spill()

    def _save_entry(self, entry: dict) -> None:
        if not self.db_path:
            return
        chave = entry.get("metadata", {}).get("chave")
        with self._lock:
            try:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    conn.execute(
                        "INSERT INTO stm_entries (data, created_at, chave) VALUES (?, ?, ?)",
                        (cbor2.dumps(entry), entry["timestamp"], chave),
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

    # ------------------------------------------------------------------
    # Spill-to-disk correto
    # ------------------------------------------------------------------

    def _maybe_spill(self) -> None:
        """Drena o cache RAM quando o RSS do processo ultrapassa o threshold.

        As entradas ja estao no SQLite (gravadas no add), entao drenar a RAM
        e seguro: nada e perdido. Nenhum arquivo temporario e criado.
        """
        if not (self._spill_enabled and self.db_path):
            return
        if _process_rss_mb() <= self._spill_threshold_mb:
            return
        if not self._buffer:
            return
        self._spilled = True
        self._buffer.clear()
        self._timestamps.clear()
        logger.info(
            "[STM-SPILL] RSS=%dMB > threshold=%dMB — cache RAM drenado "
            "(dados seguros no SQLite); re-hidratacao sob demanda",
            _process_rss_mb(),
            self._spill_threshold_mb,
        )

    def _maybe_restore(self) -> None:
        """Re-hidrata o cache RAM do SQLite quando o RSS cai abaixo do threshold."""
        if not self._spilled:
            return
        if _process_rss_mb() > self._spill_threshold_mb:
            return
        self._load()
        self._spilled = False
        logger.info(
            "[STM-SPILL] RSS=%dMB < threshold=%dMB — cache RAM re-hidratado",
            _process_rss_mb(),
            self._spill_threshold_mb,
        )

    def _read_cached(self, n: int) -> List[Dict]:
        """Le do cache RAM, ou do SQLite (disco) se o cache foi drenado."""
        self._maybe_restore()
        if not self._spilled:
            return list(self._buffer)[-n:]
        if not self.db_path:
            return []
        with self._lock:
            try:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    cursor = conn.execute(
                        "SELECT data FROM stm_entries ORDER BY id DESC LIMIT ?",
                        (n,),
                    )
                    rows = cursor.fetchall()
                entries = []
                for row in reversed(rows):
                    try:
                        entries.append(cbor2.loads(row[0]))
                    except Exception:
                        continue
                return entries
            except Exception:
                return []
