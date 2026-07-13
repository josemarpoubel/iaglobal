# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
GA Runner — Ciclo evolutivo completo com telemetria e persistência.

Executa 1 geração a cada N tasks, salva melhor genoma em JSON,
e aplica pesos via epigenetic.py. Integra com Obsidian Vault,
memória vetorial, sistema imunológico e árvore de ancestralidade.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Optional

from iaglobal._paths import PROJECT_ROOT
from iaglobal.evolution.ga.population import Individual, Population
from iaglobal.evolution.ga.selector import evolve_population
from iaglobal.memory.db_manager import DatabaseManager as DBManager
from iaglobal.memory.memory_vector import store as memory_vector_store
from iaglobal.obsidian.ancestry_tree import ancestry_tree
from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry
from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.evolution.ga")

GENOME_PATH = (
    Path(PROJECT_ROOT) / "iaglobal" / "memory" / "data" / "json" / "best_genome.json"
)
TELEMETRY_PATH = (
    Path(PROJECT_ROOT) / "iaglobal" / "memory" / "data" / "json" / "ga_telemetry.json"
)

GENERATION_INTERVAL = 10
TELEMETRY_WINDOW = 100


def _load_genome() -> dict:
    if GENOME_PATH.exists():
        try:
            return json.loads(GENOME_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_genome(data: dict):
    GENOME_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENOME_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _load_telemetry() -> dict:
    if TELEMETRY_PATH.exists():
        try:
            return json.loads(TELEMETRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"generations": [], "best_fitness_history": [], "avg_fitness_history": []}


def _save_telemetry(data: dict):
    TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    TELEMETRY_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _compute_fitness_from_metrics(individual: Individual) -> float:
    """Calcula fitness baseado em métricas reais do sistema.

    Usa dados do BanditPolicy e provider_metrics para avaliar
    o desempenho dos pesos propostos.
    """
    try:
        from iaglobal.graphs.bandit import _get_bandit

        bandit = _get_bandit()

        reward_sum = 0.0
        reward_count = 0

        for arm, rewards in bandit.rewards.items():
            recent = rewards[-TELEMETRY_WINDOW:]
            if not recent:
                continue

            p_contrib = sum(recent) * individual.ivm_p
            e_contrib = (1.0 / max(0.1, len(recent))) * individual.ivm_e

            c_contrib = 0.0
            if bandit.credit_engine:
                stats = bandit.credit_engine.stats
                total_calls = sum(s["success"] + s["fail"] for s in stats.values())
                c_contrib = (total_calls / max(1, len(stats))) * individual.ivm_c * 0.01

            score = (p_contrib * 0.5) + (e_contrib * 0.3) + (c_contrib * 0.2)
            reward_sum += score
            reward_count += 1

        if reward_count == 0:
            return 0.5

        base_fitness = reward_sum / reward_count
        return max(0.0, min(1.0, base_fitness))

    except Exception as e:
        logger.debug("Fitness via métricas falhou: %s", e)
        return 0.5


def _apply_epigenetic_weights(weights: dict):
    """Aplica pesos do melhor genoma ao sistema via epigenetic.py.

    Atualiza flags epigenéticas para refletir a nova configuração
    de pesos IVM, sem necessidade de deploy.
    """
    try:
        from iaglobal.evolution.epigenetic import set_flag

        for key, value in weights.items():
            flag_name = f"ga_weight_{key.lower()}"
            set_flag(flag_name, value)

        logger.info("[GA] Pesos epigenéticos aplicados: %s", weights)
    except Exception as e:
        logger.warning("[GA] Falha ao aplicar pesos epigenéticos: %s", e)


async def _persist_biological_memory_async(
    generation: int,
    best_weights: dict,
    best_fitness: float,
    avg_fitness: float,
    prev_genome_id: Optional[str],
    prev_fitness: Optional[float],
):
    """Persiste o genoma nos sistemas de memória biológica do iaglobal.

    Escreve em:
    - SubconsciousAPI (STM → LTM)
    - DBManager (insight imunológico)
    - memory_vector (busca semântica)
    - AncestryTree (linhagem)
    - EpigeneticRegistry (marcas epigenéticas)
    - Vacinas (genomas mortos com fitness em queda)
    """
    try:
        sub = SubconsciousAPI()
        db = DBManager()
        epi = EpigeneticRegistry()
        genome_id = f"ga_gen_{generation}"

        # 1. Memória de curto prazo (STM)
        stm_content = (
            f"## Geração {generation}\n"
            f"- **Best Fitness**: {best_fitness:.4f}\n"
            f"- **Avg Fitness**: {avg_fitness:.4f}\n"
            f"- **Weights**: P={best_weights.get('p', 0):.3f} "
            f"E={best_weights.get('e', 0):.3f} "
            f"C={best_weights.get('c', 0):.3f} "
            f"I={best_weights.get('i', 0):.3f}\n"
            f"- **Timestamp**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"
        )
        await sub.escrever_curto_prazo(
            nome=genome_id,
            conteudo=stm_content,
            tags=["ga", "genoma", f"gen_{generation}"],
        )

        # 2. Memória de longo prazo (LTM) se fitness > 0.7
        if best_fitness >= 0.7:
            ltm_content = (
                f"## Genoma Evoluído — Geração {generation}\n\n"
                f"Este genoma atingiu fitness **{best_fitness:.4f}** "
                f"e foi consolidado como conhecimento de longo prazo.\n\n"
                f"### Pesos Finais\n"
                f"- Produtividade (P): {best_weights.get('p', 0):.4f}\n"
                f"- Eficiência (E): {best_weights.get('e', 0):.4f}\n"
                f"- Cooperação (C): {best_weights.get('c', 0):.4f}\n"
                f"- Imunidade (I): {best_weights.get('i', 0):.4f}\n\n"
                f"### Métricas\n"
                f"- Fitness médio da geração: {avg_fitness:.4f}\n"
                f"- Variação: {abs(best_fitness - avg_fitness):.4f}\n"
                f"- Consolidação: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"
            )
            await sub.escrever_longo_prazo(
                nome=genome_id,
                conteudo=ltm_content,
                tipo="GenomaEvoluido",
                tags=["ga", "genoma", "evolucao", f"fitness_{int(best_fitness * 100)}"],
                fitness=best_fitness,
                links=[f"gen_{max(0, generation - 1)}"] if generation > 0 else [],
            )

        # 3. Insight no sistema imunológico
        db.insert_insight(
            agent="ga_runner",
            task_id=genome_id,
            content=(
                f"GA generation {generation}: fitness={best_fitness:.4f}, "
                f"weights={best_weights}"
            ),
            score=best_fitness * 100,
        )

        # 4. Memória vetorial para busca semântica
        memory_vector_store(
            text=(
                f"GA generation {generation}: best_fitness={best_fitness:.4f}, "
                f"avg_fitness={avg_fitness:.4f}, "
                f"weights=({best_weights})"
            ),
            mtype="ga_genome",
        )

        # 5. AncestryTree — linhagem evolutiva
        parents = [prev_genome_id] if prev_genome_id else ["ga_seed"]
        await ancestry_tree.register_fusion_async(
            hybrid_id=genome_id,
            parents=parents,
            resonance_score=best_fitness,
            traits_inherited={
                "p": "ga_seed",
                "e": "ga_seed",
                "c": "ga_seed",
                "i": "ga_seed",
            },
            generation=generation,
            obsidian_note_id=f"lineage_{genome_id}",
        )

        # 6. EpigeneticRegistry — marca de sucesso
        await epi.record_success(
            agent_id="ga_runner",
            task_hash=f"gen_{generation}",
            ivm_score=best_fitness,
            reward_value=best_fitness,
        )

        # 7. Vacina se fitness caiu significativamente (>15%)
        if prev_fitness is not None and best_fitness < prev_fitness * 0.85:
            vacina_content = (
                f"**⚠️ Vacina Evolutiva — Queda de Fitness**\n\n"
                f"Geração {generation} apresentou queda significativa:\n"
                f"- Fitness anterior: {prev_fitness:.4f}\n"
                f"- Fitness atual: {best_fitness:.4f}\n"
                f"- Variação: {(best_fitness - prev_fitness) / prev_fitness * 100:.1f}%\n\n"
                f"### Pesos que falharam\n"
                f"{json.dumps(best_weights, indent=2)}\n\n"
                f"Recomenda-se não reutilizar esta combinação.\n"
                f"Gerado em: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"
            )
            await sub.escrever_vacina(
                lineage_marker=genome_id,
                conteudo=vacina_content,
            )
            logger.info(
                "[GA] Vacina registrada para genoma %s (queda de fitness)", genome_id
            )

    except Exception as e:
        logger.debug("[GA] Memória biológica: %s", e)


def _persist_biological_memory_sync(
    generation: int,
    best_weights: dict,
    best_fitness: float,
    avg_fitness: float,
    prev_genome_id: Optional[str],
    prev_fitness: Optional[float],
):
    """Wrapper síncrono que delega para _persist_biological_memory_async.

    Tenta obter o event loop ativo; se não houver, cria um novo.
    """
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            asyncio.ensure_future(
                _persist_biological_memory_async(
                    generation,
                    best_weights,
                    best_fitness,
                    avg_fitness,
                    prev_genome_id,
                    prev_fitness,
                )
            )
        else:
            loop.run_until_complete(
                _persist_biological_memory_async(
                    generation,
                    best_weights,
                    best_fitness,
                    avg_fitness,
                    prev_genome_id,
                    prev_fitness,
                )
            )
    except RuntimeError:
        asyncio.run(
            _persist_biological_memory_async(
                generation,
                best_weights,
                best_fitness,
                avg_fitness,
                prev_genome_id,
                prev_fitness,
            )
        )


class GARunner:
    """Executa o ciclo evolutivo do GA Tuning.

    Uso:
        runner = GARunner()
        runner.ensure_initialized()
        runner.step()  # 1 geração
    """

    def __init__(self):
        self.population = Population()
        self.initialized = False
        self._task_counter = 0
        self._prev_genome_id: Optional[str] = None
        self._prev_best_fitness: Optional[float] = None

    def ensure_initialized(self):
        if not self.initialized:
            genome = _load_genome()
            if genome and "weights" in genome:
                self.population.individuals = [Individual(weights=genome["weights"])]
                for _ in range(self.population.size - 1):
                    self.population.individuals.append(
                        Population._random_individual(self.population)
                    )
                self.population.generation = genome.get("generation", 0)
                logger.info(
                    "[GA] População carregada do genoma salvo (gen=%d)",
                    self.population.generation,
                )
            else:
                self.population.initialize()
                logger.info(
                    "[GA] População inicializada com %d indivíduos",
                    self.population.size,
                )
            self.initialized = True

    def step(self) -> dict[str, Any]:
        """Executa uma geração do GA.

        Returns:
            Dict com {best_weights, best_fitness, generation, avg_fitness}.
        """
        self.ensure_initialized()

        prev_generation = self.population.generation
        prev_genome_id = self._prev_genome_id

        for ind in self.population.individuals:
            ind.fitness = _compute_fitness_from_metrics(ind)
            ind.generation = self.population.generation

        best = self.population.best()
        avg_fit = self.population.avg_fitness()

        self.population.individuals = evolve_population(self.population.individuals)
        self.population.generation += 1

        result = {
            "best_weights": best.to_dict(),
            "best_fitness": round(best.fitness, 4),
            "generation": self.population.generation,
            "avg_fitness": round(avg_fit, 4),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        _save_genome(
            {
                "weights": best.weights,
                "fitness": best.fitness,
                "generation": self.population.generation,
                "timestamp": result["timestamp"],
            }
        )

        telemetry = _load_telemetry()
        telemetry["generations"].append(result)
        telemetry["best_fitness_history"].append(best.fitness)
        telemetry["avg_fitness_history"].append(avg_fit)
        telemetry["last_generation"] = self.population.generation
        if len(telemetry["generations"]) > 1000:
            telemetry["generations"] = telemetry["generations"][-1000:]
        _save_telemetry(telemetry)

        _apply_epigenetic_weights(best.to_dict())

        # Persistência nos sistemas de memória biológica
        genome_id = f"ga_gen_{self.population.generation}"
        _persist_biological_memory_sync(
            generation=self.population.generation,
            best_weights=best.to_dict(),
            best_fitness=best.fitness,
            avg_fitness=avg_fit,
            prev_genome_id=prev_genome_id,
            prev_fitness=self._prev_best_fitness,
        )
        self._prev_genome_id = genome_id
        self._prev_best_fitness = best.fitness

        logger.info(
            "[GA] Geração %d | best_fitness=%.4f | avg_fitness=%.4f | pesos=%s",
            self.population.generation,
            best.fitness,
            avg_fit,
            best.to_dict(),
        )

        return result

    def run_n_generations(self, n: int = 10) -> list[dict[str, Any]]:
        """Executa N gerações consecutivas.

        Returns:
            Lista de resultados de cada geração.
        """
        results = []
        for _ in range(n):
            results.append(self.step())
        return results

    def task_hook(self):
        """Hook chamado a cada N tasks para evoluir automaticamente."""
        self._task_counter += 1
        if self._task_counter % GENERATION_INTERVAL == 0:
            self.step()

    @staticmethod
    def load_best_genome() -> dict[str, Any]:
        """Carrega o melhor genoma salvo.

        Returns:
            Dict com as chaves: weights, fitness, generation, updated.
        """
        genome = _load_genome()
        return (
            genome
            if genome
            else {
                "weights": [0.25, 0.25, 0.25, 0.25],
                "fitness": 0.0,
                "generation": 0,
                "updated": "",
            }
        )


runner = GARunner()
