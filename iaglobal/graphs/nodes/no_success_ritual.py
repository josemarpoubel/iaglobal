# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_success_ritual.py
"""
no_success_ritual — Nó que registra métricas de sucesso ao final do ciclo.

Foca em: Eficiência Energética (economia de energia).
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from iaglobal.obsidian.success_cycle_logger import SuccessCycleLogger, SuccessMetrics
from iaglobal.cognition.adaptive_router import adaptive_router

logger = logging.getLogger(__name__)


async def run_success_ritual(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa ritual de registro de sucesso.
    
    Args:
        context: {"cycle_id": str, "successes": int, "attempts": int}
    
    Returns:
        {"logged": bool, "efficiency": float}
    """
    cycle_id = context.get("cycle_id", f"cycle_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    successes = context.get("successes", 1)
    attempts = context.get("attempts", 1)
    previous_ivm = context.get("previous_ivm", 0.0)
    
    # Calcular métricas
    logger_instance = SuccessCycleLogger()
    
    integrity = logger_instance.calculate_integrity_rate(successes, attempts)
    
    # Obter IVM atual
    current_ivm = 0.5
    for provider in ["groq", "nvidia", "ollama"]:
        try:
            metrics = adaptive_router.get_provider_metrics(provider)
            ivm = adaptive_router.calculate_ivm(provider, metrics)
            current_ivm = max(current_ivm, ivm)
        except Exception:
            pass
    
    growth = logger_instance.calculate_growth_rate(current_ivm, previous_ivm)
    alignment = context.get("alignment", 0.95)  # Default alto
    
    # Eficiência energética (foco no "fazer mais com menos")
    work_units = float(successes)
    energy_units = context.get("energy_units", 1.0)
    efficiency = logger_instance.calculate_energy_efficiency(work_units, energy_units)
    
    metrics = SuccessMetrics(
        integrity_rate=integrity,
        growth_rate=growth,
        alignment_score=alignment,
        energy_efficiency=efficiency,
        cycle_id=cycle_id,
    )
    
    logger_instance.log_success_cycle(metrics)
    
    logger.info(f"[SUCCESS-RITUAL] {cycle_id}: efficiency={efficiency:.2f}, growth={growth:+.3f}")
    
    return {
        "logged": True,
        "efficiency": efficiency,
        "growth_rate": growth,
        "integrity_rate": integrity,
        "execution_metrics": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success_ritual": True,
        },
    }