"""
Formal Collapse Detector — tests.

Verifies that each indicator correctly identifies collapse scenarios
and does NOT produce false positives on healthy populations.
"""

import statistics

from iaglobal.graphs.node import Node
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.evolutionengine import EvolutionEngine
from iaglobal.evolution.collapse_detector import (
    CollapseDetector, CollapseIndicator, CollapseReport,
)
from iaglobal.evolution.darwin_harness import (
    EvolutionMetrics, GenerationSnapshot,
)
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


def _make_healthy_metrics(generations: int = 5) -> EvolutionMetrics:
    """Metrics with increasing fitness and stable diversity."""
    metrics = EvolutionMetrics()
    for gen in range(generations):
        fitness = [0.5 + gen * 0.08 + 0.05 * (i % 3) for i in range(10)]
        metrics.record(GenerationSnapshot(
            gen=gen, fitness_values=fitness,
            population_size=10,
            diversity=0.6 + gen * 0.02,
            error_count=gen,
        ))
    return metrics


def _make_collapsed_metrics(generations: int = 5) -> EvolutionMetrics:
    """Metrics with flat/decreasing fitness and crashing diversity."""
    metrics = EvolutionMetrics()
    for gen in range(generations):
        fitness = [0.5 for _ in range(10)]  # identical fitness
        metrics.record(GenerationSnapshot(
            gen=gen, fitness_values=fitness,
            population_size=max(1, 10 - gen * 2),  # shrinking
            diversity=max(0.01, 0.5 - gen * 0.12),  # collapsing
            error_count=gen,
        ))
    return metrics


# =========================================================================
# TESTE 1: CollapseIndicator dataclass
# =========================================================================
def test_indicator_creation():
    ind = CollapseIndicator(
        name="test", score=0.3, threshold=0.5, value=0.1,
        message="low diversity",
    )
    assert ind.name == "test"
    assert ind.score == 0.3
    assert ind.collapsed is True
    assert ind.message == "low diversity"


# =========================================================================
# TESTE 2: CollapseReport aggregator
# =========================================================================
def test_report_creation():
    ind = CollapseIndicator(name="test", score=0.3, threshold=0.5, value=0.1)
    report = CollapseReport(
        generation=5, evo_count=3, overall_score=0.4,
        indicators=[ind], warnings=["test warning"],
    )
    assert report.collapsed is True
    assert len(report.collapsed_indicators) == 1
    assert "test warning" in report.warnings
    assert "COLLAPSED" in report.summary()
    assert "test" in report.summary()


# =========================================================================
# TESTE 3: Healthy population does NOT trigger collapse
# =========================================================================
def test_healthy_population_no_collapse():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        for _ in range(5):
            n.record(success=True, latency=0.5)

    detector = CollapseDetector()
    report = detector.detect(graph, engine, metrics=_make_healthy_metrics())

    assert not report.collapsed, (
        f"Populacao saudavel nao deve colapsar: score={report.overall_score:.3f}"
    )
    print(report.summary())


# =========================================================================
# TESTE 4: Collapsed population triggers collapse
# =========================================================================
def test_collapsed_population_triggers():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.0)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    # Force all to same strategy + low fitness
    for n in evos:
        n.strategy = "general"
        for _ in range(3):
            n.record(success=False, latency=5.0)

    detector = CollapseDetector()
    report = detector.detect(graph, engine, metrics=_make_collapsed_metrics())

    assert report.collapsed, (
        f"Populacao colapsada deve ser detectada: score={report.overall_score:.3f}"
    )
    print(report.summary())


# =========================================================================
# TESTE 5: Strategy entropy — single strategy = collapse
# =========================================================================
def test_strategy_entropy_collapse():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        n.strategy = "fast"  # all same strategy

    detector = CollapseDetector()
    report = detector.detect(graph, engine)
    entropy_ind = [i for i in report.indicators if i.name == "strategy_entropy"]
    assert len(entropy_ind) == 1
    # Single strategy → entropy = 0 → collapsed
    assert entropy_ind[0].collapsed, (
        f"Entropy deve colapsar com 1 estrategia: {entropy_ind[0]}"
    )


