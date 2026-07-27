# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_qa.py

"""
QA Node — Portão de controle de qualidade e garantia de software (QA).
Executa avaliações com telemetria ativa para o Bandit Policy.
"""

import time
import logging
from typing import Dict, Any

from iaglobal.agents.critic_agent import CriticAgent
from iaglobal.core.node_result import NodeResult

logger = logging.getLogger(__name__)


async def run_qa(ctx: Dict[str, Any]) -> NodeResult:
    start_time = time.time()
    resolved_model = "qa_critic_agent_llm"

    logger.info("[QA] Iniciando ciclo de Quality Assurance no código gerado...")

    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))
    prompt = ctx.get("prompt", "") or ctx.get("memory", {}).get(
        "prompt_builder", {}
    ).get("built_prompt", "")

    coder_data = ctx.get("coder", {}) or ctx.get("memory", {}).get("coder", {})
    output = coder_data.get("output", "") if isinstance(coder_data, dict) else ""

    try:
        agent = CriticAgent()
        result = await agent.avaliar(task, prompt, output)

        latency_ms = (time.time() - start_time) * 1000.0

        is_success = isinstance(result, dict) and "approved" in result
        if is_success:
            logger.info("[QA] Avaliação concluída. approved=%s", result.get("approved"))
        else:
            logger.warning(
                "[QA] Critic retornou resposta sem campo 'approved'. keys=%s",
                list(result.keys()) if isinstance(result, dict) else None,
            )

        qa_verdict = result if is_success else {
            "approved": False,
            "structured": False,
            "error": "critic_missing_verdict",
            "critic_result": result,
        }

        return NodeResult(
            success=is_success,
            output=result.get("feedback", "QA finalizado") if isinstance(result, dict) else str(result),
            metadata={
                "qa": qa_verdict,
                "score": (result.get("score", 0) if isinstance(result, dict) else 0),
                "model": resolved_model,
                "latency_ms": latency_ms,
                "cost": ctx.get("estimated_cost", 0.004),
            },
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[QA] Falha crítica durante o ciclo de Quality Assurance: %s", e
        )

        return NodeResult(
            success=False,
            output="Falha no processo de QA",
            errors=[str(e)],
            metadata={
                "qa": {"approved": False, "score": 0, "error": str(e)},
                "model": resolved_model,
                "latency_ms": latency_ms,
                "cost": 0.0,
            },
        )
