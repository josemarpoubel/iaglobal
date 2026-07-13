# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_enhancement.py

"""
Enhancement Node — Expande, refina e enriquece a tarefa bruta com metadados estruturados.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.enhancement_agent import EnhancementAgent

logger = logging.getLogger(__name__)


async def run_enhancement(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o enriquecimento analítico da tarefa de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso cognitivo para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "enhancement_agent_llm"

    logger.info(
        "[ENHANCEMENT] Iniciando refinação cognitiva e enriquecimento da tarefa..."
    )

    # Garante a existência estruturada do objeto de prompt
    prompt = ctx.get("prompt") or ctx.get("memory", {}).get("prompt_builder", {})
    if not prompt or not isinstance(prompt, dict) or not prompt.get("normalized"):
        task = str(ctx.get("input", {}).get("task", ""))
        prompt = {
            "raw": task,
            "normalized": task,
            "tokens": len(task.split()),
            "intents": ["unknown"],
        }

    raw = prompt["normalized"]
    intake = {
        "raw": raw,
        "normalized": raw,
        "domain": ctx.get("input", {}).get("domain", "unknown"),
    }

    knowledge_context = str(
        ctx.get("knowledge_context", "")
        or ctx.get("memory", {}).get("knowledge", {}).get("summary", "")
    )
    error_context = str(
        ctx.get("error_context", "")
        or ctx.get("memory", {}).get("errors", {}).get("enhancement", "")
    )

    try:
        # Inicializa o agente de enriquecimento
        agent = EnhancementAgent(agent_name="enhancement")

        # Como o enriquecimento de prompts processa inferências densas,
        # desviamos para Thread Pool se o método for síncrono para proteger o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.enhance):
            result = await agent.enhance(
                task=raw,
                intake=intake,
                knowledge_context=knowledge_context,
                error_context=error_context,
            )
        else:
            result = await asyncio.to_thread(
                agent.enhance,
                task=raw,
                intake=intake,
                knowledge_context=knowledge_context,
                error_context=error_context,
            )

        intents = ["analysis", "planning"]
        entities = result.get("entities", []) if isinstance(result, dict) else []

        enhancement_def = {
            "intents_detected": intents,
            "entities": entities,
            "scope": {
                "phases": ["definition"],
                "complexity": result.get("complexity", "medium")
                if isinstance(result, dict)
                else "medium",
            },
            "specialization_instructions": result.get("specialization_instructions")
            if isinstance(result, dict)
            else None,
            "enhanced_task": result.get("enhanced_task", "")
            if isinstance(result, dict)
            else raw,
            "approach": result.get("approach", []) if isinstance(result, dict) else [],
            "prerequisites": result.get("prerequisites", [])
            if isinstance(result, dict)
            else [],
            "suggested_libs": result.get("suggested_libs", [])
            if isinstance(result, dict)
            else [],
        }

        logger.info(
            "[ENHANCEMENT] Refinação finalizada. Escopo e abordagens injetados com sucesso."
        )

        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict) and bool(result.get("enhanced_task"))

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": enhancement_def.get("enhanced_task", ""),
            "enhancement": enhancement_def,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.003
                ),  # Custo estimado de tokens da inferência
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[ENHANCEMENT] Falha crítica no pipeline do Enhancement Node: %s", e
        )

        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": raw,
            "enhancement": {"enhanced_task": raw, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
