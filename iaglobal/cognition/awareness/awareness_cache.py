# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
AwarenessCache v3.2 — Fachada pública única.

Todos os métodos públicos são delegados a engines. Nenhum SQL nesta classe.
API pública idêntica a v3.1 (contrato congelado).
"""

from __future__ import annotations

import asyncio
import cbor2
import logging
import sqlite3
import time
from typing import Any

from iaglobal.utils.logger import get_logger
from iaglobal.cognition.awareness.awareness_schema import (
    init_schema,
    deserialize_metadata,
    serialize_metadata,
    serialize_json,
    deserialize_json,
)
from iaglobal.cognition.awareness.models import (
    AgentActivity,
    NodeDomain,
    NodeStatus,
    CausalChain,
    DomainSnapshot,
    EpisodicMemory,
    ConfidenceTrace,
    ArtifactConfidence,
    ConfidenceSnapshot,
    AwarenessExecutionContext,
    serialize_confidence_trace,
    deserialize_confidence_trace,
    serialize_contributors,
    deserialize_contributors,
)
from iaglobal.cognition.awareness.storage_repository import StorageRepository
from iaglobal.cognition.awareness.storage_backend import SQLiteBackend
from iaglobal.cognition.awareness.time_provider import SystemClock
from iaglobal.cognition.awareness.awareness_context import (
    AwarenessContext,
    NullEventBus,
    NullMetrics,
)
from iaglobal.cognition.awareness.confidence_engine import ConfidenceEngine
from iaglobal.cognition.awareness.history_engine import HistoryEngine
from iaglobal.cognition.awareness.query_engine import QueryEngine
from iaglobal.cognition.awareness.causal_engine import CausalEngine
from iaglobal.cognition.awareness.episodic_engine import EpisodicEngine

logger = get_logger("iaglobal.cognition.awareness")


class AwarenessCache:
    """Fachada pública v3.2 — 150 linhas, zero SQL, tudo via engines."""

    def __init__(self, event_bus=None):
        self._lock = asyncio.Lock()
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        init_schema(self._db)

        self._event_bus = event_bus
        self._persistence_notify: asyncio.Event = asyncio.Event()
        self._closed = False
        self._execution_start_times: dict[str, float] = {}

        backend = SQLiteBackend(self._db)
        repository = StorageRepository(backend)
        clock = SystemClock()
        event_bus_or_null = event_bus if event_bus else NullEventBus()
        self._context = AwarenessContext(
            repository=repository,
            clock=clock,
            lock=self._lock,
            event_bus=event_bus_or_null,
            metrics=NullMetrics(),
        )
        self._confidence_engine = ConfidenceEngine(repository=repository, clock=clock)
        self._history_engine = HistoryEngine(repository=repository, clock=clock)
        self._causal_engine = CausalEngine()
        self._query_engine = QueryEngine(
            repository=repository, clock=clock, causal_engine=self._causal_engine
        )
        self._episodic_engine = EpisodicEngine(repository=repository, clock=clock)

        logger.info("AwarenessCache v3.2 inicializado (6 engines)")

    # ── API pública ────────────────────────────────────────────

    async def publish(
        self,
        execution_id: str,
        node_id: str,
        status: str,
        summary: str = "",
        metadata: dict[str, Any] | None = None,
        domain: str = NodeDomain.GENERAL.value,
        depends_on: list[str] | None = None,
        blocks: list[str] | None = None,
        tests_passed: bool = False,
        ast_valid: bool = False,
        auditor_approved: bool = False,
        consensus_reached: bool = False,
        retry_count: int = 0,
        failure_count: int = 0,
        timeout_count: int = 0,
        warning_count: int = 0,
        artifact_id: str | None = None,
    ) -> float:
        if self._closed:
            raise RuntimeError("AwarenessCache fechado")

        if execution_id not in self._execution_start_times:
            self._execution_start_times[execution_id] = time.time()

        metadata = metadata or {}
        metadata["_domain"] = domain
        metadata["_depends_on"] = depends_on or []
        metadata["_blocks"] = blocks or []
        metadata_bytes = cbor2.dumps(metadata)
        now = time.time()

        repository = self._context.repository
        old = repository.load_activity(execution_id, node_id)
        old_status = old["status"] if old else None

        ctx = AwarenessExecutionContext(
            tests_passed=tests_passed,
            ast_valid=ast_valid,
            auditor_approved=auditor_approved,
            consensus_reached=consensus_reached,
            retry_count=retry_count,
            failure_count=failure_count,
            timeout_count=timeout_count,
            warning_count=warning_count,
            domain=domain,
            artifact_id=artifact_id,
        )
        confidence, trace = self._confidence_engine.compute(ctx)
        metadata["_confidence"] = confidence
        metadata_bytes = cbor2.dumps(metadata)

        async with self._lock:
            repository.save_activity(
                execution_id, node_id, status, summary, metadata_bytes, now
            )
            repository.append_event(
                execution_id=execution_id,
                node_id=node_id,
                event_type="status_change",
                old_status=old_status,
                new_status=status,
                confidence=confidence,
                confidence_trace=serialize_confidence_trace(trace),
                metadata=metadata_bytes,
                created_at=now,
            )
            repository.append_confidence(
                execution_id=execution_id,
                node_id=node_id,
                artifact_id=artifact_id,
                domain=domain,
                confidence=confidence,
                reason=serialize_confidence_trace(trace),
                contributors=serialize_contributors([]),
                created_at=now,
            )
            # Consciência causal: reconstrói estado completo e persiste cadeias
            # de bloqueio para nós ainda ativos nesta execução.
            # Dedup por blocked_node (mantém cadeia mais recente) para evitar
            # acúmulo de cadeias obsoletas a cada publish.
            activities = repository.load_all_activities(execution_id)
            from iaglobal.cognition.awareness.awareness_schema import serialize_json

            latest_chains = {}
            for chain in self._causal_engine.build_blocking_chains(
                execution_id, activities
            ):
                latest_chains[chain.blocked_node] = chain
            for chain in latest_chains.values():
                repository.save_causal_chain(
                    {
                        "execution_id": chain.execution_id,
                        "blocked_node": chain.blocked_node,
                        "blocking_chain": serialize_json(list(chain.blocking_chain)),
                        "root_cause": chain.root_cause,
                        "depth": chain.depth,
                    }
                )
            repository.commit()

        # Notifica task de persistência
        self._persistence_notify.set()

        # Emite evento no bus (fire-and-forget, nunca bloqueia)
        if self._event_bus:
            try:
                await self._event_bus.emit(
                    "NODE_ACTIVITY",
                    {
                        "execution_id": execution_id,
                        "node": node_id,
                        "status": status,
                        "summary": summary,
                        "domain": domain,
                        "depends_on": depends_on or [],
                        "blocks": blocks or [],
                        "confidence": confidence,
                        "timestamp": now,
                    },
                )
            except Exception as exc:
                logger.warning(f"Falha ao emitir NODE_ACTIVITY: {exc}")

        return confidence

    async def snapshot(
        self,
        execution_id: str,
        domain: str | None = None,
        relevance: str | None = None,
    ) -> dict[str, AgentActivity] | DomainSnapshot | list[CausalChain]:
        if self._closed:
            raise RuntimeError("AwarenessCache fechado")
        return await self._query_engine.snapshot(
            execution_id, domain=domain, relevance=relevance
        )

    async def history(
        self,
        execution_id: str,
        node_id: str | None = None,
        fields: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if self._closed:
            raise RuntimeError("AwarenessCache fechado")
        return await self._history_engine.replay(execution_id)

    async def as_of(
        self, execution_id: str, timestamp: float
    ) -> dict[str, AgentActivity]:
        if self._closed:
            raise RuntimeError("AwarenessCache fechado")
        return await self._history_engine.as_of(execution_id, timestamp)

    async def diff(self, execution_id: str, t1: float, t2: float) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("AwarenessCache fechado")
        return await self._history_engine.diff(execution_id, t1, t2)

    async def replay(self, execution_id: str) -> list[dict[str, Any]]:
        """Replay determinístico — eventos ordenados com último estado por nó."""
        if self._closed:
            raise RuntimeError("AwarenessCache fechado")
        rows = self._context.repository.load_events(
            execution_id=execution_id, limit=10000
        )
        events = []
        node_states: dict[str, dict] = {}
        for row in rows:
            nid = row["node_id"]
            if nid:
                node_states[nid] = {
                    "node_id": nid,
                    "status": row["new_status"],
                    "old_status": row["old_status"],
                    "confidence": row["confidence"],
                    "timestamp": row["created_at"],
                }
            events.append(dict(row))
        # inject full state snapshot as the last event’s state
        if events:
            events[-1]["state"] = node_states
        return events

    async def query(self, execution_id: str, **filters) -> list[AgentActivity]:
        if self._closed:
            raise RuntimeError("AwarenessCache fechado")
        return await self._query_engine.query(execution_id, **filters)

    async def get_confidence_timeline(
        self, execution_id: str, node_id: str | None = None
    ) -> list[dict[str, Any]]:
        if self._closed:
            raise RuntimeError("AwarenessCache fechado")
        return self._confidence_engine.get_timeline(
            self._context.repository, execution_id, node_id
        )

    async def get_artifact_confidence(
        self, artifact_id: str, apply_decay: bool = False
    ) -> ArtifactConfidence | None:
        if self._closed:
            raise RuntimeError("AwarenessCache fechado")
        async with self._lock:
            row = self._context.repository.query_one(
                """SELECT * FROM confidence_history
                WHERE artifact_id = ?
                ORDER BY created_at DESC LIMIT 1""",
                (artifact_id,),
            )
        if not row:
            return None
        trace = deserialize_confidence_trace(row["reason"]) if row["reason"] else None
        contributors = (
            deserialize_contributors(row["contributors"]) if row["contributors"] else []
        )
        confidence = row["confidence"]
        if apply_decay:
            confidence = effective_confidence(
                confidence, row["created_at"], time.time()
            )
        return ArtifactConfidence(
            artifact_id=row["artifact_id"],
            artifact_type="",
            confidence=confidence,
            contributors=tuple(contributors),
            domain=row["domain"] or "",
            trace=trace or ConfidenceTrace(),
            created_at=row["created_at"],
        )

    async def export_episodic_memory(
        self,
        execution_id: str,
        final_status: str,
        ivm_score: float = 0.0,
        lessons_learned: list[str] | None = None,
    ) -> EpisodicMemory:
        if self._closed:
            raise RuntimeError("AwarenessCache fechado")
        started_at = self._execution_start_times.get(
            execution_id, self._context.clock.now()
        )
        memory = await self._episodic_engine.export(
            execution_id=execution_id,
            final_status=final_status,
            ivm_score=ivm_score,
            lessons_learned=lessons_learned,
            start_time=started_at,
        )
        await self._persist_episodic_memory(memory)
        return memory

    async def _persist_episodic_memory(self, memory: EpisodicMemory) -> None:
        await self._episodic_engine.restore(memory)

    async def get_episodic_memory(self, execution_id: str) -> EpisodicMemory | None:
        if self._closed:
            raise RuntimeError("AwarenessCache fechado")
        row = self._context.repository.load_execution(execution_id)
        if not row:
            return None
        activities = self._context.repository.load_all_activities(execution_id)
        chains = self._context.repository.load_causal_chains(execution_id)
        causal_chains = [
            CausalChain(
                execution_id=c["execution_id"],
                blocked_node=c["blocked_node"],
                blocking_chain=tuple(deserialize_json(c["blocking_chain"])),
                root_cause=c["root_cause"],
                depth=c["depth"],
            )
            for c in chains
        ]
        lessons = []
        if row.get("lessons_learned"):
            lessons = deserialize_metadata(row["lessons_learned"]).get("lessons", [])
        return EpisodicMemory(
            execution_id=row["execution_id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"] or self._context.clock.now(),
            nodes=activities,
            causal_chains=tuple(causal_chains),
            final_status=row["final_status"] or "unknown",
            ivm_score=row["ivm_score"] or 0.0,
            lessons_learned=lessons,
        )

    # ── Métodos auxiliares (mantidos para compatibilidade) ──────

    async def get_causal_explanation(
        self, execution_id: str, blocked_node: str
    ) -> str | None:
        chains = await self._query_engine.snapshot(execution_id, relevance="blocking")
        if not isinstance(chains, list):
            return None
        for chain in chains:
            if not isinstance(chain, CausalChain):
                continue
            if chain.blocked_node == blocked_node:
                if not chain.blocking_chain:
                    return f"{blocked_node} bloqueado sem causa identificada"
                path = " → ".join([blocked_node] + list(chain.blocking_chain))
                if chain.root_cause:
                    path += f" (causa raiz: {chain.root_cause})"
                return path
        return None

    async def get_node_activity(
        self, execution_id: str, node_id: str
    ) -> AgentActivity | None:
        return await self._query_engine.get_node_activity(execution_id, node_id)

    async def get_active_nodes(self, execution_id: str) -> list[str]:
        return await self._query_engine.get_active_nodes(execution_id)

    async def get_waiting_nodes(self, execution_id: str) -> list[str]:
        return await self._query_engine.get_waiting_nodes(execution_id)

    async def get_blocked_nodes(self, execution_id: str) -> list[str]:
        return await self._query_engine.get_blocked_nodes(execution_id)

    async def get_nodes_by_domain(
        self, execution_id: str, domain: str
    ) -> list[AgentActivity]:
        return await self._query_engine.get_nodes_by_domain(execution_id, domain)

    async def wait_for_persistence_signal(self, timeout: float = 5.0) -> bool:
        try:
            await asyncio.wait_for(self._persistence_notify.wait(), timeout=timeout)
            self._persistence_notify.clear()
            return True
        except asyncio.TimeoutError:
            return False

    def get_memory_db(self) -> sqlite3.Connection:
        return self._db

    async def close(self) -> None:
        self._closed = True
        if self._db:
            self._db.close()
            logger.info("AwarenessCache fechado")
