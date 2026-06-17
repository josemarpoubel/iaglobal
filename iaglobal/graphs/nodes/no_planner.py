from typing import Dict, Any
import logging

from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)


async def run_planner(ctx: Dict[str, Any]) -> Dict[str, Any]:
    from iaglobal.agents.planner_agent import PlannerAgent

    task_str = str(ctx.get("input", {}).get("task", ""))

    memory = ctx.get("memory", {})
    contexto_memoria = str(memory.get("knowledge", {}).get("summary", ""))
    erros_anteriores = memory.get("errors", {}).get("planner", [])

    agent = PlannerAgent()
    plan = await agent.criar_plano_execucao(
        task=task_str,
        contexto_memoria=contexto_memoria,
        erros_anteriores=erros_anteriores,
    )

    logger.info(
        "[PLANNER] Plano gerado: complexidade=%s subtarefas=%d",
        plan.get("complexidade", "DESCONHECIDA"),
        len(plan.get("subtarefas", [])),
    )

    ag_mailbox = memory.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus")
    if bus is not None:
        msg = AgentMessage(
            sender="planner", receiver="coder",
            type="plan_ready",
            payload={"plan": plan, "task": task_str},
        )
        bus.publish(msg)
        logger.info("[PLANNER] Mensagem enviada para coder via bus")

    return {**ctx, "plan": plan, "output": plan}
