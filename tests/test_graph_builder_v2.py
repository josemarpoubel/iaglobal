# iaglobal/tests/test_graph_builder_v2.py
"""Testes para graph_builder_v2.py - builder minimal."""
import pytest
from iaglobal.graphs.graph_builder_v2 import GraphBuilder, build_graph_minimal


class TestGraphBuilderV2:
    def test_build_creates_instance(self):
        builder = GraphBuilder()
        graph = builder.build()
        assert graph is not None
        assert len(graph.nodes) >= 4

    def test_build_has_valid_nodes(self):
        graph = build_graph_minimal()
        assert "debugger" in graph.nodes
        assert "rank" in graph.nodes
        assert "reviewer" in graph.nodes
        assert "tester" in graph.nodes

    def test_nodes_have_depends_on(self):
        graph = build_graph_minimal()
        # Nodes devem ter lista de depends_on
        for node in graph.nodes.values():
            assert hasattr(node, "depends_on")
            assert isinstance(node.depends_on, list)