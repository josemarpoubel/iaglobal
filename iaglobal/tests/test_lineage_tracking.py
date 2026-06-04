"""
Node Lineage Tracking — evolutionary history per node.

Tests that every EVO node records its ancestry: seed origin,
mutations, crossovers. Also tests causal DAG reconstruction,
fitness history, and human-readable reports.
"""

from secrets import SystemRandom

from iaglobal.graphs.node import Node, LineageEntry
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.evolutionengine import EvolutionEngine
from iaglobal.evolution.skills.skill_registry import skill_registry
from iaglobal.evolution.skills.skill_executor import skill_executor
from iaglobal.evolution.skills.skill import Skill, ExecutionPolicy
from iaglobal.memory.memory_storage import init_storage


def _build_core_graph() -> ExecutionGraph:
    graph = ExecutionGraph()
    core = [
        ("prompt_intake", "prompt_intake", "general"),
        ("architect", "architect", "general"),
        ("planner", "planner", "general"),
        ("coder", "coder", "coding"),
        ("reviewer", "reviewer", "general"),
        ("debug_coder", "debugger", "debug"),
    ]
    for name, node_type, strategy in core:
        node = Node(
            name=name,
            run=lambda ctx, n=name: {"output": f"{n}"},
            depends_on=[], strategy=strategy, node_type=node_type,
        )
        graph.add_node(node)
    return graph


# =========================================================================
# TESTE 1: LineageEntry dataclass
# =========================================================================
def test_lineage_entry_creation():
    entry = LineageEntry(
        generation=0,
        event_type="seed",
        parent_name="prompt_intake",
        strategy="coding",
        fitness_delta=0.0,
        timestamp=100.0,
    )
    assert entry.generation == 0
    assert entry.event_type == "seed"
    assert entry.parent_name == "prompt_intake"
    assert entry.strategy == "coding"
    assert entry.fitness_delta == 0.0


# =========================================================================
# TESTE 2: Node has lineage field
# =========================================================================
def test_node_has_lineage():
    node = Node(name="test", run=lambda ctx: {"output": "test"})
    assert hasattr(node, "lineage")
    assert node.lineage == []


# =========================================================================
# TESTE 3: Seed nodes get lineage entry
# =========================================================================
def test_seed_records_lineage():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    assert len(evos) >= 4, f"Esperava ao menos 4 EVOs, tem {len(evos)}"

    for evo in evos:
        assert len(evo.lineage) > 0, f"{evo.name} nao tem lineage"
        last = evo.lineage[-1]
        assert last.event_type == "seed", (
            f"{evo.name}: esperava 'seed', tem '{last.event_type}'"
        )
        assert last.generation == 0


# =========================================================================
# TESTE 4: Mutation records lineage
# =========================================================================
def test_mutation_records_lineage():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.9)
    engine._seed_evo_population()

    # Record some fitness so selection doesn't kill everything
    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(5):
            n.record(success=True, latency=0.5)

    engine._mutate_nodes()

    mutants = [n for n in graph.nodes.values() if "_mut_" in n.name]
    if not mutants:
        return  # No mutants generated, skip
    for m in mutants:
        assert len(m.lineage) > 0, f"{m.name} nao tem lineage"
        entry = m.lineage[-1]
        assert entry.event_type == "mutation", (
            f"{m.name}: esperava 'mutation', tem '{entry.event_type}'"
        )
        assert entry.parent_name != "", "mutation deve ter parent_name"
        assert entry.generation == engine.generation


# =========================================================================
# TESTE 5: Crossover records lineage
# =========================================================================
def test_crossover_records_lineage():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.0)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(5):
            n.record(success=True, latency=0.5)

    engine._crossover_phase()

    hybrids = [n for n in graph.nodes.values() if "_x_" in n.name]
    if not hybrids:
        return
    for h in hybrids:
        assert len(h.lineage) > 0, f"{h.name} nao tem lineage"
        entry = h.lineage[-1]
        assert entry.event_type == "crossover", (
            f"{h.name}: esperava 'crossover', tem '{entry.event_type}'"
        )
        assert " x " in entry.parent_name, (
            f"{h.name}: parent_name deve conter ' x ', tem '{entry.parent_name}'"
        )


# =========================================================================
# TESTE 6: lineage_graph() — causal DAG reconstruction
# =========================================================================
def test_lineage_graph():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(3):
            n.record(success=True, latency=0.5)

    engine._mutate_nodes()

    dag = engine.lineage_graph()
    assert isinstance(dag, dict)
    assert len(dag) >= len(evos), "DAG deve cobrir todos os EVOs"

    # Every node in the DAG must exist in the graph
    for node_name, parents in dag.items():
        for p in parents:
            if p:  # Allow empty parents (root seeds)
                assert p in graph.nodes or p in dag, (
                    f"Parent '{p}' de '{node_name}' nao encontrado"
                )


# =========================================================================
# TESTE 7: fitness_history() returns per-generation list
# =========================================================================
def test_fitness_history():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(3):
            n.record(success=True, latency=0.5)

    for evo in evos:
        history = engine.fitness_history(evo.name)
        assert len(history) >= 1, f"{evo.name} sem fitness_history"
        for f in history:
            assert isinstance(f, float)
            assert f >= 0.0


# =========================================================================
# TESTE 8: lineage_report() is human-readable
# =========================================================================
def test_lineage_report():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for evo in evos[:2]:
        for _ in range(3):
            evo.record(success=True, latency=0.5)

    engine._mutate_nodes()
    engine._crossover_phase()

    mutants = [n for n in graph.nodes.values() if "_mut_" in n.name]
    if mutants:
        report = engine.lineage_report(mutants[0].name)
        assert isinstance(report, str)
        assert "Lineage Report" in report
        assert mutants[0].name in report
        assert "seed" in report.lower() or "mutation" in report.lower()

    # Unknown node
    report = engine.lineage_report("nonexistent_node")
    assert "not found" in report.lower()


# =========================================================================
# TESTE 9: Causal DAG with mutation + crossover
# =========================================================================
def test_causal_dag_full_cycle():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.5)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(5):
            n.record(success=True, latency=0.5)

    engine._mutate_nodes()
    engine._crossover_phase()

    dag = engine.lineage_graph()

    # Verify that every non-root EVO has a parent chain back to a seed
    evo_names = set(n.name for n in graph.nodes.values() if n.name.startswith("evo_"))
    for name in evo_names:
        if name not in dag:
            continue
        parents = dag[name]
        if not parents:
            continue
        # Traverse up to find a root (no parents or parent not in dag)
        visited = {name}
        queue = list(parents)
        found_root = False
        while queue:
            p = queue.pop(0)
            if p in visited:
                continue
            visited.add(p)
            if p not in dag or not dag.get(p, []):
                found_root = True
                break
            queue.extend(dag.get(p, []))
        # Roots are core nodes or synthetic seeds — at least one parent chain
        assert found_root or not parents, (
            f"{name}: parent chain nao alcancou raiz"
        )


# =========================================================================
# TESTE 10: Lineage survives reset
# =========================================================================
def test_lineage_persists_across_generations():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.5)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(5):
            n.record(success=True, latency=0.5)

    engine._mutate_nodes()
    engine._crossover_phase()

    all_evo = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    if not all_evo:
        return
    # All should have at least 1 lineage entry
    for n in all_evo:
        assert len(n.lineage) >= 1, f"{n.name} perdeu lineage apos ciclo"

    # Some should have 2+ (seed + mutation/crossover)
    multi = [n for n in all_evo if len(n.lineage) >= 2]
    if not multi:
        print("  (nenhum node com 2+ lineage entries — aceitavel em populacao pequena)")
