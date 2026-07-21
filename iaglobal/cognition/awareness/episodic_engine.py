# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
EpisodicEngine v3.2 — Memória episódica de execuções.

Responsável por exportar e restaurar memórias episódicas completas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from iaglobal.cognition.awareness.models import EpisodicMemory


class EpisodicEngine:
    """
    Motor de memória episódica.

    Invariantes:
    - Export é idempotente (mesma execução → mesmo resultado)
    - Restore não modifica memórias já existentes
    """

    def __init__(self, repository, clock, causal_engine=None):
        self._repository = repository
        self._clock = clock
        self._causal_engine = causal_engine

    async def export(
        self,
        execution_id: str,
        final_status: str,
        ivm_score: float = 0.0,
        lessons_learned: list[str] | None = None,
        start_time: float | None = None,
    ) -> "EpisodicMemory":
        """
        Exporta memória episódica completa da execução.

        Usado no fim da execução para:
        - Evolution Engine (aprendizado)
        - Obsidian 04_Synapses (consolidação)
        - Auditoria e replay
        """
        from iaglobal.cognition.awareness.models import AgentActivity, EpisodicMemory
        from iaglobal.cognition.awareness.storage_repository import (
            StorageRepository,
        )

        start = start_time or self._clock.now()
        end = self._clock.now()

        # Snapshot completo via repositório
        all_activities = self._repository.load_all_activities(execution_id=execution_id)

        # Cadeias causais
        causal_rows = self._repository.load_causal_chains(execution_id=execution_id)
        from iaglobal.cognition.awareness.awareness_schema import deserialize_json
        from iaglobal.cognition.awareness.models import CausalChain

        # Dedup por blocked_node: o repositório acumula histórico (INSERT),
        # mas a memória episódica representa o estado final (última cadeia).
        latest_chains: dict[str, "CausalChain"] = {}
        for row in causal_rows:
            latest_chains[row["blocked_node"]] = CausalChain(
                execution_id=row["execution_id"],
                blocked_node=row["blocked_node"],
                blocking_chain=tuple(deserialize_json(row["blocking_chain"])),
                root_cause=row["root_cause"],
                depth=row["depth"],
            )
        causal_chains = list(latest_chains.values())

        memory = EpisodicMemory(
            execution_id=execution_id,
            started_at=start,
            ended_at=end,
            nodes=all_activities,
            causal_chains=tuple(causal_chains),
            final_status=final_status,
            ivm_score=ivm_score,
            lessons_learned=lessons_learned or [],
        )

        return memory

    async def restore(self, memory: "EpisodicMemory") -> None:
        """
        Restaura memória episódica no repositório.

        Usado após crash recovery para reinstaurar estado completo.
        """
        from iaglobal.cognition.awareness.awareness_schema import serialize_metadata

        exec_data = {
            "execution_id": memory.execution_id,
            "started_at": memory.started_at,
            "ended_at": memory.ended_at,
            "final_status": memory.final_status,
            "ivm_score": memory.ivm_score,
            "lessons_learned": serialize_metadata({"lessons": memory.lessons_learned}),
        }
        self._repository.save_execution(exec_data)
        for node_id, activity in memory.nodes.items():
            metadata = serialize_metadata(activity.metadata)
            self._repository.save_activity(
                execution_id=memory.execution_id,
                node_id=node_id,
                status=activity.status,
                summary=activity.summary,
                metadata=metadata,
                updated_at=activity.timestamp,
            )
        for chain in memory.causal_chains:
            from iaglobal.cognition.awareness.awareness_schema import serialize_json

            chain_data = {
                "execution_id": chain.execution_id,
                "blocked_node": chain.blocked_node,
                "blocking_chain": serialize_json(list(chain.blocking_chain)),
                "root_cause": chain.root_cause,
                "depth": chain.depth,
            }
            self._repository.save_causal_chain(chain_data)
        self._repository.commit()
