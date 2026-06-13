# iaglobal/tests/test_graphs_refactor.py
"""Testes para refatoração do builder.py em nodes/edges/registry."""
import pytest
from iaglobal.graphs.registry import NODE_REGISTRY, register_node, get_node
from iaglobal.graphs.edges import EDGES, validate_edges


class TestRegistry:
    def test_registry_has_core_nodes(self):
        assert "search" in NODE_REGISTRY
        assert "debugger" in NODE_REGISTRY
        assert "evaluator" in NODE_REGISTRY

    def test_register_node_adds_to_registry(self):
        register_node("custom_test", lambda: None)
        assert "custom_test" in NODE_REGISTRY

    def test_get_node_returns_factory_result(self):
        node = get_node("search")
        assert node is not None
        assert hasattr(node, "name")


class TestEdges:
    def test_edges_not_empty(self):
        assert len(EDGES) > 0

    def test_edges_validate(self):
        node_set = validate_edges(EDGES)
        assert len(node_set) >= 10  # Deve ter pelo menos 10 nós únicos

    def test_edges_are_tuples(self):
        for edge in EDGES[:5]:
            assert isinstance(edge, tuple)
            assert len(edge) == 2
            assert edge[0] and edge[1]  # Não vazio