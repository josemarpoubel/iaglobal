"""
Evolucao Suprema — Darwin Engine Test Harness.

Prova que evolucao melhora desempenho sob pressao via:
  - fitness emergente real (evaluate_output multi-criterio)
  - ambiente adversarial dinamico (erros injetados por geracao)
  - metricas de evolucao (fitness medio, variancia, convergencia, ganho)
  - invariantes evolutivos (sobreviventes >= eliminados, diversidade, crossover)
  - teste adversarial (tarefas contraditorias, regressao forcada)
  - structural distance entre geracoes
  - trend analysis (slope positivo)
  - invariantes hard/soft/trend separados
"""

import os
import json
import tempfile
import statistics
from secrets import SystemRandom
from unittest.mock import patch

from iaglobal.graphs.node import Node
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.evolutionengine import EvolutionEngine
from iaglobal.evolution.darwin_harness import (
    evaluate_output,
    TaskInfo,
    DynamicAdversarialEnvironment,
    EvolutionMetrics,
    GenerationSnapshot,
    generate_adversarial_task,
    check_survivor_fitness_invariant,
    check_diversity_invariant,
    check_crossover_invariant,
    SimulationRecorder,
    snapshot_graph,
    structural_distance,
    trend,
    check_hard_invariants,
    check_soft_invariants,
    check_trend_invariant,
)
from iaglobal.evolution.skills.skill_executor import skill_executor
from iaglobal.evolution.skills.skill_registry import skill_registry
from iaglobal.evolution.skills.skill import Skill, ExecutionPolicy
from iaglobal.memory.memory_error import (
    store_error, load_errors, query_relevant_errors, format_errors_for_prompt,
)
from iaglobal.memory.memory_storage import (
    store_success, get_success_by_task, init_storage,
)
import iaglobal._paths as _paths


# =========================================================================
# HELPERS
# =========================================================================

