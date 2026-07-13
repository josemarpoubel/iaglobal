# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_meta_director.py
"""
no_meta_director — Nó de propósito macro para o iaGlobal.

Permite que o sistema persiga objetivos complexos com proteção imunológica.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from iaglobal.intention.meta_director import MetaIntent, meta_director

logger = logging.getLogger(__name__)


async def run_meta_director(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa objetivo macro com direção.

    Args:
        context: {"intent": str, "description": str, "max_cycles": int}

    Returns:
        {"objective_queued": bool, "id": str}
    """
    intent = context.get("intent", "explore")
    description = context.get("description", "Autonomous exploration")
    max_cycles = context.get("max_cycles", 50)

    from iaglobal.intention.meta_director import MetaObjective

    obj = MetaObjective(
        intent=MetaIntent(intent),
        description=description,
        success_criteria=["survive", "learn", "adapt"],
        max_cycles=max_cycles,
    )

    queued_id = meta_director.queue_global_objective(intent, description)

    logger.info(f"[META-DIRECTOR] Objetivo macro enfileirado: {intent}")

    return {
        "objective_queued": True,
        "id": queued_id,
        "intent": intent,
        "description": description,
        "execution_metrics": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "meta_director": True,
        },
    }
