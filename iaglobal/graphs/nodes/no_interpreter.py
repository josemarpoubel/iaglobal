# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_interpreter.py

"""
Interpreter Node — Interpreta e refina a tarefa cognitiva de forma não-bloqueante.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.enhancement_agent import EnhancementAgent

logger = logging.getLogger(__name__)


async def run_interpreter(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a interpretação analítica e enriquecimento do escopo de forma assíncrona.
    Mapeia latência, custos de inferência e sucesso para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "interpreter_enhancement_agent_llm"

    logger.info(
        "[INTERPRETER] Iniciando interpretação cognitiva e análise do prompt..."
    )

    # Extração resiliente de dados de contexto das etapas anteriores
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))
    intake = ctx.get("intake", {}) or ctx.get("memory", {}).get("prompt_intake", {})

    try:
        # Inicializa o agente especializado em interpretação e enriquecimento
        agent = EnhancementAgent()

        # Sendo uma chamada síncrona que consome processamento analítico/LLM pesado,
        # desviamos para a Thread Pool para não congelar o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.enhance):
            result = await agent.enhance(task=task, intake=intake)
        else:
            result = await asyncio.to_thread(agent.enhance, task=task, intake=intake)

        logger.info(
            "[INTERPRETER] Interpretação e refinamento de intenções concluídos com sucesso."
        )

        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict) and bool(result)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result.get("enhanced_task", "")
            if isinstance(result, dict)
            else str(result),
            "interpreter": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.003
                ),  # Custo de inferência estimado para a interpretação
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[INTERPRETER] Falha crítica no pipeline do Interpreter Node: %s", e
        )

        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "",
            "interpreter": {"error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
