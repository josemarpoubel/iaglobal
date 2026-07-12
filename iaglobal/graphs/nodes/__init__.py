# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Re-exporta create_skill_node da nodes.py (shadowed pelo package nodes/).
"""
import importlib.util
import sys
from pathlib import Path

_NODES_MODULE_PATH = Path(__file__).resolve().parent.parent / "nodes.py"
_SPEC = importlib.util.spec_from_file_location(
    "iaglobal.graphs._nodes_mod",
    str(_NODES_MODULE_PATH),
)
_NODES_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_NODES_MOD)
sys.modules["iaglobal.graphs._nodes_mod"] = _NODES_MOD

create_skill_node = _NODES_MOD.create_skill_node
Nodes = _NODES_MOD.Nodes

__all__ = ["create_skill_node", "Nodes"]
