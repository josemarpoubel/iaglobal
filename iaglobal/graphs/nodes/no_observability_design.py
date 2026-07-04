# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_observability_design.py

"""
Observability Design Node — Injeta e planeja a camada de telemetria, logs e monitoramento.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md com telemetria ativa.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.performance_design_agent import PerformanceDesignAgent

logger = logging.getLogger(__name__)


async def run_observability_design(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a modelagem do design de observabilidade de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso de instrumentação para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "observability_design_agent_llm"
    
    logger.info("[OBSERVABILITY_DESIGN] Iniciando desenho cognitivo dos componentes de telemetria...")
    
    # Coleta o contexto de design de forma resiliente das etapas anteriores
    design_context = ctx.get("design_context") or ctx.get("memory", {}).get("security_design", ctx)

    try:
        # Inicializa o agente especializado em performance e design
        agent = PerformanceDesignAgent()
        
        # Como modelagens de observabilidade realizam análises de código e estruturas pesadas,
        # desviamos para Thread Pool se o método for síncrono para proteger o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.analyze):
            result = await agent.analyze(design_context=design_context)
        else:
            result = await asyncio.to_thread(agent.analyze, design_context=design_context)
            
        logger.info("[OBSERVABILITY_DESIGN] Desenho de observabilidade finalizado com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result.get("observability_report", result) if isinstance(result, dict) else str(result),
            "observability_design": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.004)  # Custo de inferência estimado para modelagem
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[OBSERVABILITY_DESIGN] Falha crítica no pipeline do Observability Design Node: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": {},
            "observability_design": {"error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

