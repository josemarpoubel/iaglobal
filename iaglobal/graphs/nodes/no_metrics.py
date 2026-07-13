# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_metrics.py

"""
Metrics Node — Executa auditorias de performance no código gerado.
Totalmente integrado às diretrizes de concorrência e telemetria do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.performance_audit_agent import PerformanceAuditAgent

logger = logging.getLogger(__name__)


async def run_metrics(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a auditoria de performance medindo latência e sucesso
    para retroalimentação transparente do JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "performance_audit_agent"

    logger.info("[METRICS] Iniciando auditoria de performance no código gerado...")

    # Extrai o código gerado pelo nó do programador (coder) com fallback seguro
    coder_data = ctx.get("coder", {}) or ctx.get("memory", {}).get("no_coder", {})
    code = coder_data.get("output", "") if isinstance(coder_data, dict) else ""

    try:
        # Inicializa o agente auditor
        agent = PerformanceAuditAgent()

        # Como auditorias de código realizam análises estáticas pesadas,
        # desviamos para Thread Pool se o método for síncrono
        if asyncio.iscoroutinefunction(agent.audit):
            result = await agent.audit(code=code, performance_requirements=[])
        else:
            result = await asyncio.to_thread(
                agent.audit, code=code, performance_requirements=[]
            )

        logger.info("[METRICS] Auditoria concluída com sucesso.")

        latency_ms = (time.time() - start_time) * 1000.0

        return {
            "output": result,
            "metrics": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.002
                ),  # Análise local leve, mas consome processamento
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[METRICS] Falha crítica durante a execução da auditoria: %s", e
        )

        return {
            "output": {},
            "metrics": {},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
