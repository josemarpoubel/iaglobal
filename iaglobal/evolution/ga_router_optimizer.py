# iaglobal/evolution/ga_router_optimizer.py
"""
GARouterOptimizer — Algoritmo genético para otimização dos pesos IVM.

Cada indivíduo = vetor de pesos [P, E, C, I]
Fitness = desempenho do roteamento nas últimas 100 execuções
Elitismo mantém os melhores, crossover gera variações
"""

import random
import logging
from typing import Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RouterIndividual:
    """Indivíduo do GA para otimização de router (vetor de pesos IVM nomeados)."""

    weights: Dict[str, float]
    fitness: float = 0.0

    def mutate(self, mutation_rate: float = 0.1) -> None:
        """Mutação gaussiana nos pesos."""
        for key in self.weights:
            if random.random() < mutation_rate:
                self.weights[key] += random.gauss(0, 0.05)
        self._normalize()

    def _normalize(self) -> None:
        """Normaliza pesos para somar 1.0."""
        total = sum(self.weights.values())
        if total > 0:
            for key in self.weights:
                self.weights[key] /= total


class GARouterOptimizer:
    """
    Otimizador genético dos pesos IVM.

    Operação:
    1. Population inicial aleatória
    2. Avalia fitness via métricas de routing
    3. Seleção -> Crossover -> Mutação
    4. Elitismo: top 20% preservados
    """

    POP_SIZE = 20
    GENERATIONS = 50
    MUTATION_RATE = 0.1

    def __init__(self):
        self.population: List[Individual] = []
        self._history: List[Dict[str, Any]] = []

    def _create_random_individual(self) -> Individual:
        weights = {
            "productivity": random.random(),
            "energy": random.random(),
            "cooperation": random.random(),
            "immunity": random.random(),
        }
        return Individual(weights=weights)

    def _initialize_population(self) -> None:
        self.population = [
            self._create_random_individual() for _ in range(self.POP_SIZE)
        ]

    def _evaluate_fitness(self, individual: Individual) -> float:
        """Calcula fitness baseado em métricas históricas."""
        # Simulação: usar dados do provider_metrics
        try:
            from iaglobal.providers.provider_metrics import metrics

            provider_data = metrics.get_all_metrics()
        except Exception:
            return 0.5

        scores = []
        for provider, data in provider_data.items():
            if data.get("success", 0) > 0:
                score = (
                    data.get("success", 0) * individual.weights["productivity"]
                    + min(1, 20.0 / data.get("avg_latency", 10))
                    * individual.weights["energy"]
                )
                scores.append(score)

        fitness = sum(scores) / len(scores) if scores else 0.5
        individual.fitness = fitness
        return fitness

    def _select_parents(self) -> List[Individual]:
        sorted_pop = sorted(self.population, key=lambda x: x.fitness, reverse=True)
        return sorted_pop[: max(2, self.POP_SIZE // 5)]

    def _crossover(self, p1: Individual, p2: Individual) -> Individual:
        child_weights = {}
        for key in p1.weights:
            child_weights[key] = (p1.weights[key] + p2.weights[key]) / 2
        return Individual(weights=child_weights)

    def evolve_next_generation(self) -> Dict[str, float]:
        """
        Executa uma geração do GA.

        Returns:
            Pesos do melhor indivíduo
        """
        if not self.population:
            self._initialize_population()

        # Avaliar
        for ind in self.population:
            self._evaluate_fitness(ind)

        # Selecionar pais
        parents = self._select_parents()
        if len(parents) < 2:
            return self.population[0].weights

        # Elitismo: top 20%
        elite = sorted(self.population, key=lambda x: x.fitness, reverse=True)[:4]

        # Nova população
        new_pop = list(elite)
        while len(new_pop) < self.POP_SIZE:
            p1, p2 = random.sample(parents, 2)
            child = self._crossover(p1, p2)
            child.mutate(self.MUTATION_RATE)
            new_pop.append(child)

        self.population = new_pop

        best = max(self.population, key=lambda x: x.fitness)
        logger.info(
            f"[GA-ROUTER] Best IVM weights: {best.weights} (fitness={best.fitness:.3f})"
        )
        return best.weights

    def run_evolution(self, generations: int = 10) -> Dict[str, float]:
        """Executa X gerações e retorna melhor configuração."""
        self._initialize_population()
        best_weights = self.population[0].weights

        for gen in range(generations):
            best_weights = self.evolve_next_generation()

        return best_weights
