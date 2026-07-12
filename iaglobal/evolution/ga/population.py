# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
GA Population — indivíduos e população para otimização genética dos pesos IVM.

Cada indivíduo = vetor [P, E, C, I] com bounds [0.0, 1.0].
População inicial: 50 indivíduos gerados aleatoriamente.
"""

import random
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class Individual:
    weights: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    fitness: float = 0.0
    generation: int = 0

    WEIGHT_NAMES: ClassVar[list[str]] = ["P", "E", "C", "I"]

    @property
    def ivm_p(self) -> float:
        return self.weights[0]

    @property
    def ivm_e(self) -> float:
        return self.weights[1]

    @property
    def ivm_c(self) -> float:
        return self.weights[2]

    @property
    def ivm_i(self) -> float:
        return self.weights[3]

    def to_dict(self) -> dict:
        return {
            name: round(w, 4)
            for name, w in zip(self.WEIGHT_NAMES, self.weights)
        }

    def clamp(self, lo: float = 0.0, hi: float = 1.0):
        for i in range(len(self.weights)):
            self.weights[i] = max(lo, min(hi, self.weights[i]))


class Population:
    SIZE: int = 50

    def __init__(self, size: int = SIZE):
        self.size = size
        self.individuals: list[Individual] = []
        self.generation = 0

    def initialize(self):
        self.individuals = [self._random_individual() for _ in range(self.size)]

    def _random_individual(self) -> Individual:
        return Individual(
            weights=[random.random() for _ in range(4)],
        )

    def best(self) -> Individual:
        return max(self.individuals, key=lambda x: x.fitness)

    def avg_fitness(self) -> float:
        if not self.individuals:
            return 0.0
        return sum(ind.fitness for ind in self.individuals) / len(self.individuals)

    def top_n(self, n: int) -> list[Individual]:
        return sorted(self.individuals, key=lambda x: x.fitness, reverse=True)[:n]