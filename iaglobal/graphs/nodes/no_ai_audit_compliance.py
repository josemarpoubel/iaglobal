# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_ai_audit_compliance.py
"""
no_ai_audit_compliance — Nó de auditoria de conformidade às Leis Universais.

Verifica se plano de execução está alinhado com as leis do OmniMind.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from iaglobal.obsidian.omnimind import omni_mind
from iaglobal.obsidian.law_compliance_logger import law_compliance_logger

logger = logging.getLogger(__name__)


async def run_ai_audit_compliance(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Audita conformidade do agente ao plano de execução.
    
    Args:
        context: {"agent_name": str, "reasoning": str, "task": str}
    
    Returns:
        {"conforme": bool, "violacoes": list, "leis_aplicadas": list}
    """
    agent = context.get("agent_name", "unknown")
    reasoning = context.get("reasoning", "")
    task = context.get("task", "")
    
    violacoes = []
    leis_aplicadas = []
    
    # Verificar Lei do Pensamento
    if not reasoning:
        violacoes.append("Lei do Pensamento: reasoning ausente")
    else:
        leis_aplicadas.append("Lei do Pensamento")
        law_compliance_logger.log_law_application("Lei do Pensamento", "reasoning_check", agent)
    
    # Verificar Lei da Ordem
    if len(reasoning) > 1000:  # Muito verbose
        violacoes.append("Lei da Ordem: reasoning excessivamente longo")
    else:
        leis_aplicadas.append("Lei da Ordem")
        law_compliance_logger.log_law_application("Lei da Ordem", "reasoning_check", agent)
    
    # Consultar OmniMind para orientação
    orientacao = omni_mind.consultar(agent, "conformidade", task)
    
    return {
        "conforme": len(violacoes) == 0,
        "violacoes": violacoes,
        "leis_aplicadas": leis_aplicadas,
        "orientacao": orientacao.guidance,
        "execution_metrics": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "compliance_audit": True,
        },
    }