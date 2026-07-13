# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do Genetic Algorithm Tuning (evolution/ga/).

Cobertura:
  - Population: inicialização, best, avg_fitness, top_n
  - Individual: clamp, to_dict, propriedades
  - Selector: tournament_select, blend_crossover, gaussian_mutate, evolve_population
  - GARunner: step, run_n_generations, persistência, load_best_genome
  - Memória biológica: persiste genoma em Obsidian, DB, lineage, epigenetics
"""

import json
import logging
import random
import sqlite3


from iaglobal.evolution.ga.population import Individual, Population

logging.basicConfig(level=logging.ERROR)


# ─────────────────────────────────────────────
# Individual
# ─────────────────────────────────────────────


class TestIndividual:
    def test_default_weights(self):
        ind = Individual()
        assert ind.weights == [0.0, 0.0, 0.0, 0.0]

    def test_properties(self):
        ind = Individual(weights=[0.4, 0.3, 0.2, 0.1])
        assert ind.ivm_p == 0.4
        assert ind.ivm_e == 0.3
        assert ind.ivm_c == 0.2
        assert ind.ivm_i == 0.1

    def test_to_dict(self):
        ind = Individual(weights=[0.4567, 0.3, 0.2, 0.1])
        d = ind.to_dict()
        assert d["P"] == 0.4567
        assert list(d.keys()) == ["P", "E", "C", "I"]

    def test_clamp_lower(self):
        ind = Individual(weights=[-0.5, 1.5, 0.3, 0.2])
        ind.clamp()
        assert ind.weights[0] == 0.0
        assert ind.weights[1] == 1.0

    def test_clamp_upper(self):
        ind = Individual(weights=[0.1, 0.2, 0.3, -0.1])
        ind.clamp()
        assert ind.weights[3] == 0.0

    def test_fitness_default(self):
        ind = Individual()
        assert ind.fitness == 0.0

    def test_generation_tracking(self):
        ind = Individual(weights=[0.5] * 4, generation=5)
        assert ind.generation == 5


# ─────────────────────────────────────────────
# Population
# ─────────────────────────────────────────────


class TestPopulation:
    def test_initialize_creates_correct_size(self):
        pop = Population(size=20)
        pop.initialize()
        assert len(pop.individuals) == 20

    def test_initialize_default_size(self):
        pop = Population()
        pop.initialize()
        assert len(pop.individuals) == Population.SIZE

    def test_all_individuals_have_valid_weights(self):
        pop = Population(size=50)
        pop.initialize()
        for ind in pop.individuals:
            assert len(ind.weights) == 4
            for w in ind.weights:
                assert 0.0 <= w <= 1.0

    def test_best_returns_highest_fitness(self):
        pop = Population(size=10)
        pop.initialize()
        pop.individuals[0].fitness = 0.9
        pop.individuals[1].fitness = 0.5
        best = pop.best()
        assert best.fitness == 0.9

    def test_avg_fitness(self):
        pop = Population(size=5)
        pop.initialize()
        for i, ind in enumerate(pop.individuals):
            ind.fitness = i / 4
        assert abs(pop.avg_fitness() - 0.5) < 0.01

    def test_avg_fitness_empty(self):
        pop = Population(size=10)
        assert pop.avg_fitness() == 0.0

    def test_top_n(self):
        pop = Population(size=10)
        pop.initialize()
        for i, ind in enumerate(pop.individuals):
            ind.fitness = i
        top = pop.top_n(3)
        assert len(top) == 3
        assert top[0].fitness == 9
        assert top[2].fitness == 7


# ─────────────────────────────────────────────
# Selector
# ─────────────────────────────────────────────


class TestSelector:
    def test_tournament_select_returns_best_of_sample(self):
        pop = [Individual(weights=[0.5] * 4) for _ in range(10)]
        for i, ind in enumerate(pop):
            ind.fitness = i / 10
        from iaglobal.evolution.ga.selector import tournament_select

        winner = tournament_select(pop, tournament_size=10)
        assert winner.fitness == 0.9

    def test_tournament_select_small_population(self):
        from iaglobal.evolution.ga.selector import tournament_select

        pop = [Individual(weights=[0.5] * 4) for _ in range(2)]
        pop[0].fitness = 0.8
        pop[1].fitness = 0.6
        winner = tournament_select(pop, tournament_size=5)
        assert winner.fitness == 0.8

    def test_blend_crossover_produces_valid_weights(self):
        from iaglobal.evolution.ga.selector import blend_crossover

        p1 = Individual(weights=[0.2, 0.8, 0.3, 0.7])
        p2 = Individual(weights=[0.6, 0.4, 0.7, 0.3])
        child = blend_crossover(p1, p2, alpha=0.5)
        assert len(child.weights) == 4
        for w in child.weights:
            assert 0.0 <= w <= 1.0

    def test_blend_crossover_children_differ_from_parents(self):
        from iaglobal.evolution.ga.selector import blend_crossover

        p1 = Individual(weights=[0.1, 0.1, 0.1, 0.1])
        p2 = Individual(weights=[0.9, 0.9, 0.9, 0.9])
        child = blend_crossover(p1, p2, alpha=0.5)
        assert child.ivm_p >= 0.0
        assert child != p1
        assert child != p2

    def test_gaussian_mutate_changes_some_weights(self):
        from iaglobal.evolution.ga.selector import gaussian_mutate

        ind = Individual(weights=[0.5, 0.5, 0.5, 0.5])
        gaussian_mutate(ind, mutation_rate=1.0, sigma=0.1)
        assert ind.weights != [0.5, 0.5, 0.5, 0.5]

    def test_gaussian_mutate_no_mutation(self):
        from iaglobal.evolution.ga.selector import gaussian_mutate

        ind = Individual(weights=[0.5, 0.5, 0.5, 0.5])
        gaussian_mutate(ind, mutation_rate=0.0, sigma=0.1)
        assert ind.weights == [0.5, 0.5, 0.5, 0.5]

    def test_evolve_population_keeps_size(self):
        from iaglobal.evolution.ga.selector import evolve_population

        pop = [Individual(weights=[0.5] * 4) for _ in range(20)]
        for i, ind in enumerate(pop):
            ind.fitness = i / 20
        new_pop = evolve_population(pop)
        assert len(new_pop) == 20

    def test_evolve_population_preserves_top_elite(self):
        from iaglobal.evolution.ga.selector import evolve_population

        pop = [Individual(weights=[0.5] * 4) for _ in range(20)]
        for i, ind in enumerate(pop):
            ind.fitness = i
            ind.weights = [i / 20] * 4
        new_pop = evolve_population(pop, elite_ratio=0.2)
        assert new_pop[0].fitness >= 18

    def test_evolve_population_preserves_structure(self):
        from iaglobal.evolution.ga.selector import evolve_population

        pop = [Individual(weights=[0.5] * 4) for _ in range(30)]
        for ind in pop:
            ind.fitness = random.uniform(0, 0.5)
        new_pop = evolve_population(pop)
        assert len(new_pop) == 30
        for ind in new_pop:
            assert len(ind.weights) == 4
            for w in ind.weights:
                assert 0.0 <= w <= 1.0


# ─────────────────────────────────────────────
# GA Runner
# ─────────────────────────────────────────────


class TestGARunner:
    def test_ensure_initialized_creates_population(self):
        from iaglobal.evolution.ga.ga_runner import GARunner

        runner = GARunner()
        runner.ensure_initialized()
        assert runner.population is not None
        assert len(runner.population.individuals) > 0
        assert runner.initialized is True

    def test_step_returns_result_structure(self):
        from iaglobal.evolution.ga.ga_runner import GARunner

        runner = GARunner()
        runner.ensure_initialized()
        result = runner.step()
        assert "best_weights" in result
        assert "best_fitness" in result
        assert "generation" in result
        assert "avg_fitness" in result
        assert result["generation"] >= 1

    def test_step_increments_generation(self):
        from iaglobal.evolution.ga.ga_runner import GARunner

        runner = GARunner()
        runner.ensure_initialized()
        g1 = runner.step()["generation"]
        g2 = runner.step()["generation"]
        assert g2 == g1 + 1

    def test_run_n_generations(self):
        from iaglobal.evolution.ga.ga_runner import GARunner

        runner = GARunner()
        runner.ensure_initialized()
        results = runner.run_n_generations(3)
        assert len(results) == 3
        assert results[-1]["generation"] == runner.population.generation

    def test_load_best_genome_no_file(self):
        from iaglobal.evolution.ga.ga_runner import GARunner, GENOME_PATH

        if GENOME_PATH.exists():
            GENOME_PATH.unlink()
        genome = GARunner.load_best_genome()
        assert genome["weights"] == [0.25, 0.25, 0.25, 0.25]
        assert genome["fitness"] == 0.0

    def test_task_hook_triggers_at_interval(self):
        from iaglobal.evolution.ga.ga_runner import GARunner, GENERATION_INTERVAL

        runner = GARunner()
        runner.ensure_initialized()
        gen_before = runner.population.generation
        for _ in range(GENERATION_INTERVAL - 1):
            runner.task_hook()
        assert runner.population.generation == gen_before
        runner.task_hook()
        assert runner.population.generation > gen_before

    def test_persist_genome(self):
        from iaglobal.evolution.ga.ga_runner import GARunner, GENOME_PATH

        if GENOME_PATH.exists():
            GENOME_PATH.unlink()
        runner = GARunner()
        runner.ensure_initialized()
        runner.step()
        assert GENOME_PATH.exists()
        data = json.loads(GENOME_PATH.read_text(encoding="utf-8"))
        assert "weights" in data
        assert "fitness" in data
        assert "generation" in data

    def test_persist_telemetry(self):
        from iaglobal.evolution.ga.ga_runner import GARunner, TELEMETRY_PATH

        if TELEMETRY_PATH.exists():
            TELEMETRY_PATH.unlink()
        runner = GARunner()
        runner.ensure_initialized()
        runner.step()
        assert TELEMETRY_PATH.exists()
        data = json.loads(TELEMETRY_PATH.read_text(encoding="utf-8"))
        assert "generations" in data
        assert "best_fitness_history" in data
        assert len(data["generations"]) >= 1

    def test_apply_epigenetic_weights(self):
        from iaglobal.evolution.ga.ga_runner import _apply_epigenetic_weights

        _apply_epigenetic_weights({"P": 0.4, "E": 0.3, "C": 0.2, "I": 0.1})
        from iaglobal.evolution.epigenetic import get_flag

        assert get_flag("ga_weight_p") == 0.4
        assert get_flag("ga_weight_e") == 0.3

    def test_clone_genome_restores_population(self):
        from iaglobal.evolution.ga.ga_runner import GARunner, GENOME_PATH

        if GENOME_PATH.exists():
            GENOME_PATH.unlink()
        runner = GARunner()
        runner.ensure_initialized()
        runner.step()
        data1 = json.loads(GENOME_PATH.read_text(encoding="utf-8"))

        runner2 = GARunner()
        runner2.ensure_initialized()
        assert runner2.population.generation == data1["generation"]


class TestBiologicalMemory:
    """Testes da persistência do GA nos sistemas de memória biológica."""

    def test_persist_biological_memory_creates_stm_note(self):
        """step() deve gerar nota de curto prazo no Obsidian."""
        from iaglobal.evolution.ga.ga_runner import GARunner
        from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

        runner = GARunner()
        runner.ensure_initialized()
        gen_before = runner.population.generation
        runner.step()
        gen = runner.population.generation
        genome_id = f"ga_gen_{gen}"
        sub = SubconsciousAPI()
        stm_path = sub.short_term_dir / f"{genome_id}.md"
        assert stm_path.exists(), f"STM note should exist at {stm_path}"

    def test_persist_biological_memory_creates_ltm_note_if_fitness_high(self):
        """step() com fitness >= 0.7 deve gerar nota de longo prazo."""
        from iaglobal.evolution.ga.ga_runner import GARunner
        from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

        runner = GARunner()
        runner.ensure_initialized()
        runner.step()
        gen = runner.population.generation
        genome_id = f"ga_gen_{gen}"
        sub = SubconsciousAPI()
        genome_path = (
            runner.population.genome_path
            if hasattr(runner.population, "genome_path")
            else None
        )

        ltm_path = sub.long_term_dir / f"{genome_id}.md"
        if runner.step()["best_fitness"] >= 0.7:
            assert ltm_path.exists(), (
                f"LTM note should exist for high-fitness genome at {ltm_path}"
            )
        else:
            pass  # fitness < 0.7 — sem LTM

    def test_persist_biological_memory_stores_insight(self):
        """step() deve registrar insight no sistema imunológico."""
        from iaglobal.evolution.ga.ga_runner import GARunner
        from iaglobal.memory.db_manager import DatabaseManager

        runner = GARunner()
        runner.ensure_initialized()
        runner.step()
        gen = runner.population.generation
        genome_id = f"ga_gen_{gen}"
        db = DatabaseManager()
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT agent, task_id, score FROM insights WHERE task_id = ?", (genome_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        assert len(rows) >= 1
        assert rows[0][0] == "ga_runner"

    def test_persist_biological_memory_stores_memory_vector(self):
        """step() deve registrar no banco vetorial."""
        from iaglobal.evolution.ga.ga_runner import GARunner
        from iaglobal.memory import memory_vector as mv

        runner = GARunner()
        runner.ensure_initialized()
        runner.step()
        gen = runner.population.generation

        conn = mv.get_vector_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT type FROM memory WHERE type = 'ga_genome' ORDER BY id DESC LIMIT 1"
        )
        rows = cursor.fetchall()
        conn.close()
        assert len(rows) >= 1
        assert rows[0][0] == "ga_genome"

    def test_persist_biological_memory_registers_lineage(self):
        """step() deve registrar linhagem no AncestryTree."""
        from iaglobal.evolution.ga.ga_runner import GARunner
        from iaglobal.obsidian.ancestry_tree import ancestry_tree

        runner = GARunner()
        runner.ensure_initialized()
        gen_before = runner.population.generation
        runner.step()
        gen = runner.population.generation
        genome_id = f"ga_gen_{gen}"
        assert genome_id in ancestry_tree._lineage_notes

    def test_persist_biological_memory_registers_epigenetic_success(self):
        """step() deve registrar marca epigenética de sucesso (arquivo CBOR)."""
        from iaglobal.evolution.ga.ga_runner import GARunner
        from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry

        runner = GARunner()
        runner.ensure_initialized()
        runner.step()
        gen = runner.population.generation
        epi = EpigeneticRegistry()
        task_hash = f"gen_{gen}"
        # Verifica no sistema de arquivos (cbors)
        found = False
        import cbor2

        for cbor_file in epi.base_path.glob("*.cbor"):
            try:
                data = cbor2.loads(cbor_file.read_bytes())
                if (
                    data.get("task_hash") == task_hash
                    and data.get("error_type") == "success"
                ):
                    found = True
                    break
            except Exception:
                continue
        assert found, f"Epigenetic success CBOR should exist for {task_hash}"

    def test_prev_genome_tracking(self):
        """GARunner deve rastrear geração anterior."""
        from iaglobal.evolution.ga.ga_runner import GARunner

        runner = GARunner()
        runner.ensure_initialized()
        assert runner._prev_genome_id is None
        assert runner._prev_best_fitness is None
        runner.step()
        assert runner._prev_genome_id is not None
        assert runner._prev_best_fitness is not None
        first_id = runner._prev_genome_id
        first_fit = runner._prev_best_fitness
        runner.step()
        assert runner._prev_genome_id != first_id
        assert runner._prev_best_fitness is not None
