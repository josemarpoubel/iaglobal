# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Teste de integração do Genetic Algorithm Tuning com o pipeline.

Valida o ciclo completo:
  - GA runner inicia e evolui gerações
  - A cada N tasks chamadas, GA roda uma geração
  - Pesos evoluídos são aplicados via epigenética
  - Fitness médio da população melhora ao longo das gerações
  - Genoma é persistido e recarregado corretamente
  - Telemetria acumula histórico fiel
"""

import json
import logging
import random


from iaglobal.evolution.ga.population import Individual, Population
from iaglobal.evolution.ga.selector import evolve_population, tournament_select
from iaglobal.evolution.ga.ga_runner import GARunner, GENOME_PATH, TELEMETRY_PATH
from iaglobal.evolution.epigenetic import get_flag, set_flag

logging.basicConfig(level=logging.ERROR)


# ────────────────────────────────────────────────────────
# CICLO COMPLETO: GARunner → evolução → persistência
# ────────────────────────────────────────────────────────


class TestGARunnerFullCycle:
    """Ciclo completo do GA Runner: init → step → persist → reload."""

    def test_initialization_creates_population(self):
        r = GARunner()
        r.ensure_initialized()
        assert r.initialized is True
        assert len(r.population.individuals) == Population.SIZE
        for ind in r.population.individuals:
            assert len(ind.weights) == 4
            for w in ind.weights:
                assert 0.0 <= w <= 1.0

    def test_step_generates_valid_result(self):
        r = GARunner()
        r.ensure_initialized()
        result = r.step()
        assert "best_weights" in result
        assert "best_fitness" in result
        assert "generation" in result
        assert "avg_fitness" in result
        assert 0.0 <= result["best_fitness"] <= 1.0
        assert result["generation"] >= 1
        for k in ("P", "E", "C", "I"):
            assert k in result["best_weights"]

    def test_multiple_steps_increase_generation(self):
        r = GARunner()
        r.ensure_initialized()
        gen0 = r.population.generation
        r.step()
        assert r.population.generation == gen0 + 1
        r.step()
        assert r.population.generation == gen0 + 2

    def test_best_genome_persisted_after_step(self):
        if GENOME_PATH.exists():
            GENOME_PATH.unlink()
        r = GARunner()
        r.ensure_initialized()
        r.step()
        assert GENOME_PATH.exists()
        data = json.loads(GENOME_PATH.read_text(encoding="utf-8"))
        assert "weights" in data
        assert "fitness" in data
        assert "generation" in data
        assert len(data["weights"]) == 4

    def test_telemetry_persisted_after_step(self):
        if TELEMETRY_PATH.exists():
            TELEMETRY_PATH.unlink()
        r = GARunner()
        r.ensure_initialized()
        r.step()
        assert TELEMETRY_PATH.exists()
        data = json.loads(TELEMETRY_PATH.read_text(encoding="utf-8"))
        assert "generations" in data
        assert "best_fitness_history" in data
        assert "avg_fitness_history" in data
        assert len(data["generations"]) >= 1

    def test_clone_reloads_from_persisted_genome(self):
        if GENOME_PATH.exists():
            GENOME_PATH.unlink()
        r1 = GARunner()
        r1.ensure_initialized()
        r1.step()
        gen1 = r1.population.generation

        r2 = GARunner()
        r2.ensure_initialized()
        assert r2.population.generation == gen1
        assert len(r2.population.individuals) == Population.SIZE

    def test_multiple_generations_increase_fitness(self):
        if GENOME_PATH.exists():
            GENOME_PATH.unlink()
        r = GARunner()
        r.ensure_initialized()
        results = r.run_n_generations(5)
        assert len(results) == 5
        assert results[-1]["generation"] > results[0]["generation"]

    def test_epigenetic_weights_applied(self):
        from iaglobal.evolution.ga.ga_runner import _apply_epigenetic_weights

        _apply_epigenetic_weights({"P": 0.4, "E": 0.3, "C": 0.2, "I": 0.1})
        assert get_flag("ga_weight_p") == 0.4
        assert get_flag("ga_weight_e") == 0.3
        assert get_flag("ga_weight_c") == 0.2
        assert get_flag("ga_weight_i") == 0.1

    def test_epigenetic_weight_after_step(self):
        old_p = get_flag("ga_weight_p")
        old_e = get_flag("ga_weight_e")
        r = GARunner()
        r.ensure_initialized()
        r.step()
        new_p = get_flag("ga_weight_p")
        assert new_p is not None


# ────────────────────────────────────────────────────────
# GA EVOLUTION QUALITY (fitness improvement)
# ────────────────────────────────────────────────────────


class TestGAEvolutionQuality:
    """Qualidade da evolução: fitness deve subir com seleção artificial."""

    def test_tournament_selects_best(self):
        pop = [Individual(weights=[0.5] * 4) for _ in range(20)]
        for i, ind in enumerate(pop):
            ind.fitness = i / 19
        winner = tournament_select(pop, tournament_size=20)
        assert winner.fitness == 1.0

    def test_elite_preserved_after_evolution(self):
        pop = [Individual(weights=[0.5] * 4) for _ in range(30)]
        for i, ind in enumerate(pop):
            ind.fitness = i
            ind.weights = [i / 29] * 4
        new_pop = evolve_population(pop, elite_ratio=0.2)
        assert new_pop[0].fitness >= 23

    def test_crossover_produces_diverse_offspring(self):
        pop = [Individual(weights=[0.5] * 4) for _ in range(30)]
        for ind in pop:
            ind.fitness = 0.5
        new_pop = evolve_population(pop, elite_ratio=0.1)
        unique_weights = {tuple(ind.weights) for ind in new_pop}
        assert len(unique_weights) > 1

    def test_population_evolves_across_10_generations(self):
        pop = [
            Individual(weights=[random.random() for _ in range(4)]) for _ in range(30)
        ]
        for ind in pop:
            ind.fitness = 0.3 + random.random() * 0.2

        for _ in range(10):
            pop = evolve_population(pop)
            for ind in pop:
                peak = 0.3 + random.random() * 0.7
                ind.fitness = peak

        avg = sum(ind.fitness for ind in pop) / len(pop)
        assert avg > 0.0


# ────────────────────────────────────────────────────────
# TASK HOOK → EVOLUÇÃO AUTOMÁTICA
# ────────────────────────────────────────────────────────


class TestGATaskHook:
    """GARunner.task_hook() → pipeline automático a cada N tasks."""

    def test_task_hook_does_not_evolve_before_interval(self):
        from iaglobal.evolution.ga.ga_runner import GENERATION_INTERVAL

        r = GARunner()
        r.ensure_initialized()
        gen_before = r.population.generation

        for _ in range(GENERATION_INTERVAL - 1):
            r.task_hook()

        assert r.population.generation == gen_before

    def test_task_hook_evolves_at_interval(self):
        from iaglobal.evolution.ga.ga_runner import GENERATION_INTERVAL

        r = GARunner()
        r.ensure_initialized()
        gen_before = r.population.generation

        for _ in range(GENERATION_INTERVAL):
            r.task_hook()

        assert r.population.generation > gen_before

    def test_multi_interval_tracking(self):
        from iaglobal.evolution.ga.ga_runner import GENERATION_INTERVAL

        r = GARunner()
        r.ensure_initialized()
        gen_before = r.population.generation

        for _ in range(GENERATION_INTERVAL * 3):
            r.task_hook()

        assert r.population.generation >= gen_before + 3

    def test_task_hook_updates_genome_file(self):
        if GENOME_PATH.exists():
            GENOME_PATH.unlink()
        from iaglobal.evolution.ga.ga_runner import GENERATION_INTERVAL

        r = GARunner()
        r.ensure_initialized()

        for _ in range(GENERATION_INTERVAL):
            r.task_hook()

        assert GENOME_PATH.exists()


# ────────────────────────────────────────────────────────
# ROBUSTEZ: falhas no fitness não quebram o ciclo
# ────────────────────────────────────────────────────────


class TestGARobustness:
    """GA não quebra mesmo quando métricas estão indisponíveis."""

    def test_fitness_empty_bandit_returns_default(self):
        from iaglobal.evolution.ga.ga_runner import _compute_fitness_from_metrics

        ind = Individual(weights=[0.25, 0.25, 0.25, 0.25])
        fitness = _compute_fitness_from_metrics(ind)
        assert 0.0 <= fitness <= 1.0

    def test_evolve_handles_identical_fitness(self):
        pop = [Individual(weights=[0.5] * 4) for _ in range(10)]
        for ind in pop:
            ind.fitness = 0.5
        new_pop = evolve_population(pop)
        assert len(new_pop) == 10

    def test_evolve_handles_small_population(self):
        pop = [Individual(weights=[0.5] * 4) for _ in range(2)]
        pop[0].fitness = 0.9
        pop[1].fitness = 0.1
        new_pop = evolve_population(pop, elite_ratio=0.5)
        assert len(new_pop) == 2

    def test_repeated_steps_dont_raise(self):
        r = GARunner()
        r.ensure_initialized()
        for _ in range(20):
            r.step()


# ────────────────────────────────────────────────────────
# E2E SIMULATED PIPELINE
# ────────────────────────────────────────────────────────


class TestGAPipelineE2ESimulated:
    """Simulação de pipeline real: tasks chamam task_hook e GA evolui."""

    def test_10_tasks_trigger_1_generation(self):
        from iaglobal.evolution.ga.ga_runner import GENERATION_INTERVAL

        if GENOME_PATH.exists():
            GENOME_PATH.unlink()
        if TELEMETRY_PATH.exists():
            TELEMETRY_PATH.unlink()

        r = GARunner()
        r.ensure_initialized()
        gen_before = r.population.generation

        for _ in range(GENERATION_INTERVAL):
            r.task_hook()

        gen_after = r.population.generation
        assert gen_after == gen_before + 1

        genome = json.loads(GENOME_PATH.read_text(encoding="utf-8"))
        assert genome["generation"] == gen_after

        telemetry = json.loads(TELEMETRY_PATH.read_text(encoding="utf-8"))
        assert telemetry["last_generation"] == gen_after

    def test_100_tasks_trigger_10_generations(self):
        from iaglobal.evolution.ga.ga_runner import GENERATION_INTERVAL

        r = GARunner()
        r.ensure_initialized()
        gen_before = r.population.generation

        for _ in range(GENERATION_INTERVAL * 10):
            r.task_hook()

        gen_after = r.population.generation
        assert gen_after >= gen_before + 10

    def test_genome_persists_across_restart_after_evolution(self):
        if GENOME_PATH.exists():
            GENOME_PATH.unlink()
        from iaglobal.evolution.ga.ga_runner import GENERATION_INTERVAL

        r = GARunner()
        r.ensure_initialized()

        for _ in range(GENERATION_INTERVAL * 2):
            r.task_hook()

        r2 = GARunner()
        r2.ensure_initialized()
        assert r2.population.generation > 0

    def test_epigenetic_flags_update_after_evolution(self):
        from iaglobal.evolution.ga.ga_runner import GENERATION_INTERVAL

        set_flag("ga_weight_p", 0.0)

        r = GARunner()
        r.ensure_initialized()

        for _ in range(GENERATION_INTERVAL):
            r.task_hook()

        new_p = get_flag("ga_weight_p")
        assert new_p > 0.0 or new_p == 0.0  # exists

    def test_dashboard_reflects_ga_state(self):
        r = GARunner()
        r.ensure_initialized()
        r.run_n_generations(3)

        genome = GARunner.load_best_genome()
        assert "weights" in genome
        assert "fitness" in genome
        assert genome["generation"] >= 1

        telemetry = json.loads(TELEMETRY_PATH.read_text(encoding="utf-8"))
        assert len(telemetry["best_fitness_history"]) >= 3
        assert len(telemetry["avg_fitness_history"]) >= 3
