from typing import Dict, Any
import logging

from iaglobal.providers.provider_router import async_route_generate
from iaglobal.memory.memory_error import record_error
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)


async def run_coder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    ag_mailbox = memory.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager")
    if bus is not None and inbox is not None:
        mailbox = inbox.get_or_create("coder")
        msgs = mailbox.process_inbox(max_messages=5)
        if msgs:
            for msg in msgs:
                logger.info("[CODER] Mensagem recebida de %s: type=%s", msg.sender, msg.type)
                if msg.payload.get("plan"):
                    logger.info("[CODER] Plano recebido do planner via bus")

    built_prompt = memory.get("prompt_builder", {}).get("built_prompt", "")
    if not built_prompt:
        built_prompt = memory.get("prompt_builder", {}).get("output", "")

    if not task and not built_prompt:
        record_error("coder", "Empty task", {"task": task})
        return {**ctx, "output": ""}

    specialization = (
        ctx.get("input", {})
        .get("_specialization", {})
        .get("coder", "")
    )

    if specialization:
        system = specialization
        context = built_prompt if built_prompt else task
        prompt = f"{system}\n\n{context}\n\nGere APENAS o conteudo solicitado, sem explicacoes."
    else:
        system = "Voce e um engenheiro de software gerando codigo limpo e funcional."
        context = built_prompt if built_prompt else task
        prompt = f"{system}\n\n{context}\n\nGere APENAS o codigo, sem explicacoes."

    try:
        code = await async_route_generate(
            model="", prompt=prompt, task_type="general"
        )
        if code and len(code) > 50:
            logger.info("[CODER] Conteudo gerado: %d chars", len(code))
            if bus is not None:
                msg = AgentMessage(
                    sender="coder", receiver="critic",
                    type="code_ready",
                    payload={"code": code, "task": task},
                )
                bus.publish(msg)
                logger.info("[CODER] Mensagem enviada para critic via bus")
            return {**ctx, "output": code, "code": code}
        record_error("coder", "Empty/short content generated", {"task": task[:100]})
    except Exception as e:
        logger.warning("[CODER] Falha: %s", e)
        record_error("coder", str(e), {"task": task[:100]})

    return {**ctx, "output": "", "code": ""}
