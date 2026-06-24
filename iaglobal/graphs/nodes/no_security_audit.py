# iaglobal/graphs/nodes/no_security_audit.py

"""
Security Audit Node — Executa análises estáticas de segurança e vulnerabilidade no código.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.security_audit_agent import SecurityAuditAgent

logger = logging.getLogger(__name__)


async def run_security_audit(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a auditoria de segurança de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e vulnerabilidades encontradas para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "security_audit_agent_llm"
    
    memory = ctx.get("memory", {})
    code = ""

    # Varre as memórias de forma resiliente em busca do código gerado
    sources = ("api_builder", "multi_coder", "coder", "debug_coder", "backend_builder", "frontend_builder")
    for source in sources:
        artifact = memory.get(source, {}).get("output")
        if artifact is None:
            continue
        if isinstance(artifact, str) and artifact.strip():
            code = artifact
            break
        if hasattr(artifact, "code") and artifact.code:
            code = artifact.code
            break

    if not code:
        logger.warning("[SEC_AUDIT] Nenhum código encontrado nas memórias para auditoria de segurança.")
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": {"security_audit_report": {"total_issues": 0, "status": "skipped"}},
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

    try:
        logger.info("[SEC_AUDIT] Iniciando varredura profunda contra vulnerabilidades e brechas...")
        agent = SecurityAuditAgent()
        
        # Como auditorias de segurança executam varreduras estáticas intensivas por regex ou tokens,
        # desviamos para Thread Pool se o método for síncrono para proteger o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.audit):
            result = await agent.audit(code=code, security_requirements=[])
        else:
            result = await asyncio.to_thread(agent.audit, code=code, security_requirements=[])
            
        report = result.get("security_audit_report", {}) if isinstance(result, dict) else {}
        total_issues = report.get("total_issues", 0)
        
        logger.info("[SEC_AUDIT] Auditoria concluída com sucesso. Total de falhas de segurança encontradas: %s", total_issues)
        
        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx)
        return {
            "output": result,
            "security_audit_report": report,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.003)  # Custo estimado de tokens da inferência do auditor
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[SEC_AUDIT] Falha crítica no pipeline do Security Audit Agent: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": {"security_audit_report": {"total_issues": 0, "issues": [], "error": str(e)}},
            "security_audit_report": {"total_issues": 0, "issues": [], "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

