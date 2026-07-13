# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_domain_analysis.py

"""
Domain Analysis Node — Executa a análise profunda de domínio e mapeamento de entidades.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.enhancement_agent import EnhancementAgent

logger = logging.getLogger(__name__)


async def run_domain_analysis(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a análise de domínio de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso cognitivo para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "domain_analysis_agent_llm"

    logger.info("[DOMAIN_ANALYSIS] Iniciando extração e mapeamento de domínio...")

    # Extração resiliente de dados de contexto das etapas anteriores
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))
    intake = ctx.get("intake", {}) or ctx.get("memory", {}).get("prompt_intake", {})

    try:
        # Inicializa o agente de enriquecimento de domínio
        agent = EnhancementAgent()

        # Sendo uma chamada síncrona que consome processamento analítico/LLM,
        # desviamos para a Thread Pool para não congelar o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.enhance):
            result = await agent.enhance(task=task, intake=intake)
        else:
            result = await asyncio.to_thread(agent.enhance, task=task, intake=intake)

        entities_count = (
            len(result.get("entities", [])) if isinstance(result, dict) else 0
        )
        logger.info(
            "[DOMAIN_ANALYSIS] Análise concluída. Mapeadas %d entidades do domínio.",
            entities_count,
        )

        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dict unpack do ctx na RAM)
        return {
            "output": result,
            "domain_analysis": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.004
                ),  # Custo estimado de tokens da inferência
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[DOMAIN_ANALYSIS] Falha crítica no pipeline do Domain Analysis Agent: %s",
            e,
        )

        return {
            "output": {},
            "domain_analysis": {"entities": [], "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
