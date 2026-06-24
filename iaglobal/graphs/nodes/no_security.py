# iaglobal/graphs/nodes/no_security.py

"""
Security Audit Node — Executa auditoria e varredura estática de vulnerabilidades no código.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.security_audit_agent import SecurityAuditAgent

logger = logging.getLogger(__name__)


async def run_security(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a auditoria de segurança de forma assíncrona e não-bloqueante.
    Mapeia latência, custos de inferência e sucesso analítico para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "security_audit_agent_llm"
    
    logger.info("[SECURITY] Iniciando auditoria de vulnerabilidades e brechas no código...")
    
    # Coleta os dados de forma resiliente do contexto ou das memórias
    coder_data = ctx.get("coder") or ctx.get("memory", {}).get("coder", {}) or ctx.get("memory", {}).get("multi_coder", {})
    code = coder_data.get("output", "") if isinstance(coder_data, dict) else str(coder_data or "")
    
    security_reqs = ctx.get("security_requirements", [])

    try:
        # Inicializa o agente especializado em auditoria de segurança
        agent = SecurityAuditAgent()
        
        # Como auditorias de código realizam análises estáticas pesadas,
        # desviamos para Thread Pool se o método for síncrono para proteger o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.audit):
            result = await agent.audit(code=code, security_requirements=security_reqs)
        else:
            result = await asyncio.to_thread(agent.audit, code=code, security_requirements=security_reqs)
            
        logger.info("[SECURITY] Auditoria estática de segurança finalizada com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict) or result is not None

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result.get("output", "Auditoria de segurança concluída") if isinstance(result, dict) else str(result),
            "security": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.003)  # Custo de inferência estimado para a auditoria
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[SECURITY] Falha crítica no pipeline do Security Node: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de auditoria de segurança",
            "security": {"error": str(e), "success": False},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

