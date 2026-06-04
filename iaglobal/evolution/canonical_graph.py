from typing import Dict, List, Set, Tuple
from collections import defaultdict

from iaglobal.utils.logger import logger
from iaglobal.graphs.node import Node, compute_node_id


def canonicalize(
    nodes: Dict[str, Node]
) -> Dict[str, Node]:
    if not nodes:
        logger.debug("[CANON] Grafo vazio — nada a canonicalizar")
        return {}

    before = len(nodes)
    logger.info("🧹 limpando agentes duplicados ...")

    seen: Dict[str, Node] = {}
    removed: set = set()
    removed_details = []

    for name, node in list(nodes.items()):
        if name in removed:
            continue

        if node.node_type != "general" and node.node_type != node.name:
            canonical_key = f"{node.node_type}::{node.strategy}"
        else:
            canonical_key = name

        if canonical_key in seen and canonical_key != name:
            existing = seen[canonical_key]
            merged_deps = _merge_deps(existing.depends_on, node.depends_on)

            if node.executions > existing.executions:
                node.depends_on = merged_deps
                seen[canonical_key] = node
                logger.debug("[CANON] Duplicata: '%s' (execs=%d) substitui '%s' (execs=%d) | key=%s",
                             name, node.executions, existing.name, existing.executions, canonical_key)
                removed_details.append((existing.name, name, canonical_key, node.executions, existing.executions))
            else:
                existing.depends_on = merged_deps
                logger.debug("[CANON] Duplicata: '%s' (execs=%d) mantido, '%s' (execs=%d) removido | key=%s",
                             existing.name, existing.executions, name, node.executions, canonical_key)
                removed_details.append((name, existing.name, canonical_key, node.executions, existing.executions))

            removed.add(name)
        else:
            seen[canonical_key] = node

    deduped: Dict[str, Node] = {}
    for n in seen.values():
        deduped[n.name] = n

    after_dedup = len(deduped)
    if removed_details:
        logger.info("[CANON] Deduplicação: %d removidos de %d nós",
                    len(removed_details), before)
        for removed_name, kept_name, key, rem_execs, kept_execs in removed_details:
            logger.info("  🗑️  '%s' (execs=%d) → fundido em '%s' (execs=%d) | chave=%s",
                        removed_name, rem_execs, kept_name, kept_execs, key)

    consolidated = _consolidate_edges(deduped)

    sorted_names = _topological_sort(consolidated)

    result = {}
    for name in sorted_names:
        if name in consolidated:
            result[name] = consolidated[name]

    after = len(result)
    if after < before:
        logger.info("[CANON] Grafo canonicalizado: %d → %d nós (-%d duplicatas/consolidações)",
                    before, after, before - after)
    elif before > 0:
        logger.debug("[CANON] Grafo canonicalizado: %d nós (sem duplicatas)", after)
    return result


def _merge_deps(a: List[str], b: List[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for dep in a + b:
        if dep not in seen:
            seen.add(dep)
            result.append(dep)
    return result


def _consolidate_edges(nodes: Dict[str, Node]) -> Dict[str, Node]:
    graph: Dict[str, Set[str]] = {}
    for name, node in nodes.items():
        graph[name] = set(node.depends_on)

    redundant_total = 0
    for name in graph:
        direct = set(graph[name])
        transitive: Set[str] = set()
        for dep in direct:
            if dep in graph:
                transitive.update(graph[dep])
        redundant = direct & transitive
        if redundant:
            graph[name] = direct - redundant
            nodes[name].depends_on = [d for d in nodes[name].depends_on if d not in redundant]
            redundant_total += len(redundant)
            logger.debug("[CANON] Dependências redundantes removidas de '%s': %s",
                         name, sorted(redundant))

    if redundant_total:
        logger.info("[CANON] %d dependências transitivas removidas em %d nós",
                    redundant_total,
                    sum(1 for n in nodes.values() if n.depends_on != list(graph.get(n.name, set()))))

    return nodes


def _topological_sort(nodes: Dict[str, Node]) -> List[str]:
    in_degree: Dict[str, int] = {}
    adj: Dict[str, List[str]] = defaultdict(list)

    for name in nodes:
        in_degree[name] = 0

    for name, node in nodes.items():
        for dep in node.depends_on:
            if dep in nodes:
                adj[dep].append(name)
                in_degree[name] = in_degree.get(name, 0) + 1

    queue = sorted([n for n in nodes if in_degree.get(n, 0) == 0])
    logger.debug("[CANON] Ordenação topológica: %d nós raiz (in_degree=0)", len(queue))

    sorted_list: List[str] = []

    while queue:
        current = queue.pop(0)
        sorted_list.append(current)
        for neighbor in sorted(adj.get(current, [])):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
                queue.sort()

    if len(sorted_list) != len(nodes):
        remaining = set(nodes.keys()) - set(sorted_list)
        logger.warning("[CANON] ⚠️ Ciclo detectado no grafo! %d nós não ordenados: %s",
                       len(remaining), sorted(remaining))
        sorted_list.extend(sorted(remaining))
    else:
        logger.debug("[CANON] Ordenação topológica OK: %d nós em ordem determinística", len(sorted_list))

    return sorted_list


def compute_graph_hash(nodes: Dict[str, Node]) -> str:
    import hashlib
    sorted_items = sorted(nodes.items())
    raw = "|".join(
        f"{name}:{node.node_type}:{node.strategy}:{node.seed_id}:{node.mutation_id}:{node.version}:{sorted(node.depends_on)}"
        for name, node in sorted_items
    )
    h = hashlib.sha3_256(raw.encode()).hexdigest()[:16]
    logger.debug("[CANON] Hash do grafo: %s (%d nós)", h, len(nodes))
    return h