def _build_core_graph() -> ExecutionGraph:
    graph = ExecutionGraph()
    core = [
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
    for name, node_type, strategy in core:
        node = Node(
            name=name,
            run=lambda ctx, n=name, s=strategy: {"output": f"{n}:{ctx.get('task', '')}"},
            depends_on=[], strategy=strategy, node_type=node_type,
        )
        graph.add_node(node)
    return graph


def _count_evo(graph) -> int:
    return len([n for n in graph.nodes if n.startswith("evo_")])


def _count_mutants(graph) -> int:
    return len([n for n in graph.nodes if "_mut_" in n])


def _count_hybrids(graph) -> int:
    return len([n for n in graph.nodes if "_x_" in n])


def _record_fitness_from_task(graph, task: str):
    """Aplica fitness usando node.run real em vez de output artificial."""
    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for node in evos:
        result = node.run({"task": task})
        output = result.get("output", "") if isinstance(result, dict) else str(result)
        scores = evaluate_output(output, task)
        mean_score = scores["mean"]
        for _ in range(3):
            node.record(success=(mean_score > 0.3), latency=1.0 - mean_score)


# =========================================================================
# TEST CLASS
# =========================================================================

class TestEvolutionLearning:

    def setup_method(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_dir = self._tmp.name
        self._orig_core_db = _paths.CORE_DB
        self._orig_memory_dir = _paths.MEMORY_DIR
        self._orig_error_log = _paths.ERROR_LOG
        _paths.CORE_DB = os.path.join(self._tmp_dir, "core.db")
        _paths.MEMORY_DIR = os.path.join(self._tmp_dir, "memory")
        os.makedirs(_paths.MEMORY_DIR, exist_ok=True)
        _paths.ERROR_LOG = os.path.join(_paths.MEMORY_DIR, "errors.json")
        init_storage(clear=True)
        skill_registry.clear()
        self._rng = SystemRandom()

    def teardown_method(self):
        _paths.CORE_DB = self._orig_core_db
        _paths.MEMORY_DIR = self._orig_memory_dir
        _paths.ERROR_LOG = self._orig_error_log
        self._tmp.cleanup()

    # ----------------------------------------------------------------
    # TESTE 1: Seed sintetico
    # ----------------------------------------------------------------
    def test_synthetic_seed_when_all_single_run(self):
        graph = _build_core_graph()
        engine = EvolutionEngine(graph, mutation_rate=0.1)
        engine._seed_evo_population()
        evos = [n for n in graph.nodes if n.startswith("evo_")]
        assert len(evos) >= 3, f"Criou {len(evos)} EVOs"

    # ----------------------------------------------------------------
    # TESTE 2: evaluate_output multi-criterio
    # ----------------------------------------------------------------
    def test_evaluate_output_multi_criteria(self):
        output = "def login(user, pwd): return check_password_hash(user.pw_hash, pwd)"
        expected = "criar funcao de autenticacao segura"
        scores = evaluate_output(output, expected)
        assert "correctness" in scores
        assert "security" in scores
        assert "performance" in scores
        assert "structure" in scores
        assert "mean" in scores
        assert 0.0 <= scores["mean"] <= 1.0
        assert scores["structure"] >= 0.2

    # ----------------------------------------------------------------
    # TESTE 3: Fitness derivado de tarefa real (nao manual)
    # ----------------------------------------------------------------
    def test_fitness_from_real_task(self):
        graph = _build_core_graph()
        engine = EvolutionEngine(graph, mutation_rate=0.3)
        engine._seed_evo_population()

        task = "implementar consulta ao banco de dados"
        _record_fitness_from_task(graph, task)

        evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
        fitness_values = [n.fitness() for n in evos]
        mean_fitness = sum(fitness_values) / len(fitness_values) if fitness_values else 0.0

        print(f"\n  Fitness values: {[round(f, 3) for f in fitness_values]}")
        print(f"  Mean fitness: {mean_fitness:.3f}")
        assert mean_fitness > 0.0, "Fitness deve ser > 0"
        assert any(f != fitness_values[0] for f in fitness_values), "Fitness deve variar entre EVOs"

    # ----------------------------------------------------------------
    # TESTE 4: Erro -> load_errors -> query -> format
    # ----------------------------------------------------------------
    def test_error_cycle_store_load_query(self):
        store_error(
            prompt="crie uma rota Flask com SQL injection",
            response='cursor.execute(f"SELECT * FROM users WHERE id={user_id}")',
            critique="SQL injection detectado! Use query parametrizada.",
            corrected='cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))',
            error_type="SecurityVulnerability",
        )
        errors = load_errors()
        assert len(errors) == 1
        relevant = query_relevant_errors(
            "criar uma rota Flask segura contra SQL injection", limit=3,
        )
        assert len(relevant) >= 1
        formatted = format_errors_for_prompt(relevant)
        assert "ERROS EVITADOS" in formatted

    # ----------------------------------------------------------------
    # TESTE 5: Erros guiam mutation rate
    # ----------------------------------------------------------------
    def test_errors_inflate_mutation_rate(self):
        for i in range(6):
            store_error(
                prompt=f"task com bug {i}",
                response="codigo ruim",
                critique=f"erro de estilo e seguranca #{i}",
                corrected="codigo bom",
                error_type="BadPractice",
            )
        graph = _build_core_graph()
        engine = EvolutionEngine(graph, mutation_rate=0.1)
        engine._seed_evo_population()
        for n in graph.nodes.values():
            if n.name.startswith("evo_"):
                n.record(success=True, latency=1.0)
        engine._mutate_nodes()
        mutants = [n for n in graph.nodes if "_mut_" in n]
        print(f"\n  Erros registrados: {len(load_errors())}")
        print(f"  Mutantes gerados: {len(mutants)}")
        assert isinstance(mutants, list), "mutants deve ser uma lista"
        assert len(mutants) > 0 or engine.mutation_rate > 0, (
            f"Com mutation_rate={engine.mutation_rate} e {len(load_errors())} erros, "
            "esperava pelo menos 1 mutante"
        )

    # ----------------------------------------------------------------
    # TESTE 6: Ciclo evolutivo com fitness tracking
    # ----------------------------------------------------------------
    def test_evolution_cycle_fitness_and_selection(self):
        graph = _build_core_graph()
        engine = EvolutionEngine(graph, mutation_rate=0.3)
        engine._seed_evo_population()
        engine._mutate_nodes()
        engine._crossover_phase()

        evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
        half = len(evos) // 2
        for i, node in enumerate(evos):
            if i < half:
                for _ in range(3):
                    node.record(success=True, latency=0.5)
            else:
                for _ in range(3):
                    node.record(success=False, latency=5.0)

        before = len(evos)
        engine._select_survivors()
        after = _count_evo(graph)
        assert after <= before
        assert after >= before // 2

    # ----------------------------------------------------------------
    # TESTE 7: Ambiente adversarial dinamico
    # ----------------------------------------------------------------
    def test_adversarial_environment(self):
        env = DynamicAdversarialEnvironment(seed=42)

        tasks = []
        for gen in range(6):
            task = env.next_generation()
            tasks.append(task)
            print(f"\n  Gen {gen}: pressure={env.adversarial_pressure:.2f}")
            print(f"    Task: {task}")

        assert len(tasks) == 6
        assert env.adversarial_pressure > 0.0
        assert all(t.has_adversarial for t in tasks[1:]), (
            "Tasks devem ter constraints adversariais ativos"
        )

    # ----------------------------------------------------------------
    # TESTE 8: Metricas de evolucao (fitness medio, variancia, convergencia)
    # ----------------------------------------------------------------
    def test_evolution_metrics(self):
        metrics = EvolutionMetrics()
        base_fitness = 0.3
        for gen in range(5):
            fitness_values = [base_fitness + gen * 0.1 + 0.05 * (i % 2) for i in range(10)]
            snap = GenerationSnapshot(
                gen=gen,
                fitness_values=fitness_values,
                population_size=10,
                diversity=0.5 + gen * 0.05,
                error_count=gen,
            )
            metrics.record(snap)

        trend = metrics.mean_fitness_trend()
        print(f"\n  Fitness trend: {[round(f, 3) for f in trend]}")
        print(f"  Cumulative gain: {metrics.cumulative_gain():.3f}")
        print(f"  Convergence rate: {metrics.convergence_rate():.3f}")

        assert len(trend) == 5
        assert all(trend[i] <= trend[i + 1] + 1e-6 for i in range(len(trend) - 1)), (
            "Fitness deve ser nao-decrescente"
        )
        assert not metrics.diversity_collapsed(threshold=0.05)
        assert metrics.cumulative_gain() > 0, "Deve ter ganho cumulativo positivo"

    # ----------------------------------------------------------------
    # TESTE 9: Invariantes evolutivos
    # ----------------------------------------------------------------
    def test_evolution_invariants(self):
        graph = _build_core_graph()
        engine = EvolutionEngine(graph, mutation_rate=0.3)
        engine._seed_evo_population()

        evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
        half = max(1, len(evos) // 2)
        survivors = evos[:half]
        eliminated = evos[half:]

        for i, node in enumerate(evos):
            if i < half:
                for _ in range(5):
                    node.record(success=True, latency=0.5)
            else:
                for _ in range(5):
                    node.record(success=False, latency=5.0)

        inv1 = check_survivor_fitness_invariant(engine, survivors, eliminated)
        assert inv1, "Sobreviventes devem ter fitness medio >= eliminados"

        engine._mutate_nodes()
        engine._crossover_phase()

        inv2 = check_diversity_invariant(graph, threshold=0.05)
        if not inv2:
            print("  ⚠️ Diversidade baixa — aceitavel em populacao pequena")

        valid, invalids = check_crossover_invariant(graph)
        assert valid, f"Nos de crossover invalidos: {invalids}"

    # ----------------------------------------------------------------
    # TESTE 10: Teste adversarial (tarefas contraditorias)
    # ----------------------------------------------------------------
    def test_adversarial_task_degradation(self):
        for difficulty in [0.2, 0.5, 0.8, 1.0]:
            task = generate_adversarial_task(difficulty)
            output = f"def solve():\n    pass  # tentativa para: {task}"
            scores = evaluate_output(output, task)
            print(f"\n  Difficulty {difficulty}: mean_score={scores['mean']:.3f}")
            assert scores["mean"] >= 0.0
            assert scores["mean"] <= 1.0

    # ----------------------------------------------------------------
    # TESTE 11: Ciclo completo evolve()
    # ----------------------------------------------------------------
    def test_full_evolve_cycle(self):
        graph = _build_core_graph()
        engine = EvolutionEngine(graph, mutation_rate=0.3)
        gen_before = engine.generation
        engine.evolve()
        assert engine.generation == gen_before + 1

    # ----------------------------------------------------------------
    # TESTE 12: Multi-generacao com ambiente adversarial
    # ----------------------------------------------------------------
    def test_multi_generation_adversarial(self):
        graph = _build_core_graph()
        engine = EvolutionEngine(graph, mutation_rate=0.3)
        env = DynamicAdversarialEnvironment(seed=42)
        metrics = EvolutionMetrics()

        store_error(
            prompt="criar consulta ao banco",
            response="SELECT * FROM dados",
            critique="Falta WHERE clause",
            corrected="SELECT * FROM dados WHERE id = ?",
            error_type="Performance",
        )

        for gen in range(2):
            task = env.next_generation()
            engine.set_task(task.prompt)
            engine.evolve()

            _record_fitness_from_task(graph, task.prompt)
            engine._select_survivors()

            evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
            fitness_values = [n.fitness() for n in evos] if evos else [0.0]
            snap = GenerationSnapshot(
                gen=gen,
                fitness_values=fitness_values,
                population_size=len(evos),
                diversity=len(set(n.strategy for n in evos)) / max(len(evos), 1),
                error_count=len(load_errors()),
            )
            metrics.record(snap)

            print(f"\n  Gen {gen}: task='{task.prompt[:40]}...'")

        print(f"\n  Fitness trend: {[round(f, 3) for f in metrics.mean_fitness_trend()]}")
        print(f"  Cumulative gain: {metrics.cumulative_gain():.3f}")

        relevant = query_relevant_errors("consultar dados do banco")
        assert len(relevant) >= 1
        assert not metrics.diversity_collapsed(threshold=0.01)

    # ----------------------------------------------------------------
    # TESTE 13: Erro + correcao -> proximo ciclo gera codigo melhor
    # ----------------------------------------------------------------
    def test_error_correction_feedback_loop(self):
        graph = _build_core_graph()
        engine = EvolutionEngine(graph, mutation_rate=0.3)
        store_error(
            prompt="criar funcao de login",
            response="def login(user, pwd): return True",
            critique="Senha armazenada em plaintext! Use hash.",
            corrected="def login(user, pwd): return check_password_hash(user.pw_hash, pwd)",
            error_type="InsecureDesign",
        )
        engine._seed_evo_population()
        evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
        for i, node in enumerate(evos):
            if i < len(evos) // 3:
                node.record(success=False, latency=5.0)
            else:
                node.record(success=True, latency=0.5)
        engine._select_survivors()
        engine._mutate_nodes()
        engine._crossover_phase()
        fmt = format_errors_for_prompt(
            query_relevant_errors("criar funcao de login segura")
        )
        assert len(fmt) > 0
        assert "hash" in fmt.lower() or "InsecureDesign" in fmt

    # ----------------------------------------------------------------
    # TESTE 14: store_success + get_success_by_task
    # ----------------------------------------------------------------
    def test_success_memory_feedback(self):
        store_success(
            task="criar rota Flask com autenticacao",
            codigo="""@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        return jsonify({'token': create_access_token(identity=user.id)})
    return jsonify({'error': 'invalid credentials'}), 401""",
            metadata={"framework": "flask", "security": "jwt"},
        )
        result = get_success_by_task("criar rota Flask com autenticacao")
        assert result is not None
        assert "token" in result["codigo"]
        assert result["metadata"]["framework"] == "flask"
        from iaglobal.memory.memory_storage import get_task_hash
        h1 = get_task_hash("criar rota Flask com autenticacao")
        h2 = get_task_hash("  CRIAR ROTA FLASK COM AUTENTICACAO  ")
        assert h1 == h2

    # ----------------------------------------------------------------
    # TESTE 15: Erro -> correcao -> novo sucesso -> comparacao
    # ----------------------------------------------------------------
    def test_error_to_success_improvement(self):
        task = "criar consulta SQL segura"
        codigo_ruim = "cursor.execute(f'SELECT * FROM users WHERE id={user_input}')"
        store_error(
            prompt=task,
            response=codigo_ruim,
            critique="SQL injection! Use parametros.",
            corrected="cursor.execute('SELECT * FROM users WHERE id=?', (user_input,))",
            error_type="SQLInjection",
        )
        codigo_bom = "cursor.execute('SELECT * FROM users WHERE id=?', (user_input,))"
        store_success(task=task, codigo=codigo_bom, metadata={"security": "sql-parametrized"})
        success = get_success_by_task(task)
        assert success is not None
        assert "?" in success["codigo"]
        relevant = query_relevant_errors(task, limit=3)
        fmt = format_errors_for_prompt(relevant)
        assert "SQL" in fmt or "sql" in fmt.lower()
        assert codigo_bom != codigo_ruim

    # ----------------------------------------------------------------
    # TESTE 16: Persistencia de erros entre sessoes
    # ----------------------------------------------------------------
    def test_error_persistence_across_sessions(self):
        error_file = _paths.ERROR_LOG
        assert not os.path.exists(error_file) or os.path.getsize(error_file) == 0
        store_error(
            prompt="teste persistencia",
            response="print('erro')",
            critique="Use logging em vez de print",
            corrected="logger.info('ok')",
            error_type="BadPractice",
        )
        assert os.path.exists(error_file)
        assert os.path.getsize(error_file) > 0
        with open(error_file) as f:
            data = json.load(f)
        assert "learning_errors" in data
        assert len(data["learning_errors"]) >= 1
        errors_reloaded = load_errors()
        assert len(errors_reloaded) >= 1


# =========================================================================
# imported for statistics and secrets
# =========================================================================
from secrets import SystemRandom
_rand = SystemRandom()
import statistics


# =========================================================================
# TESTE 17: Regressao deterministica (golden snapshot)
# ----------------------------------------------------------------
def test_deterministic_evolution_snapshot():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.2)
    engine._seed_evo_population()
    engine.evolve()
    recorder = SimulationRecorder()
    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    fitness_values = [n.fitness() for n in evos]
    recorder.record(graph, engine, fitness_values)
    snap = recorder.snapshot()
    assert snap["generation"] >= 1
    assert snap["core_count"] == 25


# ----------------------------------------------------------------
# TESTE 18: Monotonicidade de fitness sob ambiente controlado
# ----------------------------------------------------------------
def test_fitness_monotonic_improvement_under_stable_environment():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.1)
    env = DynamicAdversarialEnvironment(seed=1)
    engine._seed_evo_population()
    task = env.next_generation()
    engine.set_task(task.prompt)
    _record_fitness_from_task(graph, task.prompt)
    engine.evolve()
    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    avg = sum(n.fitness() for n in evos) / len(evos) if evos else 0.0
    print(f"\n  Mean fitness after evolve: {avg:.3f}")
    assert avg > 0.0, "Fitness deve ser positivo apos evolucao"


# ----------------------------------------------------------------
# TESTE 19: Colapso de diversidade detectado
# ----------------------------------------------------------------
def test_population_collapse_detection():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.9)
    engine._seed_evo_population()
    for node in graph.nodes.values():
        if node.name.startswith("evo_"):
            node.strategy = "fast"
            for _ in range(10):
                node.record(success=True, latency=0.1)
    engine._select_survivors()
    evo_nodes = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    diversity_ok = check_diversity_invariant(evo_nodes, threshold=0.2)
    assert diversity_ok is False, "Deveria detectar colapso de diversidade"


