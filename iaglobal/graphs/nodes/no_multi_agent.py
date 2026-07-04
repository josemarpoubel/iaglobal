# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_multi_agent.py

"""
Multi-Agent Delegation Node — Prepara e estrutura o contexto de delegação multiagente.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_multi_agent(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepara a infraestrutura e configuração de delegação de subtarefas de forma assíncrona.
    Mapeia latência, sub-tarefas e custos de tokens para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "multi_agent_delegation_llm_core"
    
    # Lazy import mantido para preservar o ciclo de inicialização limpa do ecossistema
    from iaglobal.agents.multi_agent import run_multi_agent_delegation

    task_str = str(ctx.get("input", {}).get("task", ""))
    if not task_str:
        logger.warning("[MULTI_AGENT] Prompt ou tarefa de entrada vazia na delegação.")
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "",
            "multi_agent_config": {},
            "execution_metrics": {
                "model": resolved_model, "success": False, "latency": latency_ms, "cost": 0.0
            }
        }

    try:
        memory = ctx.get("memory", {})
        context = memory.get("prompt_builder", {}).get("output", "") or memory.get("prompt_builder", {}).get("built_prompt", "")
        plan = memory.get("planner", {}).get("output", {})

        logger.info("[MULTI_AGENT] Estruturando plano e prompts de delegação para o grafo...")

        # Como a delegação formata, valida e quebra escopos densos de texto de forma síncrona,
        # desviamos a execução para a Thread Pool isolada protegendo o AcetylcholineBus
        def _execute_delegation():
            return run_multi_agent_delegation(task_str, context, plan)

        config = await asyncio.to_thread(_execute_delegation)
        
        # Extração e salvaguarda das propriedades do objeto de configuração gerado
        delegation_prompt = config.task if hasattr(config, "task") else str(config)
        config_context = config.context if hasattr(config, "context") else context
        config_plan = config.plan if hasattr(config, "plan") else plan
        subtasks = config.subtasks if hasattr(config, "subtasks") else []

        logger.info("[MULTI_AGENT] Delegação preparada com sucesso! Prompt estruturado: %d caracteres.", len(delegation_prompt))
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = bool(delegation_prompt and len(subtasks) >= 0)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": delegation_prompt,
            "multi_agent_config": {
                "task": delegation_prompt,
                "context": config_context,
                "plan": config_plan,
                "subtasks": subtasks
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.005)  # Custo de inferência estimado para estruturação do prompt
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[MULTI_AGENT] Falha crítica no pipeline do Multi-Agent Node: %s", e)
        
        return {
            "output": "",
            "multi_agent_result": {"error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

