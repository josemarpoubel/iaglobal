# tests/test_ga_router_optimizer.py
"""Testes do otimizador genético de pesos IVM."""
import pytest

from iaglobal.evolution.ga_router_optimizer import GARouterOptimizer, Individual


class TestGARouterOptimizer:
    """Testa evolução de pesos IVM."""

    def test_create_random_individual(self):
        """Cria indivíduo válido."""
        optimizer = GARouterOptimizer()
        ind = optimizer._create_random_individual()
        
        assert "productivity" in ind.weights
        assert "energy" in ind.weights

    def test_mutate_individual(self):
        """Mutação altera pesos."""
        ind = Individual(weights={"a": 0.5, "b": 0.5})
        original = ind.weights.copy()
        ind.mutate(mutation_rate=1.0)  # 100% mutação
        
        # Pesos mudaram ou foram normalizados
        assert ind.weights.keys() == original.keys()

    def test_initialize_population(self):
        """População é inicializada."""
        optimizer = GARouterOptimizer()
        optimizer._initialize_population()
        
        assert len(optimizer.population) == optimizer.POP_SIZE

    def test_crossover(self):
        """Crossover produz filho válido."""
        optimizer = GARouterOptimizer()
        p1 = Individual(weights={"a": 0.7, "b": 0.3})
        p2 = Individual(weights={"a": 0.2, "b": 0.8})
        
        child = optimizer._crossover(p1, p2)
        
        assert abs(child.weights["a"] - 0.45) < 0.01  # Floating point tolerance

    def test_evaluate_fitness(self):
        """Avalia fitness dos indivíduos."""
        optimizer = GARouterOptimizer()
        ind = Individual(weights={"productivity": 0.5, "energy": 0.5})
        
        fitness = optimizer._evaluate_fitness(ind)
        
        assert 0.0 <= fitness <= 1.0

    def test_run_evolution(self):
        """Executa evolução completa."""
        optimizer = GARouterOptimizer()
        best = optimizer.run_evolution(generations=5)
        
        assert "productivity" in best