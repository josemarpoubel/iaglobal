"""
Task Breakdown Node — Executa a decomposição analítica e quebra estruturada da tarefa principal.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_task_breakdown(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a decomposição de subtarefas de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso do planejamento para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "task_breakdown_planner_llm"
    
    # Lazy import mantido para preservar o ciclo de inicialização limpa do ecossistema
    from iaglobal.agents.planner_agent import PlannerAgent

    logger.info("[TASK_BREAKDOWN] Iniciando decomposição atômica e estruturação de subtarefas...")
    
    # Coleta os dados de forma resiliente do contexto ou das memórias
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))

    try:
        # Inicializa o agente planejador especializado
        agent = PlannerAgent()
        
        # Como quebras de tarefas realizam inferências e análise de escopo densas,
        # garantimos execução assíncrona ou desviamos com segurança para Thread Pool
        if asyncio.iscoroutinefunction(agent.criar_plano_execucao):
            result = await agent.criar_plano_execucao(task)
        else:
            result = await asyncio.to_thread(agent.criar_plano_execucao, task)
            
        logger.info("[TASK_BREAKDOWN] Decomposição de tarefas finalizada com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict) or result is not None

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result.get("output", "Quebra de tarefas concluída") if isinstance(result, dict) else str(result),
            "task_breakdown": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.005)  # Custo de inferência estimado para decomposição
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[TASK_BREAKDOWN] Falha crítica no pipeline do Task Breakdown Node: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de quebra de tarefas",
            "task_breakdown": {"error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

