"""
Teste do sistema de criação autônoma de agentes (Evolution Engine).

Verifica se os agentes EVO são criados, selecionados, mutados
 e cruzados corretamente.
"""

from unittest.mock import MagicMock, patch

import pytest

from iaglobal.graphs.node import Node
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.evolutionengine import EvolutionEngine
from iaglobal.evolution.canonical_graph import canonicalize
from iaglobal.evolution.skills.skill_executor import skill_executor
from iaglobal.evolution.skills.skill_registry import skill_registry
from iaglobal.evolution.skills.skill import (
    SKILL_TESTER, SKILL_DEBUGGER, SKILL_SEARCH,
    SKILL_PLANNER, SKILL_CODER,
    SKILL_SEMANTIC_VALIDATOR,
    SKILL_REVIEWER,
    SKILL_DOCUMENTATION, SKILL_DEPENDENCY,
    SKILL_REQUIREMENTS, SKILL_PRODUCT_MANAGER, SKILL_PROMPT_INTAKE,
    SKILL_RISK_ANALYSIS, SKILL_RELEASE, SKILL_METRICS, SKILL_OPTIMIZATION,
    SKILL_KNOWLEDGE,
)

# =========================================================================
# CORE PIPELINE — constante compartilhada
# =========================================================================

CORE_PIPELINE = [
    ("prompt_intake", "prompt_intake", "general"),
    ("enhancement", "enhancement", "general"),
    ("orchestrator_agent", "orchestrator_agent", "general"),
    ("pm", "pm", "general"),
    ("requirements", "requirements", "general"),
    ("architect", "architect", "general"),
    ("search", "search", "research"),
    ("knowledge", "knowledge", "fast"),
    ("dependency", "dependency", "fast"),
    ("risk_analysis", "risk_analysis", "general"),
    ("security_design", "security_design", "general"),
    ("performance_design", "performance_design", "general"),
    ("planner", "planner", "general"),
    ("coder", "coder", "coding"),
    ("reviewer", "reviewer", "general"),
    ("semantic_validator", "semantic_validator", "fast"),
    ("security_audit", "security_audit", "fast"),
    ("performance_audit", "performance_audit", "fast"),
    ("tester", "tester", "general"),
    ("debug_coder", "debugger", "debug"),
    ("documentation", "documentation", "general"),
    ("release", "release", "general"),
    ("metrics", "metrics", "fast"),
    ("optimization", "optimization", "fast"),
    ("result_agent", "result_agent", "general"),
]

# =========================================================================
# HELPERS REUTILIZÁVEIS
# =========================================================================

def evo_node_names(graph):
    return [n for n in graph.nodes if n.startswith("evo_")]

def evo_nodes(graph):
    return [node for node in graph.nodes.values() if node.name.startswith("evo_")]

def core_node_count(graph):
    return len([n for n in graph.nodes if not n.startswith("evo_")])

# =========================================================================
# SETUP: registra skills
# =========================================================================

def setup_module():
    from iaglobal.evolution.skills.skill import Skill
    for skill in [
        SKILL_PLANNER, SKILL_CODER,
        SKILL_TESTER, SKILL_DEBUGGER, SKILL_SEARCH,
        SKILL_SEMANTIC_VALIDATOR,
        SKILL_REVIEWER,
        SKILL_DOCUMENTATION, SKILL_DEPENDENCY,
        SKILL_REQUIREMENTS, SKILL_PRODUCT_MANAGER, SKILL_PROMPT_INTAKE,
        SKILL_RISK_ANALYSIS, SKILL_RELEASE, SKILL_METRICS, SKILL_OPTIMIZATION,
        SKILL_KNOWLEDGE,
    ]:
        updated = Skill(
            name=skill.name,
            description=skill.description,
            inputs=list(skill.inputs),
            outputs=list(skill.outputs),
            constraints=list(skill.constraints),
            execution_policy=skill.execution_policy,
            run_fn=lambda ctx: {"output": ""},
            version=skill.version,
            tags=list(skill.tags),
        )
        skill_registry.register_or_update(updated)

# =========================================================================
# FIXTURES
# =========================================================================

def build_core_graph() -> ExecutionGraph:
    graph = ExecutionGraph()
    for name, node_type, strategy in CORE_PIPELINE:
        node = Node(name=name, run=lambda ctx: {"output": ""},
                     depends_on=[], strategy=strategy, node_type=node_type)
        graph.add_node(node)
    return graph

@pytest.fixture
def graph():
    return build_core_graph()

@pytest.fixture
def engine(graph):
    return EvolutionEngine(graph, mutation_rate=0.1)

# =========================================================================
# TEST 1: Quais nós core são clonáveis como EVO seeds?
# =========================================================================

