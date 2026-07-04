# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_adaptive_router.py
"""
no_adaptive_router — Nó de roteamento adaptativo baseado em IVM.

Executa o algoritmo de seleção ótima de provedores.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from iaglobal.cognition.adaptive_router import adaptive_router

logger = logging.getLogger(__name__)


async def run_adaptive_router(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa roteamento adaptativo via IVM.
    
    Args:
        context: {"task_type": str, "required_mhc": bool}
    
    Returns:
        {"selected_provider": str, "ivm": float}
    """
    task_type = context.get("task_type", "general")
    required_mhc = context.get("required_mhc", True)
    
    selected = adaptive_router.select_optimal_provider(task_type, required_mhc)
    
    metrics = adaptive_router.get_provider_metrics(selected)
    ivm = adaptive_router.calculate_ivm(selected, metrics)
    
    logger.info(f"[ADAPTIVE-ROUTER] Selected {selected} (IVM={ivm})")
    
    return {
        "selected_provider": selected,
        "ivm": ivm,
        "task_type": task_type,
        "execution_metrics": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "routing_decision": True,
        },
    }