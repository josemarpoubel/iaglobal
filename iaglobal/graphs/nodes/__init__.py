"""
Proxy de re-export do Director de Nós (nodes.py) para compatibilidade com imports.

O módulo iaglobal.graphs.nodes (graph/nodes.py) contém a classe Nodes,
create_skill_node e toda a lógica de diretor. Como existe um subpacote
nodes/ com os arquivos de nó individuais, este __init__.py re-exporta
o conteúdo do módulo pai para manter a compatibilidade com imports como:
    from iaglobal.graphs.nodes import Nodes, create_skill_node
"""
import importlib.util
import os
import sys


_this_dir = os.path.dirname(os.path.abspath(__file__))
_nodes_module_path = os.path.join(_this_dir, "..", "nodes.py")

if os.path.isfile(_nodes_module_path):
    _spec = importlib.util.spec_from_file_location(
        "iaglobal.graphs.nodes_module", _nodes_module_path
    )
    if _spec and _spec.loader:
        _module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_module)
        # Re-exporta símbolos públicos do módulo pai
        for _attr in dir(_module):
            if not _attr.startswith("_"):
                globals()[_attr] = getattr(_module, _attr)
        # Garante export dos símbolos principais
        for _symbol in ("Nodes", "create_skill_node", "logger"):
            if hasattr(_module, _symbol):
                globals()[_symbol] = getattr(_module, _symbol)
