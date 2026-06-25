# iaglobal/graphs/nodes/no_immune_exchange.py
"""
no_immune_exchange — Nó de recepção de vacinas imunológicas.

Recebe fingerprints compartilhados de outros nós e os integra à MHC.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from iaglobal.immunity.immune_memory_exchange import immune_memory_exchange

logger = logging.getLogger(__name__)


async def run_immune_exchange(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recebe e processa atualizações imunológicas de nós remotos.
    
    Args:
        context: {"remote_data": dict, "source": str}
    
    Returns:
        {"imported": int, "accepted": bool}
    """
    remote_data = context.get("remote_data", {})
    source = context.get("source", "unknown")
    
    imported = await immune_memory_exchange.import_immune_memory(remote_data, source)
    
    return {
        "imported": imported,
        "accepted": imported > 0,
        "source": source,
        "execution_metrics": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "immune_exchange": True,
        },
    }