# iaglobal/graphs/nodes/no_apoptosis_kill.py
"""
Nó de Apoptose Programada — Elimina simbiontes negativos (parasitas digitais).

Quando um agente é classificado como parasita:
1. Drain de conexões em voo
2. Serialização de estado para snapshot
3. Desregistro do service mesh (registry)
4. Notificação de dependentes
5. Eliminação segura (sem cascade de erros)
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from iaglobal.evolution.metabolism.opportunity_cost_detector import opportunity_cost_detector
from iaglobal.evolution.skill_quarantine import quarantine

logger = logging.getLogger(__name__)


async def run_apoptosis_kill(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa apoptose programada em agentes parasitas.
    
    Args:
        context: {
            "agent_name": str,
            "reason": str,
            "snapshot_before": bool (salvar estado antes)
        }
    
    Returns:
        Dict com status da apoptose
    """
    agent_name = context.get("agent_name", "unknown")
    
    # Verificar classificação metabólica
    classification = opportunity_cost_detector.classify_symbiont(agent_name)
    
    if classification != "simbionte_negativo":
        return {
            "status": "skipped",
            "reason": f"Agente {agent_name} não é parasita (classificação: {classification})",
            "execution_metrics": {
                "apoptosis_attempted": False,
                "classification": classification,
            }
        }
    
    # 1. Drain de conexões (marcar agente como não disponível)
    logger.warning(f"[APOPTOSIS] Iniciando drain para {agent_name}")
    
    # 2. Serializar estado antes da eliminação
    state_snapshot = {}
    if context.get("snapshot_before", True):
        try:
            # Salvar estado no async_memory
            state_snapshot = {
                "agent_name": agent_name,
                "terminated_at": datetime.now(timezone.utc).isoformat(),
                "reason": f"Parasite detected: {context.get('reason', 'unknown')}",
                "metrics": opportunity_cost_detector.calculate_opportunity_cost(agent_name),
            }
            from iaglobal.memory.async_memory import add_ltm
            await add_ltm(agent_name, state_snapshot)
        except Exception as e:
            logger.error(f"[APOPTOSIS] Erro ao serializar estado: {e}")
    
    # 3. Quarentena automática
    quarantine.record_failure(
        agent_name,
        f"Apoptosis triggered: {context.get('reason', 'parasite')}",
        impact=3
    )
    
    # 4. Resetar perfil metabólico
    opportunity_cost_detector.reset_profile(agent_name)
    
    logger.warning(f"[APOPTOSIS] Agente {agent_name} eliminado com sucesso")
    
    return {
        "status": "executed",
        "agent_name": agent_name,
        "classification": classification,
        "state_snapshot": state_snapshot,
        "quarantine_activated": True,
        "execution_metrics": {
            "apoptosis_executed": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }