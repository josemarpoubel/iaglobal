"""
Evolution Replay — tests.

Verifies that replay correctly reconstructs per-generation snapshots,
fitness curves, ancestry trees, and diffs from node lineage data.
"""

from iaglobal.graphs.node import Node
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.evolutionengine import EvolutionEngine
from iaglobal.evolution.evolution_replay import (
    EvolutionReplay, ReplaySnapshot, ReplayNode, ReplayDiff,
    GenerationPatch, CORE_NODE_NAMES,
)
from iaglobal.evolution.skills.skill_registry import skill_registry
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
# TESTE 1: EvolutionReplay builds snapshots from engine
# =========================================================================
def test_replay_builds_snapshots():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(3):
            n.record(success=True, latency=0.5)

    replay = EvolutionReplay(graph, engine)
    snaps = replay.snapshots()

    assert len(snaps) >= 1, "Deve ter ao menos 1 snapshot"
    for snap in snaps:
        assert isinstance(snap, ReplaySnapshot)
        assert snap.generation >= 0
        assert snap.evo_count >= 0
        assert snap.core_count >= len(_build_core_graph().nodes)
        assert snap.mean_fitness >= 0.0


# =========================================================================
# TESTE 2: Snapshots include core nodes in every generation
# =========================================================================
def test_snapshots_include_core():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    replay = EvolutionReplay(graph, engine)
    snaps = replay.snapshots()

    for snap in snaps:
        assert "prompt_intake" in snap.nodes
        assert "architect" in snap.nodes
        assert "coder" in snap.nodes


# =========================================================================
# TESTE 3: Fitness curve returns generation-fitness pairs
# =========================================================================
def test_fitness_curve():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(3):
            n.record(success=True, latency=0.5)

    replay = EvolutionReplay(graph, engine)
    curve = replay.fitness_curve()

    assert len(curve) >= 1
    for gen, fit in curve:
        assert isinstance(gen, int)
        assert isinstance(fit, float)
        assert fit >= 0.0


# =========================================================================
# TESTE 4: Ancestry returns ordered chain
# =========================================================================
def test_ancestry():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.5)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(5):
            n.record(success=True, latency=0.5)

    engine._mutate_nodes()

    replay = EvolutionReplay(graph, engine)
    mutants = [n for n in graph.nodes.values() if "_mut_" in n.name]
    if mutants:
        chain = replay.ancestry(mutants[0].name)
        assert isinstance(chain, list)
        assert len(chain) >= 1
        # Last element should be the node itself
        assert chain[-1] == mutants[0].name


# =========================================================================
# TESTE 5: Ancestry tree is ASCII
# =========================================================================
def test_ancestry_tree():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.5)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(5):
            n.record(success=True, latency=0.5)

    engine._mutate_nodes()

    replay = EvolutionReplay(graph, engine)
    evo_names = [n.name for n in graph.nodes.values() if n.name.startswith("evo_")]
    if evo_names:
        tree = replay.ancestry_tree(evo_names[0])
        assert isinstance(tree, str)
        assert len(tree) > 10
        assert evo_names[0] in tree


# =========================================================================
# TESTE 6: Diff detects added/removed nodes
# =========================================================================
def test_diff():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(5):
            n.record(success=True, latency=0.5)

    replay = EvolutionReplay(graph, engine)
    snaps = replay.snapshots()

    if len(snaps) >= 2:
        d = replay.diff(snaps[0].generation, snaps[1].generation)
        assert isinstance(d, ReplayDiff)
        assert d.gen_a == snaps[0].generation
        assert d.gen_b == snaps[1].generation
        summary = d.summary()
        assert isinstance(summary, str)
        assert len(summary) > 10


# =========================================================================
# TESTE 7: Stepper yields snapshots in order
# =========================================================================
def test_stepper():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(3):
            n.record(success=True, latency=0.5)

    replay = EvolutionReplay(graph, engine)
    prev_gen = -1
    count = 0
    for snap in replay.stepper():
        assert snap.generation > prev_gen
        prev_gen = snap.generation
        count += 1
    assert count >= 1


# =========================================================================
# TESTE 8: Full report is human-readable
# =========================================================================
def test_report():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(3):
            n.record(success=True, latency=0.5)

    replay = EvolutionReplay(graph, engine)
    report = replay.report()

    assert isinstance(report, str)
    assert "EVOLUTION REPLAY REPORT" in report
    assert "Fitness Curve" in report
    assert "Per-Generation Summary" in report
    assert "Diffs" in report


