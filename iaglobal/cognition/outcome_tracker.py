import json
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from pathlib import Path

from iaglobal._paths import CORE_DB
from iaglobal.utils.logger import logger


@dataclass
class ExecutionOutcome:
    provider: str
    model: str
    fingerprint: str
    latency_ms: float
    token_cost: float
    success_score: float
    retries: int = 0
    timestamp: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


class OutcomeTracker:
    """Persiste ExecutionOutcome em tabela SQLite para alimentar BanditPolicy com dados históricos."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or CORE_DB
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS execution_outcomes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        provider TEXT NOT NULL,
                        model TEXT NOT NULL,
                        fingerprint TEXT NOT NULL DEFAULT '',
                        latency_ms REAL NOT NULL DEFAULT 0,
                        token_cost REAL NOT NULL DEFAULT 0,
                        success_score REAL NOT NULL DEFAULT 0,
                        retries INTEGER NOT NULL DEFAULT 0,
                        timestamp REAL NOT NULL,
                        tokens_in INTEGER NOT NULL DEFAULT 0,
                        tokens_out INTEGER NOT NULL DEFAULT 0
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_model ON execution_outcomes(model)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_fingerprint ON execution_outcomes(fingerprint)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_provider ON execution_outcomes(provider)")
        except sqlite3.Error as e:
            logger.error(f"[OUTCOME_TRACKER] Erro ao criar tabela: {e}")
        finally:
            conn.close()

    def record(self, outcome: ExecutionOutcome):
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute(
                    """INSERT INTO execution_outcomes
                       (provider, model, fingerprint, latency_ms, token_cost, success_score, retries, timestamp, tokens_in, tokens_out)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (outcome.provider, outcome.model, outcome.fingerprint, outcome.latency_ms,
                     outcome.token_cost, outcome.success_score, outcome.retries,
                     outcome.timestamp, outcome.tokens_in, outcome.tokens_out)
                )
        except sqlite3.Error as e:
            logger.error(f"[OUTCOME_TRACKER] Erro ao registrar outcome: {e}")
        finally:
            conn.close()

    def query(self, model: Optional[str] = None, fingerprint: Optional[str] = None,
              provider: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conditions = []
            params: List[Any] = []
            if model:
                conditions.append("model = ?")
                params.append(model)
            if fingerprint:
                conditions.append("fingerprint = ?")
                params.append(fingerprint)
            if provider:
                conditions.append("provider = ?")
                params.append(provider)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            cursor = conn.execute(
                f"SELECT provider, model, fingerprint, latency_ms, token_cost, success_score, "
                f"retries, timestamp, tokens_in, tokens_out "
                f"FROM execution_outcomes {where} ORDER BY id DESC LIMIT ?",
                params + [limit]
            )
            return [
                {"provider": r[0], "model": r[1], "fingerprint": r[2], "latency_ms": r[3],
                 "token_cost": r[4], "success_score": r[5], "retries": r[6], "timestamp": r[7],
                 "tokens_in": r[8], "tokens_out": r[9]}
                for r in cursor.fetchall()
            ]
        except sqlite3.Error as e:
            logger.error(f"[OUTCOME_TRACKER] Erro ao consultar: {e}")
            return []
        finally:
            conn.close()

    def avg_success_rate(self, model: str) -> float:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT AVG(success_score) FROM execution_outcomes WHERE model = ? AND success_score >= 0",
                (model,)
            )
            row = cursor.fetchone()
            return row[0] if row and row[0] is not None else 0.0
        except sqlite3.Error:
            return 0.0
        finally:
            conn.close()

    def avg_latency(self, model: str) -> float:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT AVG(latency_ms) FROM execution_outcomes WHERE model = ?",
                (model,)
            )
            row = cursor.fetchone()
            return row[0] if row and row[0] is not None else 0.0
        except sqlite3.Error:
            return 0.0
        finally:
            conn.close()


# Instância global
outcome_tracker = OutcomeTracker()

