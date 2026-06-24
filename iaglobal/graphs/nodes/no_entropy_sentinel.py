# iaglobal/graphs/nodes/no_entropy_sentinel.py
"""
Nó de Vigilância de Entropia — Verifica integridade genética do sistema.
"""
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from iaglobal.security.entropy_sentinel import entropy_sentinel

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