# =========================================================================
# TESTE 9: Replay with mutations + crossovers
# =========================================================================
def test_replay_full_cycle():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.5)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(5):
            n.record(success=True, latency=0.5)

    engine._mutate_nodes()
    engine._crossover_phase()

    replay = EvolutionReplay(graph, engine)
    snaps = replay.snapshots()

    assert len(snaps) >= 1
    last = snaps[-1]
    assert last.evo_count >= 0
    assert last.core_count >= 6

    # Verify all nodes in the final snapshot exist in the graph
    for node_name in last.nodes:
        if node_name not in CORE_NODE_NAMES:
            assert node_name in graph.nodes, f"{node_name} nao encontrado no graph"


# =========================================================================
# TESTE 10: Empty graph produces empty report (graceful degradation)
# =========================================================================
def test_empty_graph_replay():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)

    replay = EvolutionReplay(graph, engine)
    snaps = replay.snapshots()
    # Core nodes exist, so we get at least gen 0
    assert len(snaps) >= 1
    report = replay.report()
    assert isinstance(report, str)


# =========================================================================
# TESTE 11: GenerationPatch serialization roundtrip (to_dict / from_dict)
# =========================================================================
def test_generation_patch_roundtrip():
    patch = GenerationPatch(
        from_gen=0, to_gen=1, author="test_author",
        nodes_added={"n1": {"name": "n1", "fitness": 0.9}},
        nodes_removed={"old": {"name": "old", "fitness": 0.3}},
        nodes_modified=[("n2", {"name": "n2", "fitness": 0.4}, {"name": "n2", "fitness": 0.7})],
        strategy_shifts={"n3": ("mutate", "crossover")},
        fitness_before=0.5, fitness_after=0.8,
        diversity_before=2, diversity_after=4,
    )
    d = patch.to_dict()
    assert d["from_gen"] == 0
    assert d["to_gen"] == 1
    assert abs(d["fitness_delta"] - 0.3) < 1e-6
    assert "Gen 0" in d["summary"]

    patch2 = GenerationPatch.from_dict(d)
    assert patch2.from_gen == 0
    assert patch2.to_gen == 1
    assert "n1" in patch2.nodes_added
    assert "old" in patch2.nodes_removed
    assert len(patch2.nodes_modified) == 1
    assert patch2.nodes_modified[0][0] == "n2"


# =========================================================================
# TESTE 12: GenerationPatch JSON serialization
# =========================================================================
def test_generation_patch_json():
    patch = GenerationPatch(
        from_gen=0, to_gen=1,
        fitness_before=0.3, fitness_after=0.6,
        diversity_before=1, diversity_after=3,
    )
    j = patch.to_json()
    assert isinstance(j, str)
    assert "from_gen" in j
    assert "fitness_delta" in j

    patch2 = GenerationPatch.from_json(j)
    assert patch2.from_gen == 0
    assert patch2.to_gen == 1
    assert abs(patch2.fitness_delta - 0.3) < 1e-6
    assert patch2.diversity_delta == 2


# =========================================================================
# TESTE 13: GenerationPatch.apply_to reconstructs next snapshot
# =========================================================================
def test_patch_apply_to():
    snap_a = ReplaySnapshot(generation=0, nodes={
        "evo_001": ReplayNode(
            name="evo_001", strategy="mutate", fitness=0.5,
            event_type="seed", parents=[], created_at=0,
        ),
        "prompt_intake": ReplayNode(
            name="prompt_intake", strategy="prompt_intake", fitness=1.0,
            event_type="core", parents=[], created_at=0,
        ),
    })

    patch = GenerationPatch(
        from_gen=0, to_gen=1,
        nodes_added={
            "evo_002": dict(
                name="evo_002", strategy="crossover", fitness=0.9,
                event_type="crossover", parents=["evo_001"],
                created_at=1, node_type="general", seed_id="",
            ),
        },
        nodes_removed={},
        nodes_modified=[],
        strategy_shifts={},
        fitness_before=0.5, fitness_after=0.9,
    )

    snap_b = patch.apply_to(snap_a)
    assert snap_b.generation == 1
    assert "evo_001" in snap_b.nodes
    assert "evo_002" in snap_b.nodes
    assert "prompt_intake" in snap_b.nodes
    # EVO nodes: evo_001 (0.5) + evo_002 (0.9) → mean=0.7
    assert abs(snap_b.mean_fitness - 0.7) < 1e-6


