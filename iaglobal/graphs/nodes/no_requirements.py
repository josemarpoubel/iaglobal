from typing import Dict, Any
import logging

from iaglobal.agents.requirements_agent import RequirementsAgent
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)

_requirements_agent = RequirementsAgent()


async def run_requirements(ctx: Dict[str, Any]) -> Dict[str, Any]:
    req_inputs = ctx.get("requirements_inputs") or {}
    requirements = _requirements_agent.refine(req_inputs)

    logger.info(
        "[REQUIREMENTS] classification=%s priorities=%s total=%d",
        requirements.get("classification", "medium"),
        requirements.get("priorities", ["medium"]),
        len(requirements.get("functional", [])) + len(requirements.get("non_functional", [])),
    )

    memory = ctx.get("memory", {})
    ag_mailbox = memory.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager")

    if bus is not None and inbox is not None:
        mailbox = inbox.get_or_create("requirements")
        msgs = mailbox.process_inbox(max_messages=5)
        if msgs:
            for msg in msgs:
                logger.info("[REQUIREMENTS] Mensagem recebida de %s: type=%s", msg.sender, msg.type)

    if bus is not None:
        msg = AgentMessage(
            sender="requirements",
            receiver="architect",
            type="requirements_refined",
            payload={
                "classification": requirements.get("classification", "medium"),
                "priorities": requirements.get("priorities", ["medium"]),
                "total": len(requirements.get("functional", [])) + len(requirements.get("non_functional", [])),
            },
        )
        bus.publish(msg)

    out = {**ctx, "requirements": requirements}
    return out
