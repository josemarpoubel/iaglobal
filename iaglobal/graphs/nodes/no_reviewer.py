# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_reviewer.py

"""
Reviewer Node — Executa a revisão técnica analítica do código gerado no pipeline.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
from typing import Dict, Any

from iaglobal.agents.critic_agent import CriticAgent

logger = logging.getLogger(__name__)


async def run_reviewer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a revisão técnica de código de forma assíncrona e não-bloqueante.
    Mapeia latência, custos de inferência e sucesso analítico para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "reviewer_critic_agent_llm"

    logger.info(
        "[REVIEWER] Iniciando ciclo de revisão técnica e auditoria de código..."
    )

    # Coleta os dados de entrada de forma resiliente
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))
    prompt = ctx.get("prompt", "") or ctx.get("memory", {}).get(
        "prompt_builder", {}
    ).get("built_prompt", "")

    coder_data = ctx.get("coder", {}) or ctx.get("memory", {}).get("coder", {})
    output = (
        coder_data.get("output", "")
        if isinstance(coder_data, dict)
        else str(coder_data or "")
    )

    try:
        # Chamada direta ao CriticAgent com pré-processamento local
        # (LocalSummarizer dentro de avaliar() comprime o output antes do LLM)
        agent = CriticAgent()
        result = await agent.avaliar(task, prompt, output)
        logger.info("[REVIEWER] Ciclo de revisão concluído com sucesso.")

        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict) and "approved" in result

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result.get("feedback", "Revisão concluída com sucesso")
            if isinstance(result, dict)
            else str(result or ""),
            "reviewer": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.004
                ),  # Custo de inferência estimado do revisor
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[REVIEWER] Falha crítica no pipeline do Reviewer Node: %s", e)

        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de revisão técnica",
            "reviewer": {"approved": False, "score": 0, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
