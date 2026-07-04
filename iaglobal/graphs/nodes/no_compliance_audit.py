# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_compliance_audit.py

"""
Compliance Audit Node — Executa auditorias de conformidade legal, privacidade e governança.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.security_audit_agent import SecurityAuditAgent

logger = logging.getLogger(__name__)


async def run_compliance_audit(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a auditoria de conformidade de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e violações regulamentares para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "compliance_audit_agent_llm"
    
    logger.info("[COMPLIANCE_AUDIT] Iniciando varredura regulamentar e auditoria de governança...")
    
    # Coleta o código das memórias ou do contexto direto de forma resiliente
    coder_data = ctx.get("coder") or ctx.get("memory", {}).get("coder", {})
    code = coder_data.get("output", "") if isinstance(coder_data, dict) else str(coder_data or "")

    try:
        # Inicializa o agente auditor de conformidade
        agent = SecurityAuditAgent()
        
        # Como auditorias de conformidade exigem checagens de regras extensivas e pesadas,
        # desviamos para Thread Pool se o método for síncrono para proteger o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.audit):
            result = await agent.audit(code=code, security_requirements=[])
        else:
            result = await asyncio.to_thread(agent.audit, code=code, security_requirements=[])
            
        logger.info("[COMPLIANCE_AUDIT] Auditoria de conformidade finalizada com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        
        # Considera sucesso técnico se o agente conseguiu gerar o dicionário de resultado
        is_success = isinstance(result, dict)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result.get("compliance_report", "Auditoria de conformidade executada"),
            "compliance_audit": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.003)  # Custo estimado de tokens da inferência
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[COMPLIANCE_AUDIT] Falha crítica no pipeline do Compliance Audit Agent: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de auditoria de conformidade",
            "compliance_audit": {"compliant": False, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

