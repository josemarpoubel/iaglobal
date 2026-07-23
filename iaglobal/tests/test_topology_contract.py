import ast
from pathlib import Path

from iaglobal.graphs.pipeline_definition import PIPELINE_SKILLS
from iaglobal.graphs.builder import RUN_NODE_NAMES
from iaglobal.graphs.topology import audit_representations, PHASES, NODE_DEPENDENCIES

NODES_DIR = Path(__file__).parent.parent / "graphs" / "nodes"


def _collect_run_functions() -> set[str]:
    run_fns = set()
    for f in sorted(NODES_DIR.glob("no_*.py")):
        name = f.stem[3:]
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == f"run_{name}":
                    run_fns.add(name)
                    break
    return run_fns


def _topology_nodes() -> set[str]:
    nodes = set()
    for ns in PHASES.values():
        nodes.update(ns)
    nodes.update(NODE_DEPENDENCIES.keys())
    for deps in NODE_DEPENDENCIES.values():
        nodes.update(deps)
    return nodes


def _topological_sort(nodes: set[str], deps: dict[str, list[str]]) -> list[str]:
    in_degree = {n: 0 for n in nodes}
    for node in deps:
        if node in in_degree:
            for dep in deps[node]:
                if dep in in_degree:
                    in_degree[node] += 1

    queue = [n for n in nodes if in_degree.get(n, 0) == 0]
    order = []

    while queue:
        n = queue.pop(0)
        order.append(n)
        for node, dl in deps.items():
            if n in dl and node in in_degree:
                in_degree[node] -= 1
                if in_degree[node] == 0:
                    queue.append(node)

    # Add remaining isolated nodes
    for n in nodes:
        if n not in order:
            order.append(n)

    return order


def test_all_run_functions_have_registration():
    run_fns = _collect_run_functions()
    pipeline_set = set(n for n, _ in PIPELINE_SKILLS)
    builder_set = set(RUN_NODE_NAMES)
    topology_set = _topology_nodes()

    registered = pipeline_set | builder_set | topology_set
    orphans = run_fns - registered
    assert not orphans, f"run_* functions without registration: {sorted(orphans)}"


def test_audit_all_checks_pass():
    """All diagnostic checks in audit_representations must pass."""
    run_fns = _collect_run_functions()
    pipeline_set = set(n for n, _ in PIPELINE_SKILLS)
    builder_set = set(RUN_NODE_NAMES)
    result = audit_representations(pipeline_set, builder_set, run_fns)

    failed = [k for k, v in result["checks"].items() if not v]
    assert result["valid"], (
        f"Topology contract invalid: {failed}\n"
        f"  cycles: {result['cycles']}\n"
        f"  dangling_deps: {result['dangling_deps']}\n"
        f"  orphan_run_functions: {result['orphan_run_functions']}\n"
        f"  pipeline_without_phase: {result['pipeline_without_phase']}\n"
        f"  builder_without_phase: {result['builder_without_phase']}\n"
        f"  dependency_without_phase: {result['dependency_without_phase']}\n"
        f"  duplicate_phase_nodes: {result['duplicate_phase_nodes']}\n"
        f"  unreachable: {result['unreachable']}"
    )


def test_no_cycles():
    pipeline_set = set(n for n, _ in PIPELINE_SKILLS)
    builder_set = set(RUN_NODE_NAMES)
    result = audit_representations(pipeline_set, builder_set)
    assert len(result["cycles"]) == 0, f"Cycles detected: {result['cycles']}"


def test_topological_order_is_valid():
    """Every dependency appears before the node that depends on it."""
    all_nodes = _topology_nodes()
    dep_graph = {n: NODE_DEPENDENCIES.get(n, []) for n in all_nodes}

    order = _topological_sort(all_nodes, dep_graph)

    assert len(order) == len(all_nodes), (
        f"Topological sort produced {len(order)}/{len(all_nodes)} nodes"
    )
    assert len(set(order)) == len(order), "Duplicate nodes in topological order"

    for node in all_nodes:
        for dep in dep_graph.get(node, []):
            if dep in all_nodes:
                assert order.index(dep) < order.index(node), (
                    f"Dependency {dep} appears after {node} in topological order"
                )


def test_builder_graph_builds():
    from iaglobal.graphs.builder import build_pipeline_from_nodes

    g = build_pipeline_from_nodes()
    assert len(g.nodes) == len(RUN_NODE_NAMES)
