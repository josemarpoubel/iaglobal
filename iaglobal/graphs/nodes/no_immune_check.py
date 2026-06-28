# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_immune_check.py
"""
Nó de verificação imunológica - Anti-parasitas digitais.

Camada de defesa: LoopDetector → RegressionDetector → HallucinationDetector → MHCDetector → Quarantine
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from iaglobal.immunity.immune_orchestrator import immune_orchestrator
from iaglobal.security.network_guard import NetworkGuard, blindar_rede_sandbox

logger = logging.getLogger(__name__)


async def run_immune_check(
    skill_name: str,
    context: Dict[str, Any],
    output: str,
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Executa verificação imunológica completa.
    
    Args:
        skill_name: Nome da skill sendo executada
        context: Contexto de execução
        output: Output gerado
        metrics: Métricas de performance (cpu_seconds, file_ops, etc)
    
    Returns:
        Dict com:
        - safe: bool - se execução é segura
        - threats: dict - ameaças detectadas
        - quarantine_activated: list - skills colocadas em quarentena
    """
    # Garantir isolamento de rede
    guard = NetworkGuard(allow_network=False)
    if not guard.allow_network:
        blindar_rede_sandbox()
        logger.debug(f"[IMMUNE] Network isolation ativo para {skill_name}")
    
    # Executar scan imunológico
    report = immune_orchestrator.scan_execution(
        skill_name=skill_name,
        execution_context=context,
        output=output,
        metrics=metrics,
    )
    
    # Resultado
    result = {
        "safe": not report.threat_detected,
        "threats": report.threats,
        "quarantine_activated": report.quarantine_activated,
        "execution_metrics": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "immune_check": True,
            "threat_count": len(report.threats),
        },
    }
    
    if report.threat_detected:
        logger.warning(f"[IMMUNE] {skill_name} detectou ameaças: {list(report.threats.keys())}")
    
    return result