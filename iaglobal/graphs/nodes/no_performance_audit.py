# iaglobal/graphs/nodes/no_performance_audit.py

"""
Performance Audit Node — Executa auditoria estática de performance e riscos de gargalos.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.performance_audit_agent import PerformanceAuditAgent

logger = logging.getLogger(__name__)


async def run_performance_audit(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a auditoria de performance de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e score de risco para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "performance_audit_llm_core"
    
    memory = ctx.get("memory", {})
    code = ""

    # Varre as memórias de forma resiliente em busca do código gerado pelos builders
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
        logger.warning("[PERF_AUDIT] Nenhum código encontrado nas memórias para auditoria de performance.")
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": {"performance_audit_report": {"total_bottlenecks": 0, "status": "skipped"}},
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

    try:
        logger.info("[PERF_AUDIT] Iniciando varredura analítica profunda contra gargalos e vazamentos...")
        agent = PerformanceAuditAgent()
        
        # Como auditorias de código realizam análises estáticas pesadas,
        # desviamos para Thread Pool se o método for síncrono para proteger o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.audit):
            result = await agent.audit(code=code, performance_requirements=[])
        else:
            result = await asyncio.to_thread(agent.audit, code=code, performance_requirements=[])
            
        report = result.get("performance_audit_report", {}) if isinstance(result, dict) else {}
        risk_score = report.get("risk_score", "N/A")
        
        logger.info("[PERF_AUDIT] Auditoria finalizada. Score de risco de performance obtido: %s", risk_score)
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result,
            "performance_audit_report": report,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.003)  # Custo de inferência estimado para a auditoria
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[PERF_AUDIT] Falha crítica no pipeline do Performance Audit Agent: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": {"performance_audit_report": {"total_bottlenecks": 0, "risk_score": 0, "error": str(e)}},
            "performance_audit_report": {"total_bottlenecks": 0, "risk_score": 0, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

