from typing import Dict, Any
import logging

from iaglobal.agents.orchestrator_agent import OrchestratorAgent
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)

_orchestrator_agent = OrchestratorAgent()


async def run_orchestrator_agent(ctx: Dict[str, Any]) -> Dict[str, Any]:
    enhancement = ctx.get("enhancement") or {}
    requirements = ctx.get("requirements") or {}

    orch = _orchestrator_agent.route(enhancement, requirements)

    logger.info(
        "[ORCHESTRATOR] next_phase=%s active_nodes=%d",
        orch.get("next_phase", "definition"),
        len(orch.get("active_nodes", [])),
    )

    memory = ctx.get("memory", {})
    ag_mailbox = memory.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager")

    if bus is not None and inbox is not None:
        mailbox = inbox.get_or_create("orchestrator_agent")
        msgs = mailbox.process_inbox(max_messages=5)
        if msgs:
            for msg in msgs:
                logger.info("[ORCHESTRATOR] Mensagem recebida de %s: type=%s", msg.sender, msg.type)

    if bus is not None:
        msg = AgentMessage(
            sender="orchestrator_agent",
            receiver="pm",
            type="orchestration_ready",
            payload={
                "next_phase": orch.get("next_phase", "definition"),
                "active_nodes": orch.get("active_nodes", []),
            },
        )
        bus.publish(msg)

    out = {**ctx, "orchestration": orch}
    return out
