# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
StorageRepository v3.1.5 — Camada de persistência semântica.

Responsável por todo acesso a dados. Engines não importam sqlite3.
Operações são nomeadas por intenção, não por SQL cru.

Estratégia de migração v3.1.5:
- Delega para backend (SQLiteBackend) sem alterar comportamento
- SQL atual encapsulado aqui — engines futuros não escrevem SQL
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from iaglobal.cognition.awareness.storage_backend import PersistenceBackend

if TYPE_CHECKING:
    from iaglobal.cognition.awareness.models import (
        AgentActivity,
        CausalChain,
        ConfidenceSnapshot,
        EpisodicMemory,
    )


class StorageRepository:
    """Repositório semântico — único dono dos acessos a dados.

    Nenhum engine ou facade executa SQL diretamente.
    Toda query semântica tem nome aqui.
    """

    def __init__(self, backend: PersistenceBackend) -> None:
        self._backend = backend

    # ─────────────────────────────────────────────────────────────
    # Activities (estado atual)
    # ─────────────────────────────────────────────────────────────

    def save_activity(
        self,
        execution_id: str,
        node_id: str,
        status: str,
        summary: str,
        metadata: bytes,
        updated_at: float,
    ) -> None:
        self._backend.execute(
            """INSERT OR REPLACE INTO activities
            (execution_id, node_id, status, summary, metadata, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (execution_id, node_id, status, summary, metadata, updated_at),
        )

    def load_activity(self, execution_id: str, node_id: str) -> dict[str, Any] | None:
        row = self._backend.query_one(
            "SELECT * FROM activities WHERE execution_id = ? AND node_id = ?",
            (execution_id, node_id),
        )
        return row

    def load_all_activities(self, execution_id: str) -> dict[str, "AgentActivity"]:
        rows = self._backend.query(
            "SELECT * FROM activities WHERE execution_id = ?", (execution_id,)
        )
        from iaglobal.cognition.awareness.models import AgentActivity

        return {
            row["node_id"]: AgentActivity.from_row(row, execution_id) for row in rows
        }

    # ─────────────────────────────────────────────────────────────
    # Activity Events (histórico temporal)
    # ─────────────────────────────────────────────────────────────

    def append_event(
        self,
        execution_id: str,
        node_id: str,
        event_type: str,
        old_status: str | None,
        new_status: str,
        confidence: float,
        confidence_trace: bytes | None,
        metadata: bytes,
        created_at: float,
    ) -> None:
        self._backend.execute(
            """INSERT INTO activity_events
            (execution_id, node_id, event_type, old_status, new_status,
             confidence, confidence_trace, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                execution_id,
                node_id,
                event_type,
                old_status,
                new_status,
                confidence,
                confidence_trace,
                metadata,
                created_at,
            ),
        )

    def load_events(
        self,
        execution_id: str,
        node_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if node_id:
            return self._backend.query(
                """SELECT * FROM activity_events
                WHERE execution_id = ? AND node_id = ?
                ORDER BY created_at LIMIT ?""",
                (execution_id, node_id, limit),
            )
        return self._backend.query(
            """SELECT * FROM activity_events
            WHERE execution_id = ?
            ORDER BY created_at LIMIT ?""",
            (execution_id, limit),
        )

    def load_events_up_to(
        self, execution_id: str, timestamp: float
    ) -> list[dict[str, Any]]:
        return self._backend.query(
            """SELECT * FROM activity_events
            WHERE execution_id = ? AND created_at <= ?
            ORDER BY created_at""",
            (execution_id, timestamp),
        )

    # ─────────────────────────────────────────────────────────────
    # Confidence History (evolução epistemológica)
    # ─────────────────────────────────────────────────────────────

    def append_confidence(
        self,
        execution_id: str,
        node_id: str,
        artifact_id: str | None,
        domain: str,
        confidence: float,
        reason: bytes | None,
        contributors: bytes | None,
        created_at: float,
    ) -> None:
        self._backend.execute(
            """INSERT INTO confidence_history
            (execution_id, node_id, artifact_id, domain, confidence,
             reason, contributors, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                execution_id,
                node_id,
                artifact_id,
                domain,
                confidence,
                reason,
                contributors,
                created_at,
            ),
        )

    def load_confidence_timeline(
        self, execution_id: str, node_id: str | None = None
    ) -> list[dict[str, Any]]:
        if node_id:
            return self._backend.query(
                """SELECT * FROM confidence_history
                WHERE execution_id = ? AND node_id = ?
                ORDER BY created_at""",
                (execution_id, node_id),
            )
        return self._backend.query(
            """SELECT * FROM confidence_history
            WHERE execution_id = ?
            ORDER BY created_at""",
            (execution_id,),
        )

    # ─────────────────────────────────────────────────────────────
    # Memória Episódica
    # ─────────────────────────────────────────────────────────────

    def save_execution(self, execution_data: dict[str, Any]) -> None:
        cols = ", ".join(execution_data.keys())
        placeholders = ", ".join("?" for _ in execution_data)
        self._backend.execute(
            f"INSERT OR REPLACE INTO executions ({cols}) VALUES ({placeholders})",
            tuple(execution_data.values()),
        )

    def load_execution(self, execution_id: str) -> dict[str, Any] | None:
        return self._backend.query_one(
            "SELECT * FROM executions WHERE execution_id = ?",
            (execution_id,),
        )

    def save_causal_chain(self, chain: dict[str, Any]) -> None:
        cols = ", ".join(chain.keys())
        placeholders = ", ".join("?" for _ in chain)
        self._backend.execute(
            f"INSERT INTO causal_chains ({cols}) VALUES ({placeholders})",
            tuple(chain.values()),
        )

    def load_causal_chains(self, execution_id: str) -> list[dict[str, Any]]:
        return self._backend.query(
            "SELECT * FROM causal_chains WHERE execution_id = ?",
            (execution_id,),
        )

    # ─────────────────────────────────────────────────────────────
    # Transaction
    # ─────────────────────────────────────────────────────────────

    def commit(self) -> None:
        self._backend.commit()

    def backup(self) -> bytes:
        return self._backend.backup()

    def restore(self, data: bytes) -> None:
        self._backend.restore(data)

    # ─────────────────────────────────────────────────────────────
    # Schema / metadata
    # ─────────────────────────────────────────────────────────────

    def get_event_count(self, execution_id: str, node_id: str) -> int:
        row = self._backend.query_one(
            """SELECT COUNT(*) as cnt FROM activity_events
            WHERE execution_id = ? AND node_id = ?""",
            (execution_id, node_id),
        )
        return row["cnt"] if row else 0

    def has_status_transitions(self, execution_id: str) -> bool:
        row = self._backend.query_one(
            """SELECT COUNT(*) as cnt FROM activity_events
            WHERE execution_id = ? AND old_status IS NOT NULL""",
            (execution_id,),
        )
        return (row["cnt"] if row else 0) >= 1

    def get_unique_confidence_records(self, execution_id: str) -> int:
        row = self._backend.query_one(
            """SELECT COUNT(DISTINCT node_id) as cnt FROM confidence_history
            WHERE execution_id = ?""",
            (execution_id,),
        )
        return row["cnt"] if row else 0
