# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_optimization.py

"""
Optimization Node — Executa a modelagem cognitiva de refinações e otimizações de performance.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.performance_design_agent import PerformanceDesignAgent

logger = logging.getLogger(__name__)


async def run_optimization(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o nó analítico de otimização de forma assíncrona e não-bloqueante.
    Mapeia latência e custos de inferência para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "optimization_performance_agent_llm"

    logger.info(
        "[OPTIMIZATION] Iniciando ciclo analítico de otimização de performance e recursos..."
    )

    # Coleta o contexto de forma resiliente das memórias anteriores
    design_context = ctx.get("design_context") or ctx.get("memory", {}).get(
        "architecture", ctx
    )

    try:
        # Inicializa o agente especializado em otimização de estruturas
        agent = PerformanceDesignAgent()

        # Sendo uma rotina analítica síncrona e potencialmente pesada,
        # desviamos a execução para Thread Pool salvaguardando o loop de eventos central
        if asyncio.iscoroutinefunction(agent.analyze):
            result = await agent.analyze(design_context=design_context)
        else:
            result = await asyncio.to_thread(
                agent.analyze, design_context=design_context
            )

        logger.info(
            "[OPTIMIZATION] Análise e modelagem de otimizações concluídas com sucesso."
        )

        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result.get("optimization_report", result)
            if isinstance(result, dict)
            else str(result),
            "optimization": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.004
                ),  # Custo de inferência estimado para o relatório de otimização
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[OPTIMIZATION] Falha crítica no pipeline do Optimization Node: %s", e
        )

        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": {},
            "optimization": {"error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
