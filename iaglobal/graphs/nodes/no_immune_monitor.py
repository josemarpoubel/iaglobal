# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_immune_monitor.py
"""
Nó de Monitoramento Imunológico Contínuo — rastreia custo-benefício em tempo real.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from iaglobal.metabolism.opportunity_cost_detector import opportunity_cost_detector

logger = logging.getLogger(__name__)


async def run_immune_monitor(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Monitora continuamente agentes por custo de oportunidade.

    Args:
        context: {
            "agent_name": str,
            "cpu_seconds": float,
            "memory_mb": float,
            "file_ops": int,
            "reward_signals": list (opcional)
        }

    Returns:
        Dict com status imunológico
    """
    agent_name = context.get("agent_name", "unknown")

    # Registrar consumo
    opportunity_cost_detector.record_consumption(
        agent_name,
        cpu_seconds=context.get("cpu_seconds", 0),
        memory_mb=context.get("memory_mb", 0),
        file_ops=context.get("file_ops", 0),
    )

    # Registrar rewards se fornecidos
    for signal in context.get("reward_signals", []):
        opportunity_cost_detector.record_reward(agent_name, signal)

    # Verificar classificação
    classification = opportunity_cost_detector.classify_symbiont(agent_name)
    cost_analysis = opportunity_cost_detector.calculate_opportunity_cost(agent_name)

    # Se é parasita, sinalizar para apoptose
    should_trigger_apoptosis = classification == "simbionte_negativo"

    result = {
        "agent_name": agent_name,
        "classification": classification,
        "cost_analysis": cost_analysis,
        "trigger_apoptosis": should_trigger_apoptosis,
        "execution_metrics": {
            "immune_monitor": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    if should_trigger_apoptosis:
        logger.warning(f"[IMMUNE-MONITOR] Parasite detected: {agent_name}")

    return result
