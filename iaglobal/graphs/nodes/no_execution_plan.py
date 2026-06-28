# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
#  iaglobal/graphs/nodes/no_execution_plan.py

"""
Execution Plan Node — Desenha o plano tático e sequencial de execução do pipeline.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_execution_plan(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a geração do plano de execução de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso do planejamento para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "execution_planner_agent_llm"
    
    # Lazy import mantido para preservar o ciclo de inicialização limpa do ecossistema
    from iaglobal.agents.planner_agent import PlannerAgent

    logger.info("[EXECUTION_PLAN] Iniciando desenho analítico do plano de execução...")
    
    # Coleta os dados de forma resiliente do contexto ou das memórias
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))

    try:
        # Inicializa o agente planejador especializado
        agent = PlannerAgent()
        
        # Como planos de execução realizam inferências e análise de requisitos densas,
        # garantimos execução assíncrona ou desviamos com segurança para Thread Pool
        if asyncio.iscoroutinefunction(agent.criar_plano_execucao):
            result = await agent.criar_plano_execucao(task)
        else:
            result = await asyncio.to_thread(agent.criar_plano_execucao, task)
            
        logger.info("[EXECUTION_PLAN] Plano de execução técnica finalizado com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict) or result is not None

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result.get("output", "Plano de execução concluído") if isinstance(result, dict) else str(result),
            "execution_plan": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.005)  # Custo de inferência estimado para o plano
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[EXECUTION_PLAN] Falha crítica no pipeline do Execution Plan Node: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de planejamento de execução",
            "execution_plan": {"error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

