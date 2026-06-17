from typing import Dict, Any
import logging

from iaglobal.agents.pm_agent import PMAgent
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)

_pm_agent = PMAgent()


async def run_pm(ctx: Dict[str, Any]) -> Dict[str, Any]:
    enhancement = ctx.get("enhancement") or {}
    prompt = ctx.get("prompt") or {}
    raw = prompt.get("normalized", "") if isinstance(prompt, dict) else str(prompt)

    req_inputs = _pm_agent.extract_requirements(raw, enhancement)

    logger.info(
        "[PM] requirements extracted: functional=%d non_functional=%d priority=%s",
        len(req_inputs.get("functional", [])),
        len(req_inputs.get("non_functional", [])),
        req_inputs.get("priority", "medium"),
    )

    memory = ctx.get("memory", {})
    ag_mailbox = memory.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager")

    if bus is not None and inbox is not None:
        mailbox = inbox.get_or_create("pm")
        msgs = mailbox.process_inbox(max_messages=5)
        if msgs:
            for msg in msgs:
                logger.info("[PM] Mensagem recebida de %s: type=%s", msg.sender, msg.type)

    if bus is not None:
        msg = AgentMessage(
            sender="pm",
            receiver="requirements",
            type="requirements_ready",
            payload={
                "functional_count": len(req_inputs.get("functional", [])),
                "non_functional_count": len(req_inputs.get("non_functional", [])),
                "priority": req_inputs.get("priority", "medium"),
            },
        )
        bus.publish(msg)

    out = {**ctx, "requirements_inputs": req_inputs}
    return out
