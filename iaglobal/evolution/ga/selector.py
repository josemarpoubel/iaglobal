# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
GA Selector — Seleção por torneio, blend crossover, mutação gaussiana.

Operadores genéticos modulares para o ciclo evolutivo do GA Tuning.
"""

import random
from typing import Optional

from iaglobal.evolution.ga.population import Individual


def tournament_select(
    population: list[Individual],
    tournament_size: int = 3,
) -> Individual:
    """Seleção por torneio: escolhe o melhor entre k indivíduos aleatórios."""
    candidates = random.sample(population, min(tournament_size, len(population)))
    return max(candidates, key=lambda x: x.fitness)


def blend_crossover(
    p1: Individual,
    p2: Individual,
    alpha: float = 0.5,
) -> Individual:
    """Blend crossover (BLX-α): filho nasce no intervalo expandido entre pais."""
    child_weights = []
    for w1, w2 in zip(p1.weights, p2.weights):
        lo = min(w1, w2) - alpha * abs(w1 - w2)
        hi = max(w1, w2) + alpha * abs(w1 - w2)
        child_weights.append(random.uniform(lo, hi))
    child = Individual(weights=child_weights)
    child.clamp()
    return child


def gaussian_mutate(
    individual: Individual,
    mutation_rate: float = 0.15,
    sigma: float = 0.05,
):
    """Mutação gaussiana com taxa configurável."""
    for i in range(len(individual.weights)):
        if random.random() < mutation_rate:
            individual.weights[i] += random.gauss(0, sigma)
    individual.clamp()


def evolve_population(
    population: list[Individual],
    elite_ratio: float = 0.2,
    tournament_size: int = 3,
    mutation_rate: float = 0.15,
    mutation_sigma: float = 0.05,
    blend_alpha: float = 0.5,
) -> list[Individual]:
    """Evolui uma geração completa: elitismo + crossover + mutação.

    Args:
        population: População atual (avaliada com fitness).
        elite_ratio: Fração dos melhores preservados intactos.
        tournament_size: Tamanho do torneio de seleção.
        mutation_rate: Probabilidade de mutação por gene.
        mutation_sigma: Desvio padrão da mutação gaussiana.
        blend_alpha: Parâmetro alpha do blend crossover.

    Returns:
        Nova população (mesmo tamanho).
    """
    pop_size = len(population)
    elite_count = max(2, int(pop_size * elite_ratio))

    sorted_pop = sorted(population, key=lambda x: x.fitness, reverse=True)
    elite = sorted_pop[:elite_count]

    new_pop = list(elite)
    while len(new_pop) < pop_size:
        p1 = tournament_select(population, tournament_size)
        p2 = tournament_select(population, tournament_size)
        child = blend_crossover(p1, p2, blend_alpha)
        gaussian_mutate(child, mutation_rate, mutation_sigma)
        new_pop.append(child)

    return new_pop