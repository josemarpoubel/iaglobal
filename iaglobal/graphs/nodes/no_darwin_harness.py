# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_darwin_harness.py
"""
Nó Darwin Harness — Testa imunidade via mutação controlada.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from iaglobal.evolution.darwin_harness import darwin_harness

logger = logging.getLogger(__name__)


async def run_darwin_harness(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa teste de estresse evolutivo.

    Args:
        context: {"mutation_type": str, "agent_name": str}

    Returns:
        Resultado do teste de mutação
    """
    mutation_type = context.get("mutation_type", "injection")
    agent_name = context.get("agent_name", "unknown")

    # Executar teste
    result = await darwin_harness.run_mutation_test(agent_name, mutation_type)

    logger.info(
        f"[DARWIN] Mutation test {mutation_type}: detected={result['detected']}"
    )

    return {
        "test_executed": True,
        "mutation_type": mutation_type,
        "detected": result["detected"],
        "adaptive_score": darwin_harness.get_adaptive_score(),
        "execution_metrics": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "darwin_test": True,
        },
    }
