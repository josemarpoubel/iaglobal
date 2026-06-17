from typing import Dict, Any
import logging

from iaglobal.agents.intent_classifier_agent import IntentClassifierAgent
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)

_intent_classifier = IntentClassifierAgent()


async def run_prompt_intake(ctx: Dict[str, Any]) -> Dict[str, Any]:
    raw = ctx.get("raw_prompt") or ctx.get("input", {}).get("task", "")
    if not raw or not isinstance(raw, str):
        raw = str(ctx.get("input", {}).get("task", ""))
    if not raw:
        return {**ctx, "prompt": {"raw": "", "normalized": "", "tokens": 0, "intents": []}, "initial_scope": {"phase": "definition"}}

    normalized = raw.strip()
    classification = _intent_classifier.classify(normalized)

    prompt_def = {
        "raw": raw,
        "normalized": normalized,
        "tokens": len(normalized.split()),
        "intents": classification["intents"],
        "entities": classification["entities"],
        "domain": classification["domain"],
        "confidence": classification["confidence"],
    }

    logger.info(
        "[PROMPT_INTAKE] domain=%s intents=%s confidence=%.2f",
        classification["domain"], classification["intents"], classification["confidence"],
    )

    memory = ctx.get("memory", {})
    ag_mailbox = memory.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager")

    if bus is not None and inbox is not None:
        mailbox = inbox.get_or_create("prompt_intake")
        msgs = mailbox.process_inbox(max_messages=5)
        if msgs:
            for msg in msgs:
                logger.info("[PROMPT_INTAKE] Mensagem recebida de %s: type=%s", msg.sender, msg.type)

    if bus is not None:
        msg = AgentMessage(
            sender="prompt_intake",
            receiver="enhancement",
            type="prompt_ready",
            payload={
                "domain": classification["domain"],
                "intents": classification["intents"],
                "entities": classification.get("entities", {}),
            },
        )
        bus.publish(msg)

    out = {**ctx, "prompt": prompt_def, "initial_scope": {"phase": "definition"}}
    return out
