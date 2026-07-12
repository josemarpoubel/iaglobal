# iaglobal/storage/snapshotter.py

import uuid
import time
import json
import sqlite3
import cbor2
import inspect
import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path

from iaglobal._paths import CORE_DB, SNAPSHOTS_DIR
from iaglobal.utils.logger import logger


def make_checkpoint_safe(obj: Any) -> Any:
    """Converte objetos não serializáveis em representações seguras para checkpoint.
    
    Substitui corrotinas, tasks, funções assíncronas por metadados serializáveis.
    """
    if inspect.iscoroutine(obj):
        return {"__type__": "coroutine", "repr": repr(obj)}
    if inspect.iscoroutinefunction(obj):
        return {"__type__": "coroutine_function", "name": obj.__name__}
    if isinstance(obj, asyncio.Task):
        return {"__type__": "task", "id": id(obj), "name": obj.get_name()}
    if inspect.isasyncgen(obj):
        return {"__type__": "async_generator", "repr": repr(obj)}
    if inspect.isasyncgenfunction(obj):
        return {"__type__": "async_generator_function", "name": obj.__name__}
    
    if isinstance(obj, dict):
        return {k: make_checkpoint_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_checkpoint_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(make_checkpoint_safe(v) for v in obj)
    if isinstance(obj, set):
        return [make_checkpoint_safe(v) for v in obj]
    
    return obj


class Snapshotter:
    """Gerenciador de snapshots CBOR2 com índice SQLite.

    - Cria snapshots CBOR2 do SystemStateBuffer
    - Mantém índice SQLite (snapshot_id, timestamp, task_fingerprint)
    - Suporta rollback para último snapshot válido
    - Imutável: snapshots nunca são sobrescritos
    """

    def __init__(self, db_path: Optional[Path] = None, snapshots_dir: Optional[Path] = None):
        self.db_path = db_path or CORE_DB
        self.snapshots_dir = snapshots_dir or SNAPSHOTS_DIR
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._init_index()

    def _init_index(self):
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS snapshots (
                        snapshot_id TEXT PRIMARY KEY,
                        timestamp REAL NOT NULL,
                        task_fingerprint TEXT NOT NULL DEFAULT '',
                        schema_version INTEGER NOT NULL DEFAULT 1,
                        snapshot_path TEXT NOT NULL,
                        state_size INTEGER NOT NULL DEFAULT 0,
                        compressed_entries INTEGER NOT NULL DEFAULT 0
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_fp ON snapshots(task_fingerprint)")
        except sqlite3.Error as e:
            logger.error(f"[SNAPSHOTTER] Erro ao criar índice: {e}")
        finally:
            conn.close()

    def create_snapshot(self, state_data: Dict[str, Any]) -> Optional[str]:
        """Cria snapshot CBOR2 a partir dos dados de estado.

        Args:
            state_data: dados do estado (SystemStateBuffer.get_snapshot_data())

        Returns:
            snapshot_id (UUID) em caso de sucesso, None em falha.
        """
        snapshot_id = str(uuid.uuid4())
        timestamp = time.time()
        path = self.snapshots_dir / f"snapshot_{snapshot_id}.cbor2"

        safe_state_data = make_checkpoint_safe(state_data)

        snapshot = {
            "snapshot_id": snapshot_id,
            "timestamp": timestamp,
            "schema_version": 1,
            "state_data": safe_state_data,
        }

        try:
            with open(path, "wb") as f:
                cbor2.dump(snapshot, f)
        except Exception as e:
            logger.error(f"[SNAPSHOTTER] Erro ao escrever snapshot {snapshot_id}: {e}")
            return None

        nodes = state_data.get("nodes", {}) if isinstance(state_data, dict) else {}
        task_fingerprint = ""
        for key in nodes:
            task_fingerprint = key
            break

        self._record_index(snapshot_id, timestamp, task_fingerprint, str(path),
                           len(nodes), len(state_data.get("compressed", {})) if isinstance(state_data, dict) else 0)

        logger.info(f"[SNAPSHOTTER] Snapshot criado: {snapshot_id} "
                    f"({len(nodes)} nós, {path.name})")
        return snapshot_id

    def _record_index(self, snapshot_id: str, timestamp: float, task_fingerprint: str,
                      snapshot_path: str, state_size: int, compressed_entries: int):
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute(
                    """INSERT OR REPLACE INTO snapshots
                       (snapshot_id, timestamp, task_fingerprint, schema_version, snapshot_path, state_size, compressed_entries)
                       VALUES (?, ?, ?, 1, ?, ?, ?)""",
                    (snapshot_id, timestamp, task_fingerprint, snapshot_path, state_size, compressed_entries)
                )
        except sqlite3.Error as e:
            logger.error(f"[SNAPSHOTTER] Erro ao indexar snapshot {snapshot_id}: {e}")
        finally:
            conn.close()

    def load_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Carrega um snapshot pelo ID."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT snapshot_path FROM snapshots WHERE snapshot_id = ?",
                (snapshot_id,)
            )
            row = cursor.fetchone()
            if not row:
                logger.warning(f"[SNAPSHOTTER] Snapshot não encontrado: {snapshot_id}")
                return None
            path = Path(row[0])
        except sqlite3.Error as e:
            logger.error(f"[SNAPSHOTTER] Erro ao consultar snapshot {snapshot_id}: {e}")
            return None
        finally:
            conn.close()

        if not path.exists():
            logger.error(f"[SNAPSHOTTER] Arquivo de snapshot não existe: {path}")
            return None

        try:
            with open(path, "rb") as f:
                return cbor2.load(f)
        except Exception as e:
            logger.error(f"[SNAPSHOTTER] Erro ao ler snapshot {snapshot_id}: {e}")
            return None

    def get_latest_snapshot_id(self) -> Optional[str]:
        """Retorna o ID do snapshot mais recente."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT snapshot_id FROM snapshots ORDER BY timestamp DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except sqlite3.Error:
            return None
        finally:
            conn.close()

    def rollback(self, snapshot_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Rollback para snapshot especificado (ou último disponível).

        Returns:
            state_data para passar ao SystemStateBuffer.load_snapshot()
        """
        snap_id = snapshot_id or self.get_latest_snapshot_id()
        if not snap_id:
            logger.warning("[SNAPSHOTTER] Rollback impossível: nenhum snapshot disponível")
            return None

        data = self.load_snapshot(snap_id)
        if data is None:
            return None

        state_data = data.get("state_data", {})
        logger.info(f"[SNAPSHOTTER] Rollback para snapshot {snap_id}: "
                    f"{len(state_data.get('nodes', {}))} nós restaurados")
        return state_data

    def list_snapshots(self, limit: int = 20) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT snapshot_id, timestamp, task_fingerprint, state_size, compressed_entries "
                "FROM snapshots ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            return [
                {
                    "snapshot_id": r[0], "timestamp": r[1],
                    "task_fingerprint": r[2], "state_size": r[3],
                    "compressed_entries": r[4],
                }
                for r in cursor.fetchall()
            ]
        except sqlite3.Error:
            return []
        finally:
            conn.close()

    def prune_old_snapshots(self, keep_last: int = 50):
        """Remove snapshots antigos, mantendo apenas os `keep_last` mais recentes."""
        snapshots = self.list_snapshots(limit=keep_last + 1)
        if len(snapshots) <= keep_last:
            return

        to_remove = snapshots[keep_last:]
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                for snap in to_remove:
                    path = self.snapshots_dir / f"snapshot_{snap['snapshot_id']}.cbor2"
                    if path.exists():
                        path.unlink()
                        logger.debug(f"[SNAPSHOTTER] Removido snapshot antigo: {path.name}")
                    conn.execute("DELETE FROM snapshots WHERE snapshot_id = ?",
                                 (snap["snapshot_id"],))
            logger.info(f"[SNAPSHOTTER] Prune concluído: {len(to_remove)} snapshots removidos")
        except sqlite3.Error as e:
            logger.error(f"[SNAPSHOTTER] Erro ao fazer prune: {e}")
        finally:
            conn.close()


# Instância global
snapshotter = Snapshotter()
