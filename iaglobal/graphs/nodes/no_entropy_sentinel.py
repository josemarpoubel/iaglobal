# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_entropy_sentinel.py
"""
Nó de Vigilância de Entropia — Verifica integridade genética do sistema.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from iaglobal.immunity.entropy_sentinel import entropy_sentinel

logger = logging.getLogger(__name__)


async def run_entropy_sentinel(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Varre a árvore de arquivos para detectar manipulação.

    Returns:
        {"healthy": bool, "violations": list, "genesis_hash": str}
    """
    # Executar varredura diretamente (arquivo I/O é rápido)
    result = entropy_sentinel.scan_critical_files()

    # Gerar ID soberano para o nó atual
    node_id = entropy_sentinel.get_sober_agent_id("entropy_sentinel")

    return {
        "healthy": result.get("healthy", False),
        "violations": result.get("violations", []),
        "genesis_hash": result.get("genesis_hash"),
        "node_id": node_id,
        "files_scanned": result.get("files_scanned", 0),
        "execution_metrics": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entropy_scan": True,
        },
    }
