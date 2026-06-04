"""
Teste de Integração Fim-a-Fim — Evolution Lab.

Executa o ciclo completo sem mocks:
  init → evolve → replay → diff → detect-collapse → export-json

Valida que todos os componentes do Evolution Lab funcionam juntos.
"""

import json
import tempfile

from iaglobal.graphs.node import Node
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.evolutionengine import EvolutionEngine
from iaglobal.evolution.evolution_replay import EvolutionReplay, GenerationPatch
from iaglobal.evolution.collapse_detector import CollapseDetector
from iaglobal.evolution.skills.skill_registry import skill_registry
from iaglobal.memory.memory_storage import init_storage


def _build_test_graph() -> ExecutionGraph:
    graph = ExecutionGraph()
    core_names = ["prompt_intake", "architect", "planner", "coder", "reviewer"]
    for name in core_names:
        node = Node(
            name=name,
            run=lambda ctx, n=name: {"output": n, "success": True},
            depends_on=[], strategy=name, node_type=name,
        )
        graph.add_node(node)
    return graph


def _record_all(engine: EvolutionEngine, times: int = 3):
    for node in engine.graph.nodes.values():
        if node.name.startswith("evo_") or "_mut_" in node.name or "_x_" in node.name:
            for _ in range(times):
                node.record(success=True, latency=0.5)


def test_full_evolution_lab_cycle():
    """Ciclo completo: init → evolve → replay → diff → detect-collapse → export."""
    init_storage(clear=True)
    skill_registry.clear()

    # ── 1. INIT ──
    graph = _build_test_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.5)
    engine._seed_evo_population()
    _record_all(engine, 5)
    evo_count = len([n for n in graph.nodes if n.startswith("evo_")])
    assert evo_count >= 1, "Deve ter ao menos 1 EVO seed"
    core_count = len([n for n in graph.nodes if n in {
        "prompt_intake", "architect", "planner", "coder", "reviewer",
    }])
    assert core_count == 5, f"Esperado 5 core, got {core_count}"
    assert engine.generation >= 0

    # ── 2. EVOLVE (mutation) ──
    # Advance generation so mutants are recorded at gen 1
    engine.generation += 1
    engine._mutate_nodes()
    _record_all(engine, 5)

    # ── 3. REPLAY ──
    replay = EvolutionReplay(graph, engine)
    snaps = replay.snapshots()
    assert len(snaps) >= 1, "Replay deve produzir ao menos 1 snapshot"
    for snap in snaps:
        assert snap.generation >= 0
        assert snap.evo_count >= 0
        assert snap.core_count == core_count
        assert snap.mean_fitness >= 0.0

    # ── 4. FITNESS CURVE ──
    curve = replay.fitness_curve()
    assert len(curve) >= 1
    for gen, fit in curve:
        assert isinstance(gen, int)
        assert isinstance(fit, float)

    # ── 5. DIFF ──
    if len(snaps) >= 2:
        diff = replay.diff(snaps[0].generation, snaps[1].generation)
        assert diff.gen_a == snaps[0].generation
        assert diff.gen_b == snaps[1].generation
        assert isinstance(diff.summary(), str)
        assert len(diff.summary()) > 10

        # Git-style patch
        patch = replay.diff_patch(snaps[0].generation, snaps[1].generation)
        assert isinstance(patch, GenerationPatch)
        assert patch.from_gen == diff.gen_a
        assert patch.to_gen == diff.gen_b
        # Validate patch is JSON-serializable
        j = patch.to_json()
        patch2 = GenerationPatch.from_json(j)
        assert patch2.from_gen == patch.from_gen
        assert patch2.to_gen == patch.to_gen
        assert abs(patch2.fitness_delta - patch.fitness_delta) < 1e-6

    # ── 6. PATCH SEQUENCE ──
    patches = replay.patch_sequence()
    if len(patches) >= 2:
        for i in range(len(patches) - 1):
            assert patches[i].to_gen == patches[i + 1].from_gen

    # ── 7. ANCESTRY ──
    evo_names = [n.name for n in graph.nodes.values() if n.name.startswith("evo_")]
    if evo_names:
        chain = replay.ancestry(evo_names[0])
        assert isinstance(chain, list)
        assert len(chain) >= 1
        assert chain[-1] == evo_names[0]
        tree = replay.ancestry_tree(evo_names[0])
        assert isinstance(tree, str)
        assert len(tree) > 10

    # ── 8. STEPPER ──
    gen_order = [snap.generation for snap in replay.stepper()]
    assert gen_order == sorted(gen_order)

    # ── 9. REPORT ──
    report = replay.report()
    assert isinstance(report, str)
    assert "EVOLUTION REPLAY REPORT" in report
    assert "Fitness Curve" in report
    assert "Diffs" in report

    # ── 10. COLLAPSE DETECTOR ──
    detector = CollapseDetector()
    report_collapse = detector.detect(graph, engine)
    assert report_collapse.overall_score >= 0.0
    assert report_collapse.overall_score <= 1.0
    assert len(report_collapse.indicators) >= 1
    summary = report_collapse.summary() if hasattr(report_collapse, 'summary') else str(report_collapse)
    assert isinstance(summary, str)
    assert len(summary) > 10

    # ── 11. EXPORT JSON ──
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name
        data = [p.to_dict() for p in patches]
        json.dump(data, f, indent=2, default=str)
    with open(path) as f:
        loaded = json.load(f)
    assert isinstance(loaded, list)
    if patches:
        assert len(loaded) == len(patches)
        assert "from_gen" in loaded[0]
        assert "fitness_delta" in loaded[0]

    # ── 12. FULL CYCLE WITH CROSSOVER ──
    # One more generation with crossover
    engine.generation += 1
    engine._crossover_phase()
    _record_all(engine, 5)

    replay2 = EvolutionReplay(graph, engine)
    snaps2 = replay2.snapshots()
    assert len(snaps2) >= len(snaps), "Crossover deve adicionar geracoes"

    patches2 = replay2.patch_sequence()
    assert len(patches2) >= len(patches), "Crossover deve adicionar patches"

    # All patches must be valid
    for p in patches2:
        assert isinstance(p, GenerationPatch)
        assert p.from_gen >= 0
        assert p.to_gen >= 0
        assert p.to_gen > p.from_gen
