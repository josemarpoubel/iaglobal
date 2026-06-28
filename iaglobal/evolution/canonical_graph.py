# iaglobal/evolution/canonical_graph.py

from __future__ import annotations

import logging

from typing import Dict, List, Set, Tuple

from collections import defaultdict

from iaglobal.graphs.node import Node

from iaglobal.utils.logger import get_logger

logger = logging.getLogger(__name__)

class Canonical_Graph:

    def __init__(self):
        # instancia o logger do módulo (corrige uso atual de logger global inexistente)
        self.logger = get_logger()

    def canonicalize(
        self,
        nodes: Dict[str, Node]
    ) -> Dict[str, Node]:
        if not nodes:
            logger.debug("[CANON] Grafo vazio — nada a canonicalizar")
            return {}

        before = len(nodes)
        logger.info("🧹 Iniciando limpeza de agentes duplicados ...")

        seen: Dict[str, Node] = {}
        removed: Set[str] = set()
        removed_details: List[tuple] = []

        def canonical_key(node: Node, name: str) -> str:
            """
            Gera chave estável de deduplicação.
            Prioriza identidade funcional ao invés de nome bruto.
            """
            if node.node_type and node.node_type != "general":
                return f"{node.node_type}::{node.strategy}"
            return name

        for name, node in list(nodes.items()):
            if name in removed:
                continue

            key = canonical_key(node, name)

            if key in seen:
                existing = seen[key]

                merged_deps = self._merge_deps(existing.depends_on, node.depends_on)

                # regra de sobrevivência: maior número de execuções vence
                if node.executions > existing.executions:
                    survivor, loser = node, existing
                    seen[key] = node
                else:
                    survivor, loser = existing, node

                survivor.depends_on = merged_deps

                logger.debug(
                    "[CANON] Duplicata '%s' vs '%s' | vencedor='%s' (execs=%d) | key=%s",
                    node.name,
                    existing.name,
                    survivor.name,
                    survivor.executions,
                    key,
                )

                removed_details.append(
                    (loser.name, survivor.name, key, loser.executions, survivor.executions)
                )
                removed.add(loser.name)

            else:
                seen[key] = node

        deduped: Dict[str, Node] = {n.name: n for n in seen.values()}

        if removed_details:
            logger.info(
                "[CANON] Deduplicação concluída: %d removidos de %d nós",
                len(removed_details),
                before,
            )

            for removed_name, kept_name, key, rem_execs, kept_execs in removed_details:
                logger.info(
                    "  🗑️ '%s' (execs=%d) → '%s' (execs=%d) | key=%s",
                    removed_name,
                    rem_execs,
                    kept_name,
                    kept_execs,
                    key,
                )

        consolidated = self._consolidate_edges(deduped)
        sorted_names = self._topological_sort(consolidated)

        result: Dict[str, Node] = {}
        for name in sorted_names:
            node = consolidated.get(name)
            if node:
                result[name] = node

        after = len(result)

        if after < before:
            logger.info(
                "[CANON] Grafo canonicalizado: %d → %d nós (-%d)",
                before,
                after,
                before - after,
            )
        else:
            logger.debug(
                "[CANON] Canonicalização estável: %d nós",
                after,
            )

        return result

    def _merge_deps(self, a: List[str], b: List[str]) -> List[str]:
        """
        Merge estável de dependências preservando ordem de aparição
        e eliminando duplicatas mantendo a primeira ocorrência.
        """
        if not a and not b:
            return []

        if not a:
            return list(dict.fromkeys(b))

        if not b:
            return list(dict.fromkeys(a))

        seen: Set[str] = set()
        result: List[str] = []

        for dep in (*a, *b):
            if dep in seen:
                continue
            seen.add(dep)
            result.append(dep)

        return result

    def _consolidate_edges(self, nodes: Dict[str, Node]) -> Dict[str, Node]:
        """
        Remove dependências transitivas redundantes mantendo consistência estrutural
        do grafo e preservando relações diretas essenciais.
        """

        if not nodes:
            return nodes

        graph: Dict[str, Set[str]] = {
            name: set(node.depends_on) for name, node in nodes.items()
        }

        redundant_total = 0
        affected_nodes = 0

        for name, direct in graph.items():
            if not direct:
                continue

            transitive: Set[str] = set()
            for dep in direct:
                dep_edges = graph.get(dep)
                if dep_edges:
                    transitive.update(dep_edges)

            redundant = direct.intersection(transitive)

            if not redundant:
                continue

            new_direct = direct.difference(redundant)
            graph[name] = new_direct

            node = nodes[name]
            node.depends_on = [d for d in node.depends_on if d not in redundant]

            redundant_total += len(redundant)
            affected_nodes += 1

            logger.debug(
                "[CANON] '%s' - removidas dependências transitivas: %s",
                name,
                sorted(redundant),
            )

        if redundant_total:
            logger.info(
                "[CANON] Consolidação concluída: %d redundâncias removidas em %d nós",
                redundant_total,
                affected_nodes,
            )

        return nodes

    def _topological_sort(self, nodes: Dict[str, Node]) -> List[str]:
        """
        Ordenação topológica determinística com detecção de ciclos
        e estabilidade de execução.
        """

        if not nodes:
            return []

        in_degree: Dict[str, int] = {name: 0 for name in nodes}
        adj: Dict[str, List[str]] = defaultdict(list)

        for name, node in nodes.items():
            for dep in node.depends_on:
                if dep in nodes:
                    adj[dep].append(name)
                    in_degree[name] += 1

        queue: List[str] = sorted(
            [n for n, deg in in_degree.items() if deg == 0]
        )

        logger.debug(
            "[CANON] Topological sort iniciado: %d nós raiz",
            len(queue),
        )

        sorted_list: List[str] = []
        visited_count = 0

        while queue:
            current = queue.pop(0)
            sorted_list.append(current)
            visited_count += 1

            for neighbor in sorted(adj.get(current, [])):
                in_degree[neighbor] -= 1

                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

            queue.sort()

        if visited_count != len(nodes):
            remaining = sorted(set(nodes.keys()) - set(sorted_list))

            logger.warning(
                "[CANON] Ciclo detectado no grafo: %d nós não ordenados: %s",
                len(remaining),
                remaining,
            )

            sorted_list.extend(remaining)
        else:
            logger.debug(
                "[CANON] Ordenação topológica OK (%d nós)",
                len(sorted_list),
            )

        return sorted_list

    def compute_graph_hash(self, nodes: Dict[str, Node]) -> str:
        """
        Gera hash determinístico do grafo com base em estrutura completa
        e estado dos nós.
        """

        import hashlib

        if not nodes:
            return hashlib.sha3_256(b"empty").hexdigest()[:16]

        sorted_items = sorted(nodes.items())

        raw = "|".join(
            f"{name}:"
            f"{node.node_type}:"
            f"{node.strategy}:"
            f"{node.seed_id}:"
            f"{node.mutation_id}:"
            f"{node.version}:"
            f"{tuple(sorted(node.depends_on))}"
            for name, node in sorted_items
        )

        h = hashlib.sha3_256(raw.encode()).hexdigest()[:16]

        logger.debug(
            "[CANON] Hash do grafo gerado: %s (%d nós)",
            h,
            len(nodes),
        )

        return h


# Funções de compatibilidade para importação direta
_canonical = Canonical_Graph()


def canonicalize(nodes: Dict[str, Node]) -> Dict[str, Node]:
    return _canonical.canonicalize(nodes)


def compute_graph_hash(nodes: Dict[str, Node]) -> str:
    return _canonical.compute_graph_hash(nodes)
