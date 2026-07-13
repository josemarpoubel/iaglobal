# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_search_agent.py

"""
Search Agent Node — Executa queries técnicas segmentadas e rotinas de autoaprendizado.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any, Tuple

from iaglobal.agents.search_agent import SearchAgent
from iaglobal.memory.memory_error import record_error
from iaglobal.graphs.nodes._search_queries import generate_queries

logger = logging.getLogger(__name__)
SOURCE = "search_agent"

# Inicialização limpa do agente especialista em buscas e indexação
_search_agent = SearchAgent()


def _sync_execute_and_learn(candidates: list, task_str: str) -> Tuple[str, bool]:
    """
    Executa o laço de tentativas, buscas de rede e aprendizado
    de forma enclausurada em uma thread pool separada.
    """
    for q in candidates:
        if not q:
            continue

        try:
            result = asyncio.run(_search_agent.process_task(q))

            if result and len(str(result).strip()) > 30:
                result_str = str(result)
                try:
                    # Executa a rotina pesada de absorção de conhecimento local de forma isolada
                    _search_agent.pesquisar_e_aprender(q)
                except Exception as learner_err:
                    logger.debug(
                        "[SEARCH_AGENT] Ignorada falha na rotina de aprendizado: %s",
                        learner_err,
                    )

                logger.info(
                    "[SEARCH_AGENT] Sucesso técnico: %d chars extraídos (q: %.50s)",
                    len(result_str),
                    q,
                )
                return result_str, True

        except Exception as e:
            logger.debug("[SEARCH_AGENT] Falha na tentativa da query '%s': %s", q, e)

    return "", False


async def run_search_agent(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o agente de buscas técnicas e aprendizado contínuo de forma assíncrona.
    Mapeia latência acumulada e sucesso de indexação para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "search_agent_technical_llm_core"

    task = str(ctx.get("input", {}).get("task", ""))

    if not task or len(task) < 5:
        await asyncio.to_thread(
            record_error, SOURCE, "Task string empty or too short", {"task": task}
        )
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "",
            "search_results": "",
            "success": False,
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }

    logger.info(
        "[SEARCH_AGENT] Iniciando decomposição analítica e geração de queries técnicas..."
    )

    try:
        # Geração determinística de queries locais
        queries = generate_queries(task) or {}
        candidates = [
            queries.get("technical", ""),
            queries.get("general", ""),
            queries.get("practical", ""),
        ]

        logger.info(
            "[SEARCH_AGENT] Despachando laço sequencial de requisições de rede para a Thread Pool..."
        )

        # DESVIA TODO O TRÁFEGO DE REDE, RETRIES SÍNCRONOS E GRAVAÇÃO DE CONHECIMENTO PARA A THREAD POOL ISOLADA
        result_content, is_success = await asyncio.to_thread(
            _sync_execute_and_learn, candidates, task
        )

        latency_ms = (time.time() - start_time) * 1000.0

        if is_success and result_content:
            # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
            return {
                "output": result_content,
                "search_results": result_content,
                "success": True,
                "execution_metrics": {
                    "model": resolved_model,
                    "success": True,
                    "latency": latency_ms,
                    "cost": ctx.get(
                        "estimated_cost", 0.0
                    ),  # Consumo puramente local/motores abertos
                },
            }

        # Caso todas as queries segmentadas falhem ou retornem strings curtas
        await asyncio.to_thread(
            record_error,
            SOURCE,
            "All technical queries returned empty answers",
            {"task": task[:100]},
        )

        return {
            "output": "",
            "search_results": "",
            "success": False,
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[SEARCH_AGENT] Falha crítica no processamento concorrente do Search Agent: %s",
            e,
        )
        await asyncio.to_thread(record_error, SOURCE, str(e), {"task": task[:100]})

        return {
            "output": "",
            "search_results": "",
            "success": False,
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