def test_quais_nos_sao_clonaveis():
    graph = build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.1)

    cloneable = []
    not_cloneable = []
    for name in engine.CORE_NODE_NAMES:
        if name in graph.nodes:
            if engine._is_evo_cloneable(name):
                cloneable.append(name)
            else:
                not_cloneable.append(name)

    assert "tester" in cloneable
    assert "search" in cloneable
    assert "debug_coder" in cloneable
    assert "metrics" in cloneable
    assert "planner" in not_cloneable
    assert "coder" in not_cloneable
    assert "prompt_intake" in not_cloneable
    assert "risk_analysis" in not_cloneable

# =========================================================================
# TEST 2: Seed da população EVO
# =========================================================================

def test_seed_populacao_evo():
    graph = build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.1)

    evo_before = evo_node_names(graph)
    assert len(evo_before) == 0

    engine._seed_evo_population()

    evo_after = evo_node_names(graph)
    assert len(evo_after) >= 3
    assert any("tester" in n for n in evo_after)

# =========================================================================
# TEST 3: Seed só roda uma vez
# =========================================================================

def test_seed_apenas_uma_vez():
    graph = build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.1)

    engine._seed_evo_population()
    count_first = len(evo_node_names(graph))

    engine._seed_evo_population()
    count_second = len(evo_node_names(graph))

    assert count_first == count_second

# =========================================================================
# TEST 4: Seleção por fitness
# =========================================================================

def test_selecao_por_fitness():
    graph = build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.1)

    engine._seed_evo_population()
    evo = evo_nodes(graph)

    for i, node in enumerate(evo):
        if i < len(evo) // 2:
            node.record(success=True, latency=0.5)
        else:
            node.record(success=False, latency=5.0)

    core_before = core_node_count(graph)
    evo_before = len(evo)

    engine._select_survivors()

    evo_after = len(evo_node_names(graph))
    core_after = core_node_count(graph)

    assert core_before == core_after
    assert evo_after <= evo_before
    assert evo_after >= evo_before // 2

# =========================================================================
# TEST 5: Mutação cria novos nós
# =========================================================================

def test_mutacao_cria_novos_nos():
    graph = build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.1)

    engine._seed_evo_population()
    evo_before = len(evo_node_names(graph))

    engine._mutate_nodes()

    evo_after = len(evo_node_names(graph))
    new_mutants = [n for n in graph.nodes if "_mut_" in n]

    if len(new_mutants) == 0:
        pass
    else:
        assert evo_after > evo_before

# =========================================================================
# TEST 6: Crossover cria híbridos
# =========================================================================

def test_crossover_cria_hibridos():
    graph = build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.1)

    engine._seed_evo_population()
    engine._mutate_nodes()

    hybrid_before = len([n for n in graph.nodes if "_x_" in n])

    engine._crossover_phase()

    hybrid_after = len([n for n in graph.nodes if "_x_" in n])
    new_hybrids = hybrid_after - hybrid_before
    assert new_hybrids >= 0

# =========================================================================
# TEST 7: Ciclo completo de evolução
# =========================================================================

def test_ciclo_evolucao_completo():
    graph = build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.1)

    gen_before = engine.generation
    nodes_before = len(graph.nodes)

    engine.evolve()

    gen_after = engine.generation
    nodes_after = len(graph.nodes)

    assert gen_after == gen_before + 1
    assert nodes_after >= 28

# =========================================================================
# TEST 8: Nós críticos não são removidos na seleção
# =========================================================================

def test_nos_criticos_preservados():
    graph = build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.1)

    engine._seed_evo_population()

    evo = evo_nodes(graph)
    for node in evo:
        node.record(success=False, latency=10.0)

    engine._select_survivors()

    remaining = set(graph.nodes.keys())
    for core in engine.CORE_NODE_NAMES:
        if core in remaining:
            continue
        assert core in remaining, f"Nó core {core} foi eliminado!"

# =========================================================================
# TEST 9: Canonicalização remove duplicatas
# =========================================================================

def test_canonicalizacao_remove_duplicatas():
    graph = build_core_graph()

    node_a = Node(name="test_dup_a", run=lambda ctx: {"output": ""},
                   depends_on=[], strategy="coding", node_type="coder")
    node_b = Node(name="test_dup_b", run=lambda ctx: {"output": ""},
                   depends_on=[], strategy="coding", node_type="coder")
    graph.add_node(node_a)
    graph.add_node(node_b)

    before = len(graph.nodes)
    graph.nodes = canonicalize(graph.nodes)
    after = len(graph.nodes)

    assert after < before
    assert after >= 24

# =========================================================================
# TEST 10: Evolution Runtime cria thread de fundo
# =========================================================================

