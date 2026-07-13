# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_coder.py

"""
Coder Node — O programador central do ecossistema iaglobal.
Gera implementações de software com telemetria ativa para o Bandit Policy.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.coder_agent import CoderAgent, CodeArtifact
from iaglobal.memory.memory_error import record_error
from iaglobal.graphs.comms.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)
_coder = CoderAgent()


async def run_coder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o agente programador de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso sintático para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "coder_agent_llm"

    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    # Recupera instâncias de comunicação injetadas no ecossistema
    ag_mailbox = memory.get("agentmailbox", {}) or ctx.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus") or ctx.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager") or ctx.get("_mailbox_manager")

    # Processamento seguro e isolado da caixa de entrada em thread pool
    if bus is not None and inbox is not None:

        def _consume_inbox():
            mailbox = inbox.get_or_create("coder")
            return mailbox.process_inbox(max_messages=5)

        msgs = await asyncio.to_thread(_consume_inbox)
        if msgs:
            for msg in msgs:
                logger.info(
                    "[CODER] Mensagem recebida de %s: type=%s", msg.sender, msg.type
                )
                if msg.payload.get("plan"):
                    logger.info(
                        "[CODER] Plano estratégico recebido do planner via bus."
                    )

    # Consolida a árvore de prompts gerada por nós anteriores
    built_prompt = memory.get("prompt_builder", {}).get(
        "built_prompt", ""
    ) or memory.get("prompt_builder", {}).get("output", "")

    if not task and not built_prompt:
        await asyncio.to_thread(
            record_error, "coder", "Empty task context", {"task": task}
        )
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "",
            "code": "",
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }

    contexto = built_prompt if built_prompt else task
    erros_contexto = memory.get("errors", {}).get("coder", "")

    # Security feedback: violacoes do executor anterior (no pipeline de correcao)
    security_feedback = memory.get("code_executor", {}).get(
        "security_feedback", ""
    ) or memory.get("errors", {}).get("security", "")

    try:
        logger.info("[CODER] Disparando inferência para geração autônoma de código...")

        # Executa a geração profunda de código (LLM-driven)
        artifact = await _coder.generate(
            task=built_prompt or task,
            contexto=contexto,
            erros_contexto=erros_contexto,
            security_feedback=security_feedback,
        )

        code = artifact.code if isinstance(artifact, CodeArtifact) else str(artifact)

        # Correção do Dead Code: Validação feita ANTES do return de sucesso!
        if not code or len(code.strip()) <= 5:
            await asyncio.to_thread(
                record_error,
                "coder",
                "Empty/short content generated",
                {"task": task[:100]},
            )
            latency_ms = (time.time() - start_time) * 1000.0
            return {
                "output": "",
                "code": "",
                "execution_metrics": {
                    "model": resolved_model,
                    "success": False,
                    "latency": latency_ms,
                    "cost": ctx.get("estimated_cost", 0.002),
                },
            }

        logger.info("[CODER] Código gerado com sucesso: %d caracteres", len(code))

        # Publicação reativa e assíncrona no AcetylcholineBus para alertar o Critic
        if bus is not None:
            msg = AgentMessage(
                sender="coder",
                receiver="critic",
                type="code_ready",
                payload={"code": code, "task": task},
            )
            if asyncio.iscoroutinefunction(bus.publish):
                await bus.publish(msg)
            else:
                await asyncio.to_thread(bus.publish, msg)
            logger.info(
                "[CODER] Evento 'code_ready' injetado no barramento para o Critic."
            )

        # Consumo tardio da inbox limpo de travas de thread
        if bus is not None and inbox is not None:
            await asyncio.to_thread(_consume_inbox)

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado (Sem dar dict unpack do ctx, cumprindo as Regras 1 e 5 do AGENTS.md)
        return {
            "output": code,
            "code": code,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.015
                ),  # Custo de inferência estimado para geração de código
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[CODER] Falha crítica no ciclo de geração de software: %s", e)
        await asyncio.to_thread(record_error, "coder", str(e), {"task": task[:100]})

        return {
            "output": "",
            "code": "",
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
