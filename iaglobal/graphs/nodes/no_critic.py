from typing import Dict, Any
import logging

from iaglobal.agents.critic_agent import CriticAgent
from iaglobal.memory.memory_error import record_error
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)
_critic = CriticAgent()


async def run_critic(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    ag_mailbox = memory.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager")
    if bus is not None and inbox is not None:
        mailbox = inbox.get_or_create("critic")
        msgs = mailbox.process_inbox(max_messages=5)
        if msgs:
            for msg in msgs:
                logger.info("[CRITIC] Mensagem recebida de %s: type=%s", msg.sender, msg.type)

    coder_output = memory.get("multi_coder", {}).get("output", "") or memory.get("coder", {}).get("output", "")
    if not coder_output:
        coder_output = memory.get("result_agent", {}).get("output", "")

    if not coder_output:
        logger.warning("[CRITIC] Nada para avaliar — output vazio")
        return {**ctx, "output": "", "approved": False, "score": 0, "issues": ["Sem output"]}

    prompt_built = memory.get("prompt_builder", {}).get("built_prompt", "") or task

    try:
        result = _critic.avaliar(task=task, prompt=prompt_built, output=coder_output)
        approved = result.get("approved", False)
        score = result.get("score", 0)
        issues = result.get("issues", [])

        logger.info("[CRITIC] score=%.1f approved=%s issues=%d", score, approved, len(issues))
        if issues:
            for iss in issues[:3]:
                logger.info("[CRITIC] issue: %s", iss)

        if score < 30:
            record_error("critic", f"Baixa qualidade: score={score}", {"task": task[:100]})

        if bus is not None:
            msg = AgentMessage(
                sender="critic", receiver="result_agent",
                type="review_done",
                payload={
                    "approved": approved,
                    "score": score,
                    "issues": issues,
                    "fix_suggestions": result.get("fix_suggestions", []),
                    "output": coder_output,
                },
            )
            bus.publish(msg)
            logger.info("[CRITIC] Mensagem enviada para result_agent via bus")

        return {
            **ctx,
            "output": coder_output,
            "critic": {
                "approved": approved,
                "score": score,
                "issues": issues,
                "fix_suggestions": result.get("fix_suggestions", []),
            },
        }
    except Exception as e:
        logger.warning("[CRITIC] Falha: %s", e)
        record_error("critic", str(e), {"task": task[:100]})
        return {**ctx, "output": coder_output, "critic": {"approved": False, "score": 0, "issues": [str(e)]}}
