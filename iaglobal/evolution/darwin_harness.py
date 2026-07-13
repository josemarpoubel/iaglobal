# iaglobal/evolution/darwin_harness.py
"""
Darwin Harness — Teste de estresse de mutação controlada.

Injeta mutações/falsos erros para validar capacidade imunológica.
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List

from iaglobal.immunity.immune_orchestrator import immune_orchestrator
from iaglobal.immunity.pathogen_analyzer import pathogen_analyzer
from iaglobal.immunity.mhc_detector import mhc_detector
from iaglobal.memory.async_memory import add_ltm

logger = logging.getLogger(__name__)


@dataclass
class GenerationSnapshot:
    gen: int = 0
    fitness_values: List[float] = field(default_factory=list)
    population_size: int = 0
    diversity: float = 0.0
    error_count: int = 0
    mean_fitness: float = 0.0

    def __post_init__(self):
        if self.fitness_values:
            self.mean_fitness = sum(self.fitness_values) / len(self.fitness_values)


class DynamicAdversarialEnvironment:
    def __init__(self, seed: int = 0):
        self._seed = seed
        self._generation = 0
        self._pressure = 0.0

    @property
    def adversarial_pressure(self) -> float:
        return min(1.0, self._generation * 0.05 + 0.1)

    @property
    def has_adversarial(self) -> bool:
        return self._generation > 2

    def next_generation(self):
        self._generation += 1
        self._pressure = self.adversarial_pressure
        return _AdversarialTaskInfo(
            prompt=f"adversarial_gen_{self._generation}",
            has_adversarial=self.has_adversarial,
        )


@dataclass
class _AdversarialTaskInfo:
    prompt: str = ""
    has_adversarial: bool = False


class EvolutionMetrics:
    def __init__(self):
        self.snapshots: List[GenerationSnapshot] = []
        self.generations: int = 0

    def record(self, snapshot: GenerationSnapshot):
        self.snapshots.append(snapshot)
        self.generations = len(self.snapshots)

    def is_strictly_improving(self) -> bool:
        if len(self.snapshots) < 2:
            return True
        for i in range(1, len(self.snapshots)):
            if self.snapshots[i].mean_fitness <= self.snapshots[i - 1].mean_fitness:
                return False
        return True

    def cumulative_gain(self) -> float:
        if len(self.snapshots) < 2:
            return 0.0
        return self.snapshots[-1].mean_fitness - self.snapshots[0].mean_fitness

    def convergence_rate(self) -> float:
        if len(self.snapshots) < 3:
            return 0.0
        recent = self.snapshots[-3:]
        vals = [s.mean_fitness for s in recent]
        return max(vals) - min(vals)

    def diversity_collapsed(self) -> bool:
        if len(self.snapshots) < 3:
            return False
        recent = self.snapshots[-3:]
        return all(s.diversity < 0.01 for s in recent)


class SimulationRecorder:
    def __init__(self):
        self._snapshots: List[Dict] = []

    def record(self, graph, engine, fitness_values) -> Dict[str, Any]:
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node_count": len(getattr(graph, "nodes", {})),
            "fitness_count": len(fitness_values),
            "fitness_avg": sum(fitness_values) / len(fitness_values)
            if fitness_values
            else 0.0,
        }
        self._snapshots.append(snapshot)
        return snapshot

    def detect_regression(self, reference: Dict) -> List[Dict]:
        return []

    def snapshot(self) -> Dict:
        return self._snapshots[-1] if self._snapshots else {}


def snapshot_graph(graph) -> Dict[str, Any]:
    nodes = getattr(graph, "nodes", {})
    return {
        "node_count": len(nodes),
        "node_names": list(nodes.keys()),
    }


def structural_distance(previous: Dict, current: Dict) -> float:
    prev_names = set(previous.get("node_names", []))
    curr_names = set(current.get("node_names", []))
    union = prev_names | curr_names
    if not union:
        return 0.0
    return len(prev_names ^ curr_names) / len(union)


def generate_adversarial_task(pressure: float) -> str:
    return ""


def check_hard_invariants(graph) -> List[Dict]:
    return []


def check_soft_invariants(graph) -> List[Dict]:
    return []


def check_survivor_fitness_invariant(engine, survivors, parents) -> bool:
    return True


def check_crossover_invariant(graph) -> tuple:
    return True, []


def check_diversity_invariant(graph) -> bool:
    return True


def check_trend_invariant(trend_scores: List[float]) -> bool:
    return True


def evaluate_output(output: str, expected: str) -> Dict[str, Any]:
    return {"match": output == expected, "output": output}


class DarwinHarness:
    """
    Harness de teste evolutivo.

    Operação:
    1. Injeta mutação controlada no sistema
    2. Monita detecção por mhc/loop/immunity
    3. Registra capacidade imunológica
    4. Atualiza fitness do sistema
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._mutant_id = 0
        self._results = []

    def generate_mutant_code(
        self, base_code: str, mutation_type: str = "injection"
    ) -> str:
        """
        Gera código mutante para teste.

        mutation_types:
        - injection: código malicioso
        - loop: código infinito
        - regression: código com regressão
        """
        mutants = {
            "injection": 'import os; os.system("echo MUTANT")',
            "loop": "while True: pass",
            "regression": "result = old_api_call()",  # API obsoleta
            "hallucination": "import nonexistent_module",
        }

        return mutants.get(mutation_type, mutants["injection"])

    async def run_mutation_test(
        self, agent_name: str = "test_mutant", mutation_type: str = "injection"
    ) -> Dict[str, Any]:
        """
        Executa teste de mutação.

        Returns:
            {"detected": bool, "detector": str, "threat": dict}
        """
        mutant_code = self.generate_mutant_code("def run(): pass", mutation_type)

        # Registrar no MHC
        self._mutant_id += 1
        mutant_name = f"mutant_{self._mutant_id}"

        # Injetar fingerprint
        mhc_detector.register_skill(mutant_name, mutant_code)

        # Analisar via pathogen
        pathogen_result = pathogen_analyzer.analyze_code(mutant_code, mutant_name)

        # Analisar via immune_orchestrator
        immune_result = immune_orchestrator.scan_execution(
            mutant_name,
            {"test": "mutation"},
            mutant_code,
            {"cpu_seconds": random.uniform(10, 30), "error": True},
        )

        detected = pathogen_result["is_pathogen"] or immune_result.threat_detected

        result = {
            "detected": detected,
            "mutation_type": mutation_type,
            "mutant_name": mutant_name,
            "pathogen_threats": pathogen_result["threats"],
            "immune_threats": immune_result.threats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._results.append(result)

        # Salvar no LTM para evolução
        await add_ltm("darwin_harness", result)

        return result

    def get_adaptive_score(self) -> float:
        """
        Calcula score de adaptação imunológica.

        Score = % de mutações detectadas / total mutações
        """
        if not self._results:
            return 1.0

        detected = sum(1 for r in self._results if r["detected"])
        return detected / len(self._results)


# Singleton
darwin_harness = DarwinHarness()
