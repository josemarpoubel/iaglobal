# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
HistoryEngine v3.2 — Operações de consulta temporal.

Responsável por replay, as_of, diff e get_confidence_timeline.
Não executa SQL diretamente — acede dados via StorageRepository.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from iaglobal.cognition.awareness.models import (
    AgentActivity,
    NodeDomain,
)


class HistoryEngine:
    """
    Motor de consulta temporal.

    Invariantes:
    - replay(history) == snapshot (Audit 1)
    - as_of reconstroi estado exato via activity_events
    """

    def __init__(self, repository, clock):
        self._repository = repository
        self._clock = clock

    # ─────────────────────────────────────────────────────────────
    # Replay temporal
    # ─────────────────────────────────────────────────────────────

    async def replay(self, execution_id: str) -> list[dict[str, Any]]:
        """
        Reconstrói timeline completa de eventos para uma execução.

        Returns: lista de eventos ordenados por created_at.
        """
        rows = self._repository.load_events(execution_id=execution_id, limit=10000)
        events = []
        for row in rows:
            event = dict(row)
            if event.get("confidence_trace"):
                from iaglobal.cognition.awareness.models import (
                    deserialize_confidence_trace,
                )

                event["confidence_trace"] = deserialize_confidence_trace(
                    event["confidence_trace"]
                )
            if event.get("metadata"):
                from iaglobal.cognition.awareness.awareness_schema import (
                    deserialize_metadata,
                )

                event["metadata"] = deserialize_metadata(event["metadata"])
            events.append(event)
        return events

    async def as_of(
        self, execution_id: str, timestamp: float
    ) -> dict[str, AgentActivity]:
        """
        Snapshot point-in-time via MVCC (activity_events).
        Reconstrói estado da execução em um timestamp específico.
        """
        rows = self._repository.load_events_up_to(
            execution_id=execution_id, timestamp=timestamp
        )
        from iaglobal.cognition.awareness.awareness_schema import deserialize_metadata
        from iaglobal.cognition.awareness.models import NodeStatus

        node_states: dict[str, AgentActivity] = {}
        for row in rows:
            if row["event_type"] != "status_change":
                continue
            metadata = deserialize_metadata(row["metadata"]) if row["metadata"] else {}
            node_states[row["node_id"]] = AgentActivity(
                execution_id=execution_id,
                node_id=row["node_id"],
                status=row["new_status"],
                summary="",
                metadata={k: v for k, v in metadata.items() if not k.startswith("_")},
                timestamp=row["created_at"],
                domain=metadata.get("_domain", NodeDomain.GENERAL.value),
                depends_on=tuple(metadata.get("_depends_on", [])),
                blocks=tuple(metadata.get("_blocks", [])),
            )
        return node_states

    async def diff(self, execution_id: str, t1: float, t2: float) -> dict[str, Any]:
        """
        Delta semântico entre dois instantes.
        Retorna activities adicionadas, modificadas e removidas.
        """
        s1 = await self.as_of(execution_id, t1)
        s2 = await self.as_of(execution_id, t2)

        added = {nid: a for nid, a in s2.items() if nid not in s1}
        removed = {nid: a for nid, a in s1.items() if nid not in s2}
        modified = {
            nid: {"before": s1[nid], "after": s2[nid]}
            for nid in s1
            if nid in s2 and s1[nid].status != s2[nid].status
        }

        return {
            "added": added,
            "removed": removed,
            "modified": modified,
            "t1": t1,
            "t2": t2,
        }

    async def get_confidence_timeline(
        self, execution_id: str, node_id: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Retorna timeline de confiança para um ou todos os nós.
        """
        rows = self._repository.load_confidence_timeline(
            execution_id=execution_id, node_id=node_id
        )
        from iaglobal.cognition.awareness.models import deserialize_confidence_trace

        events = []
        for row in rows:
            event = dict(row)
            if event.get("reason"):
                event["reason"] = deserialize_confidence_trace(event["reason"])
            events.append(event)
        return events