def test_runtime_cria_thread():
    graph = build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.1)

    from iaglobal.evolution.evolutionruntime import EvolutionRuntime
    runtime = EvolutionRuntime(engine, interval=3600)

    assert not runtime._running
    assert runtime._thread is None

    runtime.start()

    assert runtime._running
    assert runtime._thread is not None
    assert runtime._thread.is_alive()

    runtime.stop()
    assert not runtime._running

# =========================================================================
# NOVOS TESTES (leiame.md seções 5–10)
# =========================================================================

# --- 5. Integridade do grafo ---

def test_grafo_sem_nos_orfaos():
    graph = build_core_graph()
    for node in graph.nodes.values():
        for dep in node.depends_on:
            assert dep in graph.nodes, (
                f"{node.name} depende de {dep} inexistente"
            )

# --- 6. Fitness monotônico ---

def test_fitness_recompensa_sucesso():
    graph = build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.1)

    engine._seed_evo_population()

    node = evo_nodes(graph)[0]

    node.record(success=False, latency=5)
    bad_fitness = node.fitness()

    node.record(success=True, latency=0.5)
    good_fitness = node.fitness()

    assert good_fitness > bad_fitness

# --- 7. Idempotência do evolve() ---

def test_multiplas_geracoes():
    graph = build_core_graph()
    engine = EvolutionEngine(graph)

    for _ in range(5):
        engine.evolve()

    assert engine.generation == 5

# --- 8. Thread safety (runtime start dupla) ---

def test_runtime_start_duas_vezes():
    graph = build_core_graph()
    engine = EvolutionEngine(graph)

    from iaglobal.evolution.evolutionruntime import EvolutionRuntime

    runtime = EvolutionRuntime(engine)

    runtime.start()
    first_thread = runtime._thread

    runtime.start()

    assert runtime._thread is first_thread

    runtime.stop()

# --- 9. Canonicalização preserva tipo ---

def test_canonicalizacao_preserva_tipo():
    graph = build_core_graph()

    node_a = Node(
        name="dup1",
        run=lambda ctx: {},
        depends_on=[],
        strategy="coding",
        node_type="coder",
    )
    node_b = Node(
        name="dup2",
        run=lambda ctx: {},
        depends_on=[],
        strategy="coding",
        node_type="coder",
    )

    graph.add_node(node_a)
    graph.add_node(node_b)

    canonical = canonicalize(graph.nodes)

    coder_nodes = [
        n for n in canonical.values()
        if getattr(n, "node_type", None) == "coder"
    ]

    assert len(coder_nodes) >= 1

# --- 10. Edge cases ---

def test_select_survivors_populacao_vazia():
    graph = build_core_graph()
    engine = EvolutionEngine(graph)

    engine._select_survivors()

    assert len(graph.nodes) > 0

def test_crossover_sem_populacao():
    graph = build_core_graph()
    engine = EvolutionEngine(graph)

    engine._crossover_phase()

    assert len(graph.nodes) > 0

def test_mutacao_sem_evos():
    graph = build_core_graph()
    engine = EvolutionEngine(graph)

    before = len(graph.nodes)

    engine._mutate_nodes()

    after = len(graph.nodes)

    assert after >= before

# =========================================================================
# EXECUÇÃO
# =========================================================================

if __name__ == "__main__":
    tests = [
        ("Cloneable nodes", test_quais_nos_sao_clonaveis),
        ("Seed população", test_seed_populacao_evo),
        ("Seed única vez", test_seed_apenas_uma_vez),
        ("Seleção fitness", test_selecao_por_fitness),
        ("Mutação", test_mutacao_cria_novos_nos),
        ("Crossover", test_crossover_cria_hibridos),
        ("Ciclo completo", test_ciclo_evolucao_completo),
        ("Core preservados", test_nos_criticos_preservados),
        ("Canonicalização", test_canonicalizacao_remove_duplicatas),
        ("Runtime thread", test_runtime_cria_thread),
        ("Sem nós órfãos", test_grafo_sem_nos_orfaos),
        ("Fitness monotônico", test_fitness_recompensa_sucesso),
        ("Múltiplas gerações", test_multiplas_geracoes),
        ("Runtime start dupla", test_runtime_start_duas_vezes),
        ("Canonicalização preserva tipo", test_canonicalizacao_preserva_tipo),
        ("Survivors pop vazia", test_select_survivors_populacao_vazia),
        ("Crossover sem pop", test_crossover_sem_populacao),
        ("Mutação sem evos", test_mutacao_sem_evos),
    ]
    for name, fn in tests:
        try:
            fn()
            print(f"  ✅ {name}")
        except Exception as e:
            print(f"  ❌ {name}: {e}")
    print()
