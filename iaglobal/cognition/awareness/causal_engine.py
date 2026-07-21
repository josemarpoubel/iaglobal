# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
CausalEngine v3.2 — Consciência causal e detecção de bloqueios.

Responsável por construção de cadeias de bloqueio e explicações legíveis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from iaglobal.cognition.awareness.models import (
    AgentActivity,
    CausalChain,
    NodeStatus,
)


class CausalEngine:
    """
    Motor de consciência causal.

    Invariantes:
    - blocking_chain ordenada: imediato → causa raiz
    - Sem dependências cíclicas (visited set previne loops)
    """

    def build_blocking_chains(
        self,
        execution_id: str,
        activities: dict[str, AgentActivity],
    ) -> list[CausalChain]:
        """
        Constrói cadeias causais de bloqueio — semântica HISTÓRICA canônica.

        Um nó emite cadeia se status == BLOCKED. O rastreio segue depends_on
        recursivamente até a causa raiz, incluindo ancestrais COMPLETED.

        Esta é a fonte de verdade para memória episódica (AwarenessCache.publish
        / EpisodicEngine.export) — NÃO para snapshots operacionais em tempo real.
        """
        chains: list[CausalChain] = []
        blocked_nodes = {
            k: v for k, v in activities.items() if v.status == NodeStatus.BLOCKED.value
        }

        for blocked_node, activity in blocked_nodes.items():
            chain = self._trace_dependency_chain(blocked_node, activities)
            if chain:
                root_cause = chain[-1] if chain else None
                chains.append(
                    CausalChain(
                        execution_id=execution_id,
                        blocked_node=blocked_node,
                        blocking_chain=tuple(chain),
                        root_cause=root_cause,
                        depth=len(chain),
                    )
                )

        return chains

    def explain_blockage(
        self,
        blocked_node: str,
        chain: CausalChain | None = None,
    ) -> str | None:
        """
        Retorna explicação legível de por que um nó está bloqueado.

        Exemplo: "coder bloqueado → waiting database_schema (architect)
                  → waiting requirements (planner)"
        """
        if chain is None:
            return f"{blocked_node} bloqueado sem causa identificada"
        if not chain.blocking_chain:
            return f"{blocked_node} bloqueado sem causa identificada"
        arrow = " → "
        path = arrow.join([blocked_node] + list(chain.blocking_chain))
        if chain.root_cause:
            path += f" (causa raiz: {chain.root_cause})"
        return path

    def _trace_dependency_chain(
        self,
        node_id: str,
        activities: dict[str, AgentActivity],
        visited: set | None = None,
    ) -> list[str]:
        """
        Rastreia recursivamente a cadeia de dependências (depends_on).

        Exemplo: coder (BLOCKED) depends_on architect -> architect (COMPLETED)
        Retorna: ["architect"] (imediato → causa raiz)

        Args:
            node_id: Nó a rastrear
            activities: Estado completo dos nós
            visited: Conjunto de nós já visitados (previne ciclos)

        Returns:
            Cadeia na ordem: bloqueador imediato → ... → causa raiz
        """
        if visited is None:
            visited = set()

        if node_id in visited or node_id not in activities:
            return []

        visited.add(node_id)
        activity = activities[node_id]
        chain: list[str] = []

        for dep in activity.depends_on:
            if dep in activities:
                chain.append(dep)
                dep_activity = activities[dep]
                if dep_activity.status == NodeStatus.BLOCKED.value:
                    sub_chain = self._trace_dependency_chain(dep, activities, visited)
                    chain.extend(sub_chain)

        return chain
