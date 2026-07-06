# iaglobal/graphs/graph_builder_v2.py
"""
Builder V2 - Substituto modularizado do builder.py.
Meta: < 300 linhas usando registry + edges + graph_factory.
"""
from typing import Any, Optional
from .execution_graph import ExecutionGraph
from .edges import EDGES, validate_edges
from .registry import NODE_REGISTRY
from .nodes import create_skill_node
from iaglobal.utils.logger import logger


class GraphBuilder:
    """Builder modularizado do pipeline DAG."""

    def __init__(self, orchestrator: Any = None):
        self._orchestrator = orchestrator

    def _load_nodes(self, graph: ExecutionGraph) -> None:
        """Carrega nós do registry com dependências."""
        from iaglobal.graphs.execution_graph import Node
        from iaglobal.graphs.registry import NODE_REGISTRY
        from iaglobal.graphs.nodes import create_skill_node

        for name, node_cls in NODE_REGISTRY.items():
            try:
                node = create_skill_node(name)
                graph.add_node(node)
            except Exception as exc:
                logger.warning("[GRAPH-BUILDER-V2] Falha ao carregar nó '%s': %s", name, exc)

    def _load_edges(self, graph: ExecutionGraph) -> None:
        """Constrói dependências usando EDGES."""
        for src, dst in EDGES:
            if src in graph.nodes and dst in graph.nodes:
                dst_node = graph.nodes[dst]
                if src not in dst_node.depends_on:
                    dst_node.depends_on.append(src)

    def build(self) -> ExecutionGraph:
        """Constrói e valida o grafo."""
        graph = ExecutionGraph()
        logger.info("[GRAPH-BUILDER-V2] Construindo grafo...")
        self._load_nodes(graph)
        self._load_edges(graph)
        validate_edges([(src, dst) for src, dst in EDGES if src in graph.nodes and dst in graph.nodes])
        return graph


def build_graph_minimal(orchestrator: Any = None) -> ExecutionGraph:
    return GraphBuilder(orchestrator).build()