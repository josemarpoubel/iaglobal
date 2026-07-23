# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
QueryEngine v3.2 — Operações de consulta e snapshot.

Responsável por snapshot(), query(), e operações de filtro por domínio/status.
Não executa SQL diretamente.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from iaglobal.cognition.awareness.models import (
    AgentActivity,
    CausalChain,
    DomainSnapshot,
    NodeDomain,
    NodeStatus,
)


class QueryEngine:
    """
    Motor de consulta e snapshot.

    Invariantes:
    - snapshot retorna estado imutável (cópia)
    - query é read-only (side-effect free)
    """

    def __init__(self, repository, clock, causal_engine=None):
        self._repository = repository
        self._clock = clock
        self._causal_engine = causal_engine

    async def snapshot(
        self,
        execution_id: str,
        domain: str | None = None,
        relevance: str | None = None,
    ) -> dict[str, AgentActivity] | DomainSnapshot | list[CausalChain]:
        """
        Retorna snapshot do estado com filtros avançados.

        Returns:
        - Sem filtros: dict[node_id -> AgentActivity]
        - Com domain: DomainSnapshot
        - Com relevance="blocking": list[CausalChain]
        """
        all_activities = self._repository.load_all_activities(execution_id=execution_id)

        if domain is not None:
            filtered = {k: v for k, v in all_activities.items() if v.domain == domain}
            return DomainSnapshot(
                execution_id=execution_id,
                domain=domain,
                activities=tuple(filtered.values()),
                timestamp=self._clock.now(),
            )

        if relevance == "blocking":
            return self._build_causal_chains(execution_id, all_activities)

        return all_activities

    def _build_causal_chains(
        self,
        execution_id: str,
        activities: dict[str, AgentActivity],
    ) -> list[CausalChain]:
        """Constrói cadeias causais para snapshot(relevance="blocking").

        Semântica OPERACIONAL (estado vivo do organismo):
        Um nó entra na cadeia se está BLOCKED OU se alguma dependência ainda
        não está COMPLETED (causalmente aguardando progresso). O rastreio segue
        depends_on até a causa raiz, considerando apenas dependências não-COMPLETED.

        Esta é uma fotografia do bloqueio instantâneo — diferente da
        causalidade HISTÓRICA persistida por CausalEngine.build_blocking_chains
        (que considera apenas status == BLOCKED).
        """
        chains: list[CausalChain] = []
        for node_id, activity in activities.items():
            if not self._is_operationally_blocked(activity, activities):
                continue
            chain = self._trace_dependency_chain(node_id, activities)
            root_cause = chain[-1] if chain else None
            chains.append(
                CausalChain(
                    execution_id=execution_id,
                    blocked_node=node_id,
                    blocking_chain=tuple(chain),
                    root_cause=root_cause,
                    depth=len(chain),
                )
            )

        return chains

    @staticmethod
    def _is_operationally_blocked(
        activity: "AgentActivity", activities: dict[str, AgentActivity]
    ) -> bool:
        """Predicado de bloqueio operacional instantâneo (snapshot)."""
        if activity.status == NodeStatus.BLOCKED.value:
            return True
        for dep in activity.depends_on:
            dep_activity = activities.get(dep)
            if (
                dep_activity is None
                or dep_activity.status != NodeStatus.COMPLETED.value
            ):
                return True
        return False

    def _trace_dependency_chain(
        self,
        node_id: str,
        activities: dict[str, AgentActivity],
        visited: set | None = None,
    ) -> list[str]:
        """Rastreia recursivamente a cadeia de dependências (depends_on).

        Semântica operacional: segue apenas dependências NÃO COMPLETED,
        pois apenas elas podem estar bloqueando o nó atual.
        """
        if visited is None:
            visited = set()

        if node_id in visited or node_id not in activities:
            return []

        visited.add(node_id)
        activity = activities[node_id]
        chain: list[str] = []

        for dep in activity.depends_on:
            if dep not in activities:
                continue
            dep_activity = activities[dep]
            if dep_activity.status == NodeStatus.COMPLETED.value:
                continue
            chain.append(dep)
            sub_chain = self._trace_dependency_chain(dep, activities, visited)
            chain.extend(sub_chain)

        return chain

    async def query(self, execution_id: str, **filters) -> list[AgentActivity]:
        """
        Query composicional com filtros.

        Filtros suportados: domain, status, node_id, depends_on (parcial).
        """
        snapshot = await self.snapshot(execution_id)
        results = list(snapshot.values())

        if "domain" in filters:
            results = [a for a in results if a.domain == filters["domain"]]
        if "status" in filters:
            results = [a for a in results if a.status == filters["status"]]
        if "node_id" in filters:
            results = [a for a in results if a.node_id == filters["node_id"]]
        if "depends_on" in filters:
            dep = filters["depends_on"]
            results = [a for a in results if dep in (a.depends_on or [])]

        return results

    async def get_node_activity(
        self, execution_id: str, node_id: str
    ) -> AgentActivity | None:
        """Obtém atividade de um nó específico."""
        row = self._repository.load_activity(execution_id=execution_id, node_id=node_id)
        if not row:
            return None
        from iaglobal.cognition.awareness.models import AgentActivity

        return AgentActivity.from_row(row, execution_id)

    async def get_active_nodes(self, execution_id: str) -> list[str]:
        """Retorna lista de node_ids com status 'running'."""
        snapshot = await self.snapshot(execution_id)
        return [
            nid
            for nid, activity in snapshot.items()
            if activity.status == NodeStatus.RUNNING.value
        ]

    async def get_waiting_nodes(self, execution_id: str) -> list[str]:
        """Retorna lista de node_ids com status 'waiting'."""
        snapshot = await self.snapshot(execution_id)
        return [
            nid
            for nid, activity in snapshot.items()
            if activity.status == NodeStatus.WAITING.value
        ]

    async def get_blocked_nodes(self, execution_id: str) -> list[str]:
        """Retorna lista de node_ids com status 'blocked'."""
        snapshot = await self.snapshot(execution_id)
        return [
            nid
            for nid, activity in snapshot.items()
            if activity.status == NodeStatus.BLOCKED.value
        ]

    async def get_nodes_by_domain(
        self, execution_id: str, domain: str
    ) -> list[AgentActivity]:
        """Retorna todos os nós de um domínio específico."""
        domain_snapshot = await self.snapshot(execution_id, domain=domain)
        return list(domain_snapshot.activities)

    async def get_causal_explanation(
        self, execution_id: str, blocked_node: str
    ) -> str | None:
        """Retorna explicação legível de por que um nó está bloqueado."""
        chains = await self.snapshot(execution_id, relevance="blocking")
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
