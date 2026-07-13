# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_typing_agent.py

"""
Typing Agent Node — Simula fluxos de processamento de escrita e digitação de forma não-bloqueante.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.typing_agent import TypingAgent

logger = logging.getLogger(__name__)


async def run_typing_agent(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a simulação de escrita de forma assíncrona e isolada em thread pool.
    Mapeia latência acumulada e caracteres processados para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "typing_agent_deterministic_io"

    text = str(ctx.get("input", {}).get("task", ""))
    if not text:
        logger.warning(
            "[TYPING_AGENT] Nenhum texto fornecido para processamento de escrita."
        )
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "",
            "typing_result": "",
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }

    logger.info(
        "[TYPING_AGENT] Iniciando ciclo de simulação de digitação estruturada..."
    )

    try:
        # Inicializa o agente de processamento de escrita
        agent = TypingAgent()

        # Enclausura o laço sequencial síncrono e callbacks de manipulação de strings
        def _execute_sync_typing():
            chars_typed = []
            agent.simulate_typing(text, on_char=lambda c: chars_typed.append(c))
            return "".join(chars_typed)

        # DESVIA TODO O PROCESSAMENTO INTENSIVO E MICRO-DELAYS SÍNCRONOS PARA A THREAD POOL ISOLADA
        result = await asyncio.to_thread(_execute_sync_typing)

        logger.info(
            "[TYPING_AGENT] Sucesso! Processados e digitados %d caracteres.",
            len(result),
        )

        latency_ms = (time.time() - start_time) * 1000.0
        is_success = bool(result and len(result) > 0)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result,
            "typing_result": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": 0.0,  # Infraestrutura puramente local e offline
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[TYPING_AGENT] Falha crítica no pipeline concorrente do Typing Agent Node: %s",
            e,
        )

        return {
            "output": "",
            "typing_result": "",
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