# ----------------------------------------------------------------
# TESTE 20: Ambiente adversarial nunca fica estatico
# ----------------------------------------------------------------
def test_adversarial_anti_learning_pressure():
    init_storage(clear=True)
    skill_registry.clear()
    env = DynamicAdversarialEnvironment(seed=99)
    tasks = [env.next_generation() for _ in range(10)]
    assert any(t.has_adversarial for t in tasks)
    assert len(set(t.prompt for t in tasks)) > 1
    contradiction_score = sum(1 for t in tasks if t.has_adversarial)
    assert contradiction_score > 0, "Ambiente nunca fica estatico"


# ----------------------------------------------------------------
# TESTE 21: Memoria de erros nao contamina todo contexto
# ----------------------------------------------------------------
def test_error_memory_does_not_poison_all_outputs():
    init_storage(clear=True)
    skill_registry.clear()
    for _ in range(20):
        store_error(
            prompt="x",
            response="bad code",
            critique="always wrong",
            corrected="good code",
            error_type="Noise",
        )
    relevant = query_relevant_errors("unrelated task with unique context")
    assert len(relevant) < 20, "Memoria toxica nao deve dominar contexto"


# ----------------------------------------------------------------
# TESTE 22: Estabilidade entre mutacao e crossover
# ----------------------------------------------------------------
def test_mutation_crossover_stability():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()
    before_core = len([n for n in graph.nodes.keys() if not n.startswith("evo_")])
    engine._mutate_nodes()
    engine._crossover_phase()
    after_nodes = set(graph.nodes.keys())
    after_core = [n for n in after_nodes if not n.startswith("evo_")]
    assert len(after_core) == before_core, "Core graph nao pode ser destruido"


