# iaglobal/graphs/nodes/no_immune_check_build.py
"""
Nó de verificação imunológica pós-build - Anti-parasitas digitais na fase de construção.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from iaglobal.immunity.immune_orchestrator import immune_orchestrator
from iaglobal.security.network_guard import NetworkGuard, blindar_rede_sandbox

logger = logging.getLogger(__name__)


async def run_immune_check_build(
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Executa verificação imunológica pós-build.
    
    Args:
        context: Contexto com skill_name, output, metrics
    
    Returns:
        Dict com resultado da verificação imunológica
    """
    skill_name = context.get("skill_name", "code_executor")
    output = context.get("output", "")
    metrics = context.get("metrics", {})
    
    # Garantir isolamento de rede
    guard = NetworkGuard(allow_network=False)
    blindar_rede_sandbox()
    
    # Executar scan imunológico
    report = immune_orchestrator.scan_execution(
        skill_name=skill_name,
        execution_context=context,
        output=output,
        metrics=metrics,
    )
    
    result = {
        "safe": not report.threat_detected,
        "threats": report.threats,
        "quarantine_activated": report.quarantine_activated,
        "execution_metrics": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "immune_check_build": True,
            "threat_count": len(report.threats),
        },
    }
    
    return result