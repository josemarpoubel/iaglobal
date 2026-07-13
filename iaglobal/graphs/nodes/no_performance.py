# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_performance.py

"""
Performance Audit Node — Executa auditorias de performance e eficiência no código gerado.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.performance_audit_agent import PerformanceAuditAgent

logger = logging.getLogger(__name__)


async def run_performance(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a auditoria de performance de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso analítico para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "performance_audit_agent_llm"

    logger.info(
        "[PERFORMANCE] Iniciando auditoria de eficiência e performance no código..."
    )

    # Coleta os dados de forma resiliente do contexto ou das memórias
    coder_data = (
        ctx.get("coder")
        or ctx.get("memory", {}).get("coder", {})
        or ctx.get("memory", {}).get("multi_coder", {})
    )
    code = (
        coder_data.get("output", "")
        if isinstance(coder_data, dict)
        else str(coder_data or "")
    )

    performance_reqs = ctx.get("performance_requirements", [])

    try:
        # Inicializa o agente especializado em auditoria de performance
        agent = PerformanceAuditAgent()

        # Como auditorias de código realizam análises estáticas pesadas,
        # desviamos para Thread Pool se o método for síncrono para proteger o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.audit):
            result = await agent.audit(
                code=code, performance_requirements=performance_reqs
            )
        else:
            result = await asyncio.to_thread(
                agent.audit, code=code, performance_requirements=performance_reqs
            )

        logger.info("[PERFORMANCE] Auditoria de performance finalizada com sucesso.")

        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict) or result is not None

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result.get("output", "Auditoria de performance concluída")
            if isinstance(result, dict)
            else str(result),
            "performance": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.003
                ),  # Custo de inferência estimado para a auditoria
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[PERFORMANCE] Falha crítica no pipeline do Performance Audit Node: %s", e
        )

        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de auditoria de performance",
            "performance": {"error": str(e), "success": False},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
