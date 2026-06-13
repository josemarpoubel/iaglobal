# SPDX-License-Identifier: MIT
"""
Teste de integração Nodes → Builder → ExecutionGraph minimal.
Objetivo: verificação que nodes.py canonical + builder.py + topology.py 
funcionam com nós atualizados pra viabilizar DAG de 55 nodes.

Teste roda apenas nodes preview list:
Phase 1: prompt_intake → requirements → architect
Phase 2: planner → execution_plan
"""

import importlib.util
import os as _os
_nodes_path = _os.path.join(_os.path.dirname(__file__), '..', 'iaglobal', 'graphs', 'nodes.py')
_spec = importlib.util.spec_from_file_location('iaglobal.graphs._nodes_mod', _nodes_path)
_nodes_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_nodes_mod)
Nodes = _nodes_mod.Nodes
RUN_NODES = _nodes_mod.RUN_NODES

from iaglobal.graphs.builder import build_pipeline_from_nodes
from iaglobal.graphs.execution_graph import ExecutionGraph


def test_nodes_registry_minimal():
    """Certifica que registry de nodes não está vazio e contém nós críticos."""
    director = Nodes()
    assert "prompt_intake" in director.list_nodes(), "prompt_intake ausente no registry"
    assert "pm" in director.list_nodes()
    assert "requirements" in director.list_nodes()
    print("✅ Nodes registry contém nodes críticos »", list(director.list_nodes().keys())[:10])



def test_run_nodes_list():
    assert isinstance(RUN_NODES, list)
    assert len(RUN_NODES) >= 40, f"Lista RUN_NODES incompleta {len(RUN_NODES)}"
    # subset preview critical
    required = ["prompt_intake", "requirements", "architect", "planner", "execution_plan"]
    for node in required:
        assert node in RUN_NODES, f"{node} ausente em RUN_NODES"
    print("✅ RUN_NODES contém etapas críticas »", required)



def test_build_graph_minimal():
    """Build do Graph a partir de nodes_director usando builder."""
    from iaglobal.graphs.nodes import nodes_director_singleton
    graph = build_pipeline_from_nodes(nodes_director_singleton)
    assert isinstance(graph, ExecutionGraph), f"graph não é ExecutionGraph: {type(graph)}"
    assert len(graph.nodes) >= 20, f"graph não contém expected nodes {len(graph.nodes)}"
    print(f"✅ Graph construído: {len(graph.nodes)} nodes registradas")
    
    # Validar dependências no subset preview
    preview_nodes = {"prompt_intake", "requirements", "architect"}
    for name in preview_nodes:
        node = graph.nodes.get(name)
        assert node is not None
        print(f"   - Nó {name}: depends_on={node.depends_on}")
    
    # Validar topo consistente
    assert graph._graph_hash, "Graph não canonicalizou"


def test_topology_phases():
    from iaglobal.graphs.topology import PHASES
    assert isinstance(PHASES, dict)
    assert "definicao" in PHASES
    assert len(PHASES["definicao"]) >= 10
    assert "planejamento" in PHASES
    assert len(PHASES["planejamento"]) == 3
    assert "construcao" in PHASES
    assert all(k in PHASES for k in ["qualidade", "correcao", "entrega", "metacognicao"])
    print("✅ PHASES contém 7 fases com nodes esperados")


def test_nodes_integrator_compatibility():
    """Nodes registry deve expor handlers dos nós via classmethod."""
    node = Nodes.get_node("prompt_intake")
    assert callable(node), "Nodes.get_node não retornou callable pra prompt_intake"
    print("✅ Integrator compat: node callable registrado")


if __name__ == "__main__":
    import sys
    
    try:
        print("\n🧪 [Phase 1] TEST: Nodes Registry + RUN_NODES\n")
        test_nodes_registry_minimal()
        test_run_nodes_list()
        print("🎯 PASSED Phase 1\n")
        
        print("🧪 [Phase 2] TEST: Topology + Builder → Graph\n")
        test_topology_phases()
        test_build_graph_minimal()
        test_nodes_integrator_compatibility()
        print("🎯 PASSED Phase 2\n")
        
        print("🎉 SUCCESS ❤️ 👉 Nodes → Builder → Graph MINIMAL INTEGRATION OK")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ FAILED ➜ {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