# =========================================================================
# TESTE 14: patch_apply removes deleted nodes
# =========================================================================
def test_patch_apply_removes_nodes():
    snap_a = ReplaySnapshot(generation=0, nodes={
        "evo_001": ReplayNode(
            name="evo_001", strategy="mutate", fitness=0.5,
            event_type="seed", parents=[], created_at=0,
        ),
        "evo_002": ReplayNode(
            name="evo_002", strategy="mutate", fitness=0.3,
            event_type="seed", parents=[], created_at=0,
        ),
    })

    patch = GenerationPatch(
        from_gen=0, to_gen=1,
        nodes_added={},
        nodes_removed={
            "evo_002": dict(name="evo_002", strategy="mutate", fitness=0.3,
                            event_type="seed", parents=[], created_at=0),
        },
        nodes_modified=[],
        strategy_shifts={},
        fitness_before=0.4, fitness_after=0.5,
    )

    snap_b = patch.apply_to(snap_a)
    assert "evo_001" in snap_b.nodes
    assert "evo_002" not in snap_b.nodes


# =========================================================================
# TESTE 15: EvolutionReplay.diff_patch produces GenerationPatch
# =========================================================================
def test_diff_patch():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.5)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(5):
            n.record(success=True, latency=0.5)

    # Advance generation so mutate creates nodes at gen 1
    engine.generation += 1
    engine._mutate_nodes()

    replay = EvolutionReplay(graph, engine)
    snaps = replay.snapshots()

    if len(snaps) >= 2:
        patch = replay.diff_patch(snaps[0].generation, snaps[1].generation)
        assert isinstance(patch, GenerationPatch)
        assert patch.from_gen == snaps[0].generation
        assert patch.to_gen == snaps[1].generation
        assert patch.fitness_before >= 0
        assert patch.fitness_after >= 0
        assert isinstance(patch.nodes_added, dict)
        assert isinstance(patch.nodes_removed, dict)
        # Summary should be populated
        assert len(patch.summary) > 10


# =========================================================================
# TESTE 16: patch_sequence returns consecutive patches
# =========================================================================
def test_patch_sequence():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.5)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(5):
            n.record(success=True, latency=0.5)

    # Advance generation so mutate creates nodes at gen 1
    engine.generation += 1
    engine._mutate_nodes()

    replay = EvolutionReplay(graph, engine)
    patches = replay.patch_sequence()

    assert isinstance(patches, list)
    assert len(patches) >= 1
    for patch in patches:
        assert isinstance(patch, GenerationPatch)
    # Consecutive: each patch's to_gen == next patch's from_gen
    for i in range(len(patches) - 1):
        assert patches[i].to_gen == patches[i + 1].from_gen


# =========================================================================
# TESTE 17: diff_to_json / diff_from_json static roundtrip
# =========================================================================
def test_diff_to_json_from_json():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.5)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(5):
            n.record(success=True, latency=0.5)

    # Advance generation so mutate creates nodes at gen 1
    engine.generation += 1
    engine._mutate_nodes()

    replay = EvolutionReplay(graph, engine)
    snaps = replay.snapshots()

    if len(snaps) >= 2:
        j = replay.diff_to_json(snaps[0].generation, snaps[1].generation)
        assert isinstance(j, str)
        assert "fitness_delta" in j

        patch = EvolutionReplay.diff_from_json(j)
        assert isinstance(patch, GenerationPatch)
        assert patch.from_gen == snaps[0].generation
        assert patch.to_gen == snaps[1].generation


# =========================================================================
# TESTE 18: ReplayDiff to_dict / from_dict roundtrip
# =========================================================================
def test_replay_diff_serialization():
    rd = ReplayDiff(
        gen_a=0, gen_b=2,
        added=["evo_003", "evo_004"],
        removed=["evo_001"],
        fitness_changes={"evo_002": 0.15},
    )
    d = rd.to_dict()
    assert d["gen_a"] == 0
    assert d["gen_b"] == 2
    assert len(d["added"]) == 2

    rd2 = ReplayDiff.from_dict(d)
    assert rd2.gen_a == 0
    assert rd2.gen_b == 2
    assert "evo_003" in rd2.added
    assert "evo_001" in rd2.removed