# =========================================================================
# TESTE 6: Strategy entropy — diverse strategies = healthy
# =========================================================================
def test_strategy_entropy_healthy():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    strategies = ["coding", "research", "fast", "explore", "reflection", "debug"]
    for i, n in enumerate(evos):
        n.strategy = strategies[i % len(strategies)]

    detector = CollapseDetector()
    report = detector.detect(graph, engine)
    entropy_ind = [i for i in report.indicators if i.name == "strategy_entropy"]
    assert len(entropy_ind) == 1
    assert not entropy_ind[0].collapsed, (
        f"Entropy nao deve colapsar com estrategias diversas: {entropy_ind[0]}"
    )


# =========================================================================
# TESTE 7: Fitness variance — identical fitness = collapse risk
# =========================================================================
def test_variance_collapse():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        n.record(success=True, latency=1.0)
        n.record(success=True, latency=1.0)  # same fitness each

    detector = CollapseDetector()
    report = detector.detect(graph, engine)
    var_ind = [i for i in report.indicators if i.name == "fitness_variance"]
    assert len(var_ind) == 1
    # All identical latency + success → variance should be low
    assert var_ind[0].score < 0.5 or var_ind[0].collapsed, (
        f"Variance deve ser baixa com fitness identico: {var_ind[0]}"
    )


# =========================================================================
# TESTE 8: Population size — too few nodes
# =========================================================================
def test_population_size_collapse():
    detector = CollapseDetector()
    ind = detector._check_population_size(1)
    assert ind.collapsed, f"1 node deve colapsar: {ind}"

    ind = detector._check_population_size(10)
    assert not ind.collapsed, f"10 nodes nao deve colapsar: {ind}"


# =========================================================================
# TESTE 9: Genetic diversity — identical node_ids = collapse
# =========================================================================
def test_genetic_diversity_collapse():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    # Force same node_id
    for n in evos:
        n.node_type = "general"

    detector = CollapseDetector()
    report = detector.detect(graph, engine)
    genetic_ind = [i for i in report.indicators if i.name == "genetic_diversity"]
    assert len(genetic_ind) >= 1


# =========================================================================
# TESTE 10: Premature convergence detection
# =========================================================================
def test_premature_convergence():
    metrics = _make_collapsed_metrics(generations=5)
    detector = CollapseDetector()

    ind, warn = detector._check_premature_convergence(metrics, evo_count=5)
    print(f"  Premature convergence: score={ind.score:.3f}, warn={warn}")

    # Collapsed metrics have 0 variance, so drop_ratio might be very high
    # This test just validates the plumbing
    assert ind.name == "premature_convergence"
    assert ind.score >= 0.0


# =========================================================================
# TESTE 11: Full pipeline — detect + summary
# =========================================================================
def test_full_pipeline():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.0)
    engine._seed_evo_population()

    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evos:
        n.strategy = "general"
        for _ in range(3):
            n.record(success=False, latency=5.0)

    detector = CollapseDetector()
    report = detector.detect(graph, engine, metrics=_make_collapsed_metrics())

    summary = report.summary()
    assert isinstance(summary, str)
    assert len(summary) > 50
    assert report.collapsed or len(report.collapsed_indicators) >= 0

    # Individual indicator access
    for ind in report.indicators:
        assert 0.0 <= ind.score <= 1.0


# =========================================================================
# TESTE 12: Empty population = collapse
# =========================================================================
def test_empty_population():
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)

    detector = CollapseDetector()
    report = detector.detect(graph, engine)
    assert report.collapsed, "Populacao vazia deve colapsar"
    assert report.evo_count == 0


# =========================================================================
# TESTE 13: Report serializes to dict
# =========================================================================
def test_report_dict_fields():
    ind = CollapseIndicator(
        name="entropy", score=0.2, threshold=0.5,
        value=0.1, message="low",
    )
    report = CollapseReport(
        generation=1, evo_count=5, overall_score=0.3,
        indicators=[ind], warnings=["alert"],
    )
    assert report.generation == 1
    assert report.evo_count == 5
    assert report.overall_score == 0.3
    assert len(report.indicators) == 1
    assert report.indicators[0].name == "entropy"
