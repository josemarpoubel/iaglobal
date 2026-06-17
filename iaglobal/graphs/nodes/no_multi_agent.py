from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


async def run_multi_agent(ctx: Dict[str, Any]) -> Dict[str, Any]:
    from iaglobal.agents.multi_agent import run_multi_agent_delegation

    task_str = str(ctx.get("input", {}).get("task", ""))
    if not task_str:
        logger.warning("[MULTI_AGENT] Empty task")
        return {**ctx, "output": ""}

    try:
        # Prepara delegação para o grafo - NÃO executa agentes diretamente
        memory = ctx.get("memory", {})
        context = memory.get("prompt_builder", {}).get("output", "")
        plan = memory.get("planner", {}).get("output", {})
        
        config = run_multi_agent_delegation(task_str, context, plan)
        
        # Retorna configuração para que o grafo execute as fases downstream
        delegation_prompt = config.task  # O prompt já está estruturado
        logger.info("[MULTI_AGENT] Delegação preparada para grafo: %d chars", len(delegation_prompt))
        
        return {
            **ctx, 
            "output": delegation_prompt, 
            "multi_agent_config": {
                "task": config.task,
                "context": config.context,
                "plan": config.plan,
                "subtasks": config.subtasks
            }
        }
    except Exception as e:
        logger.exception("[MULTI_AGENT] Failed: %s", e)
        return {**ctx, "output": "", "multi_agent_result": ""}
