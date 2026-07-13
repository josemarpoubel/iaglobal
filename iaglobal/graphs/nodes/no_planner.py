# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_planner.py

"""
Planner Node — Componente de planejamento estratégico do iaglobal.
Desenha planos de execução com telemetria ativa para o Bandit Policy.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.graphs.comms.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)


async def run_planner(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o agente planejador de forma assíncrona e não-bloqueante.
    Mapeia a complexidade, subtarefas e latência para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "planner_agent_llm"

    # Lazy import mantido para preservar o ciclo de inicialização original
    from iaglobal.agents.planner_agent import PlannerAgent

    task_str = str(ctx.get("input", {}).get("task", ""))
    memory = ctx.get("memory", {})
    contexto_memoria = str(memory.get("knowledge", {}).get("summary", ""))
    erros_anteriores = memory.get("errors", {}).get("planner", [])

    logger.info("[PLANNER] Iniciando decomposição cognitiva da tarefa principal...")

    try:
        agent = PlannerAgent()

        # Executa a inteligência de planejamento (LLM-driven)
        if asyncio.iscoroutinefunction(agent.criar_plano_execucao):
            plan = await agent.criar_plano_execucao(
                task=task_str,
                contexto_memoria=contexto_memoria,
                erros_anteriores=erros_anteriores,
            )
        else:
            plan = await asyncio.to_thread(
                agent.criar_plano_execucao,
                task=task_str,
                contexto_memoria=contexto_memoria,
                erros_anteriores=erros_anteriores,
            )

        complexidade = plan.get("complexidade", "DESCONHECIDA")
        subtarefas = plan.get("subtarefas", []) or []

        logger.info(
            "[PLANNER] Plano gerado com sucesso: complexidade=%s | subtarefas=%d",
            complexidade,
            len(subtarefas),
        )

        # Publicação reativa e assíncrona no AcetylcholineBus para alertar o Coder
        ag_mailbox = memory.get("agentmailbox", {}) or ctx.get("agentmailbox", {})
        bus = ag_mailbox.get("_agent_bus") or ctx.get("_agent_bus")

        if bus is not None:
            msg = AgentMessage(
                sender="planner",
                receiver="coder",
                type="plan_ready",
                payload={"plan": plan, "task": task_str},
            )
            if asyncio.iscoroutinefunction(bus.publish):
                await bus.publish(msg)
            else:
                await asyncio.to_thread(bus.publish, msg)
            logger.info(
                "[PLANNER] Evento 'plan_ready' injetado com sucesso no barramento."
            )

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1 e 5 do AGENTS.md
        return {
            "output": plan,
            "plan": plan,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.005
                ),  # Custos estimados de inferência do Planner
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[PLANNER] Falha crítica no pipeline do Planner Agent: %s", e)

        return {
            "output": {},
            "plan": {},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
