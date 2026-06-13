from typing import Dict, Any
import logging

from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)


async def run_planner(ctx: Dict[str, Any]) -> Dict[str, Any]:
    requirements = ctx.get("requirements") or {}
    architecture = ctx.get("architecture") or {}

    functional = requirements.get("functional", [])
    components = architecture.get("components", [])

    plan = {
        "phases": [
            {
                "name": "setup",
                "tasks": ["inicializar projeto", "configurar ambiente", "instalar dependencias"],
                "estimated_hours": 2,
            },
            {
                "name": "backend",
                "tasks": ["criar models", "implementar endpoints", "adicionar validacoes"],
                "estimated_hours": 8,
            },
            {
                "name": "frontend",
                "tasks": ["criar componentes", "conectar API", "estilizar interface"],
                "estimated_hours": 8,
            },
            {
                "name": "database",
                "tasks": ["criar migrations", "configurar seed", "otimizar queries"],
                "estimated_hours": 4,
            },
            {
                "name": "testing",
                "tasks": ["testes unitarios", "testes integracao", "testes e2e"],
                "estimated_hours": 4,
            },
            {
                "name": "deploy",
                "tasks": ["configurar CI/CD", "deploy staging", "monitoramento"],
                "estimated_hours": 3,
            },
        ],
        "total_estimated_hours": 29,
        "parallel_tracks": len(components),
        "requirements_count": len(functional),
    }

    logger.info("[PLANNER] Plano gerado: %d fases, %d horas estimadas", len(plan["phases"]), plan["total_estimated_hours"])

    memory = ctx.get("memory", {})
    ag_mailbox = memory.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus")
    if bus is not None:
        msg = AgentMessage(
            sender="planner", receiver="coder",
            type="plan_ready",
            payload={"plan": plan, "task": str(ctx.get("input", {}).get("task", ""))},
        )
        bus.publish(msg)
        logger.info("[PLANNER] Mensagem enviada para coder via bus")

    return {**ctx, "plan": plan, "output": plan}