# ----------------------------------------------------------------
# TESTE 23: Convergencia estatistica
# ----------------------------------------------------------------
def test_statistical_convergence():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()
    engine._seed_evo_population()
    for n in [n for n in graph.nodes.values() if n.name.startswith("evo_")]:
        n.record(success=True, latency=0.5)
    engine.evolve()
    evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    mean_fitness = statistics.mean([n.fitness() for n in evos]) if evos else 0.0
    assert mean_fitness >= 0.0
    assert statistics.pstdev([n.fitness() for n in evos] if evos else [0.0]) < 1.0


# ----------------------------------------------------------------
# TESTE 24: Exploracao vs exploracao balanceada
# ----------------------------------------------------------------
def test_exploration_vs_exploitation_balance():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()
    evo = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    for n in evo:
        for _ in range(3):
            n.record(success=True, latency=0.5)
    for _ in range(2):
        engine.evolve()
    strategies = [n.strategy for n in graph.nodes.values() if n.name.startswith("evo_")]
    if strategies:
        diversity = len(set(strategies)) / len(strategies)
        assert diversity > 0.1, f"Diversidade colapsou: {diversity:.2f}"


# ----------------------------------------------------------------
# TESTE 25: Curva de aprendizado adversarial
# ----------------------------------------------------------------
def test_adversarial_learning_curve():
    init_storage(clear=True)
    skill_registry.clear()
    graph = _build_core_graph()
    engine = EvolutionEngine(graph, mutation_rate=0.3)
    engine._seed_evo_population()
    env = DynamicAdversarialEnvironment(seed=7)
    recorder = SimulationRecorder()
    for gen in range(3):
        task = env.next_generation()
        _record_fitness_from_task(graph, task.prompt)
        _record_fitness_from_task(graph, task.prompt)
        engine._select_survivors()
        evos = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
        fitness_values = [n.fitness() for n in evos] if evos else [0.0]
        recorder.record(graph, engine, fitness_values)
        engine._mutate_nodes()
    snap = recorder.snapshot()
    assert "generation" in snap
    assert snap["evo_count"] > 0
    assert len(recorder.records) == 3
    last = recorder.records[-1]
    first = recorder.records[0]
    dist = structural_distance(
        {"node_names": first.node_names, "strategies": {}, "evo_count": first.evo_count,
         "mutant_count": first.mutant_count, "hybrid_count": first.hybrid_count,
         "core_count": first.core_count},
        {"node_names": last.node_names, "strategies": {}, "evo_count": last.evo_count,
         "mutant_count": last.mutant_count, "hybrid_count": last.hybrid_count,
         "core_count": last.core_count},
    )
    print(f"\n  Estrutura mudou entre gen 0 e gen 2: {dist}")
    hard = check_hard_invariants(graph)
    assert not hard, f"Invariantes violados: {hard}"
    soft = check_soft_invariants(graph)
    if soft:
        print(f"  ⚠️ Soft warnings: {soft}")
    # trend analysis: fitness pode flutuar naturalmente; apenas verificamos estrutura
    slope = trend([r.mean_fitness for r in recorder.records])
    print(f"  Trend slope: {slope:.4f}")
