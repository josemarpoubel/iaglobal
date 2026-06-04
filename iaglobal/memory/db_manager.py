# iaglobal/memory/db_manager.py

import sqlite3

from pathlib import Path
from typing import Dict, Any, Optional
from iaglobal.utils.logger import logger
from iaglobal._paths import CORE_DB

class DatabaseManager:

    """Gerenciador de banco de dados unificado para insights e conhecimento."""

    MAX_RETRY_COUNT = 3

    def __init__(self, db_path: Path = CORE_DB):
        self.db_path = db_path
        self._init_tables()

    def _init_tables(self):
        """Cria todas as tabelas essenciais e otimiza o banco para modo WAL."""
        try:
            conn = sqlite3.connect(self.db_path)
        except sqlite3.Error as e:
            logger.error(f"💥 Erro ao inicializar tabelas: {e}")
            raise

        try:
            with conn:
                conn.execute("PRAGMA journal_mode=WAL;")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS insights (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent TEXT,
                        task_id TEXT,
                        content TEXT,
                        score REAL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS knowledge (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT,
                        context TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS vector_store (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        embedding BLOB,
                        metadata TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS execution_states (
                        execution_id TEXT NOT NULL,
                        node_id TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'PENDING',
                        result_data BLOB,
                        retry_count INTEGER DEFAULT 0,
                        error_message TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (execution_id, node_id)
                    )
                """)

                conn.execute("CREATE INDEX IF NOT EXISTS idx_vector_metadata ON vector_store(metadata)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_node ON execution_states (execution_id, status)")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS search_cache (
                        cache_key TEXT PRIMARY KEY,
                        result TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.execute("CREATE INDEX IF NOT EXISTS idx_search_cache_key ON search_cache(cache_key)")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS decision_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        execution_id TEXT NOT NULL,
                        step TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        event_data TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_execution ON decision_events(execution_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_step ON decision_events(step)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_created ON decision_events(created_at)")

                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"💥 Erro ao inicializar tabelas: {e}")
            raise
        finally:
            conn.close()

    def insert_insight(self, agent: str, task_id: str, content: str, score: float):
        """Persiste o aprendizado de um agente no banco central."""
        try:
            conn = sqlite3.connect(self.db_path)
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao inserir insight do agente {agent}: {e}")
            return

        try:
            with conn:
                conn.execute(
                    "INSERT INTO insights (agent, task_id, content, score) VALUES (?, ?, ?, ?)",
                    (agent, task_id, content, score)
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao inserir insight do agente {agent}: {e}")
        finally:
            conn.close()

    def get_insights(
        self,
        agent: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> list:
        """
        Recupera insights armazenados com filtros e paginação.

        Args:
            agent: Filtrar por nome do agente
            limit: Máximo de registros (paginação)
            offset: Deslocamento (paginação)
            start_date: Data inicial ISO (YYYY-MM-DD ou YYYY-MM-DD HH:MM)
            end_date: Data final ISO
            min_score: Score mínimo (inclusivo)

        Returns:
            Lista de dicts com id, agent, task_id, content, score, timestamp
        """
        try:
            conn = sqlite3.connect(self.db_path)
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao conectar para get_insights: {e}")
            return []

        try:
            conditions = []
            params = []

            if agent:
                conditions.append("agent = ?")
                params.append(agent)

            if start_date:
                conditions.append("timestamp >= ?")
                params.append(start_date)

            if end_date:
                conditions.append("timestamp <= ?")
                params.append(end_date)

            if min_score is not None:
                conditions.append("score >= ?")
                params.append(min_score)

            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)

            sql = (
                f"SELECT id, agent, task_id, content, score, timestamp "
                f"FROM insights {where} ORDER BY score DESC, timestamp DESC "
                f"LIMIT ? OFFSET ?"
            )
            params.append(limit)
            params.append(offset)

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "agent": r[1],
                    "task_id": r[2],
                    "content": r[3],
                    "score": r[4],
                    "timestamp": r[5],
                }
                for r in rows
            ]
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao get_insights: {e}")
            return []
        finally:
            conn.close()

    def count_insights(
        self,
        agent: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> int:
        """
        Retorna o total de insights que correspondem aos filtros (útil para paginação).

        Args:
            agent: Filtrar por nome do agente
            start_date: Data inicial ISO
            end_date: Data final ISO
            min_score: Score mínimo

        Returns:
            Número total de registros
        """
        try:
            conn = sqlite3.connect(self.db_path)
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao conectar para count_insights: {e}")
            return 0

        try:
            conditions = []
            params = []

            if agent:
                conditions.append("agent = ?")
                params.append(agent)

            if start_date:
                conditions.append("timestamp >= ?")
                params.append(start_date)

            if end_date:
                conditions.append("timestamp <= ?")
                params.append(end_date)

            if min_score is not None:
                conditions.append("score >= ?")
                params.append(min_score)

            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)

            cursor = conn.execute(
                f"SELECT COUNT(*) FROM insights {where}", params
            )
            row = cursor.fetchone()
            return row[0] if row else 0
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao count_insights: {e}")
            return 0
        finally:
            conn.close()

    # =========================================================
    # SEARCH CACHE METHODS
    # =========================================================

    def get_cached_search(self, cache_key: str) -> Optional[str]:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT result FROM search_cache WHERE cache_key = ?",
                (cache_key,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except sqlite3.Error:
            return None
        finally:
            conn.close()

    def cache_search_result(self, cache_key: str, result: str) -> None:
        conn = self._get_conn()
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO search_cache (cache_key, result) VALUES (?, ?)",
                    (cache_key, result)
                )
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao cachear busca {cache_key}: {e}")
        finally:
            conn.close()

    # =========================================================
    # CHECKPOINT / EXECUTION STATE METHODS
    # =========================================================

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def init_execution(self, execution_id: str, node_ids: list[str]) -> None:
        """Registra todos os nós de uma execução como PENDING."""
        conn = self._get_conn()
        try:
            with conn:
                for node_id in node_ids:
                    conn.execute(
                        """INSERT OR IGNORE INTO execution_states
                           (execution_id, node_id, status, retry_count)
                           VALUES (?, ?, 'PENDING', 0)""",
                        (execution_id, node_id)
                    )
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao init_execution {execution_id}: {e}")
        finally:
            conn.close()

    def get_execution_state(self, execution_id: str) -> Dict[str, dict]:
        """Retorna dict {node_id: {status, result_data, retry_count, error_message}}."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """SELECT node_id, status, result_data, retry_count, error_message
                   FROM execution_states WHERE execution_id = ?""",
                (execution_id,)
            )
            rows = cursor.fetchall()
            result = {}
            for row in rows:
                result[row[0]] = {
                    "status": row[1],
                    "result_data": row[2],
                    "retry_count": row[3],
                    "error_message": row[4],
                }
            return result
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao get_execution_state {execution_id}: {e}")
            return {}
        finally:
            conn.close()

    def get_checkpoint(self, execution_id: str) -> Dict[str, Dict[str, Any]]:
        """Retorna dicionário com todos os nós concluídos de uma execução."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """SELECT node_id, status, result_data, retry_count, error_message
                   FROM execution_states
                   WHERE execution_id = ? AND status = 'COMPLETED'""",
                (execution_id,)
            )
            rows = cursor.fetchall()
            result = {}
            for row in rows:
                result[row[0]] = {
                    "status": row[1],
                    "result_data": row[2],
                    "retry_count": row[3],
                    "error_message": row[4],
                }
            return result
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao get_checkpoint {execution_id}: {e}")
            return {}
        finally:
            conn.close()

    def update_node_status(
        self,
        execution_id: str,
        node_id: str,
        status: str,
        result_data: Optional[bytes] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Atualiza o status de um nó na execução."""
        conn = self._get_conn()
        try:
            with conn:
                if status == "FAILED":
                    conn.execute(
                        """UPDATE execution_states
                           SET status = ?, result_data = ?, error_message = ?,
                               retry_count = retry_count + 1, updated_at = CURRENT_TIMESTAMP
                           WHERE execution_id = ? AND node_id = ?""",
                        (status, result_data, error_message, execution_id, node_id)
                    )
                else:
                    conn.execute(
                        """INSERT OR REPLACE INTO execution_states
                           (execution_id, node_id, status, result_data, retry_count, error_message, updated_at)
                           VALUES (?, ?, ?, ?, COALESCE((SELECT retry_count FROM execution_states
                             WHERE execution_id = ? AND node_id = ?), 0), ?, CURRENT_TIMESTAMP)""",
                        (execution_id, node_id, status, result_data, execution_id, node_id, error_message)
                    )
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao update_node_status {execution_id}/{node_id}: {e}")
        finally:
            conn.close()

    def get_node_retry_count(self, execution_id: str, node_id: str) -> int:
        """Retorna o retry_count atual de um nó."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT retry_count FROM execution_states WHERE execution_id = ? AND node_id = ?",
                (execution_id, node_id)
            )
            row = cursor.fetchone()
            return row[0] if row else 0
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao get_node_retry_count {execution_id}/{node_id}: {e}")
            return 0
        finally:
            conn.close()

    def reset_failed_node(self, execution_id: str, node_id: str) -> None:
        """Reseta o status de um nó falho para PENDING (permite re-execução)."""
        conn = self._get_conn()
        try:
            with conn:
                conn.execute(
                    """UPDATE execution_states
                       SET status = 'PENDING', error_message = NULL, updated_at = CURRENT_TIMESTAMP
                       WHERE execution_id = ? AND node_id = ?""",
                    (execution_id, node_id)
                )
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao reset_failed_node {execution_id}/{node_id}: {e}")
        finally:
            conn.close()

    def clear_execution(self, execution_id: str) -> None:
        """Remove todos os registros de uma execução."""
        conn = self._get_conn()
        try:
            with conn:
                conn.execute("DELETE FROM execution_states WHERE execution_id = ?", (execution_id,))
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao clear_execution {execution_id}: {e}")
        finally:
            conn.close()

    # =========================================================
    # DECISION EVENTS
    # =========================================================

    def insert_decision_event(self, execution_id: str, step: str, timestamp: str, event_data: str) -> None:
        conn = self._get_conn()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO decision_events (execution_id, step, timestamp, event_data) VALUES (?, ?, ?, ?)",
                    (execution_id, step, timestamp, event_data)
                )
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao inserir decision_event {execution_id}/{step}: {e}")
        finally:
            conn.close()

    def query_decision_events(
        self,
        execution_id: Optional[str] = None,
        step: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list:
        conn = self._get_conn()
        try:
            conditions = []
            params = []
            if execution_id:
                conditions.append("execution_id = ?")
                params.append(execution_id)
            if step:
                conditions.append("step = ?")
                params.append(step)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            cursor = conn.execute(
                f"SELECT execution_id, step, timestamp, event_data, created_at "
                f"FROM decision_events {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                params + [limit, offset]
            )
            rows = cursor.fetchall()
            return [
                {
                    "execution_id": r[0],
                    "step": r[1],
                    "timestamp": r[2],
                    "event_data": r[3],
                    "created_at": r[4],
                }
                for r in rows
            ]
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao query_decision_events: {e}")
            return []
        finally:
            conn.close()

    def count_decision_events(
        self,
        execution_id: Optional[str] = None,
        step: Optional[str] = None,
    ) -> int:
        conn = self._get_conn()
        try:
            conditions = []
            params = []
            if execution_id:
                conditions.append("execution_id = ?")
                params.append(execution_id)
            if step:
                conditions.append("step = ?")
                params.append(step)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            cursor = conn.execute(f"SELECT COUNT(*) FROM decision_events {where}", params)
            row = cursor.fetchone()
            return row[0] if row else 0
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao count_decision_events: {e}")
            return 0
        finally:
            conn.close()

    def delete_execution_events(self, execution_id: str) -> None:
        conn = self._get_conn()
        try:
            with conn:
                conn.execute("DELETE FROM decision_events WHERE execution_id = ?", (execution_id,))
        except sqlite3.Error as e:
            logger.error(f"❌ Erro ao delete_execution_events {execution_id}: {e}")
        finally:
            conn.close()


# Instância Global para importação direta pelos agentes
db = DatabaseManager()
