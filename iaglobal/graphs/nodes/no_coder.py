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
from iaglobal.core.artifact import GeneratedArtifact, ArtifactKind

logger = logging.getLogger(__name__)
_coder = CoderAgent()

_CODER_CONTRACT = None


def _get_coder_contract():
    global _CODER_CONTRACT
    if _CODER_CONTRACT is None:
        from iaglobal.graphs.contracts.node_contract import NodeContract

        _CODER_CONTRACT = NodeContract(
            required_inputs=["prompt_builder"],
            optional_inputs=["agentmailbox"],
        )
    return _CODER_CONTRACT


async def run_coder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o agente programador de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso sintático para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "coder_agent_llm"

    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    _get_coder_contract().validate("coder", memory)

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
            "artifact": GeneratedArtifact(
                kind=ArtifactKind.ERROR,
                content="",
                source="coder",
                metadata={"reason": "empty_task_context"},
            ),
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
        # ── CapabilityPlan prescritivo: executa steps antes do LLM ──
        capability_plan = ctx.get("capability_plan")
        plan_code = ""
        if capability_plan and not capability_plan.is_empty():
            from iaglobal.pipeline.plan_executor import PlanExecutor

            executor = PlanExecutor()
            plan_ctx = {"task": built_prompt or task}
            artifact_desc = await executor.execute(capability_plan, plan_ctx)
            plan_code = artifact_desc.code
            logger.info(
                "[CODER] PlanExecutor: %d/%d steps resolvidos, %d chars",
                len(artifact_desc.steps_executed),
                len(capability_plan.steps),
                len(plan_code),
            )

        # Se o plano produziu código suficiente, usa-o como base
        if plan_code and len(plan_code.strip()) > 50:
            codigo_base = plan_code
            logger.info(
                "[CODER] Usando código do plano como base (%d chars)", len(plan_code)
            )
        else:
            codigo_base = ""

        logger.info("[CODER] Disparando inferência para geração autônoma de código...")

        # Executa a geração profunda de código (LLM-driven)
        artifact = await _coder.generate(
            task=built_prompt or task,
            contexto=contexto,
            erros_contexto=erros_contexto,
            security_feedback=security_feedback,
            codigo_base=codigo_base,
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
                "artifact": GeneratedArtifact(
                    kind=ArtifactKind.ERROR,
                    content="",
                    source="coder",
                    metadata={"reason": "empty_or_short_content"},
                ),
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

        # Classifica o artefato UMA VEZ, na origem (contrato GeneratedArtifact)
        gen_artifact = GeneratedArtifact.from_str(code, source="coder")

        if gen_artifact.kind != ArtifactKind.CODE:
            logger.warning(
                "[CODER] Coder produziu %s (nao CODE), %d chars — propagando tipo",
                gen_artifact.kind,
                len(code),
            )

        # Retorno higienizado (Sem dar dict unpack do ctx, cumprindo as Regras 1 e 5 do AGENTS.md)
        return {
            "output": code,
            "code": code,
            "artifact": gen_artifact,
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
            "artifact": GeneratedArtifact(
                kind=ArtifactKind.ERROR,
                content="",
                source="coder",
                metadata={"reason": "exception", "error": str(e)[:200]},
            ),
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
