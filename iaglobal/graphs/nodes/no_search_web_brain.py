# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_search_web_brain.py

"""
Search Web Brain Node — Executa queries de escopo prático e exemplos com tolerância a falhas.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any, Tuple

from iaglobal.tools.web_brain import WebBrain
from iaglobal.memory.memory_error import record_error
from iaglobal.graphs.nodes._search_queries import generate_queries

logger = logging.getLogger(__name__)
SOURCE = "search_web_brain"

# Inicialização limpa do motor WebBrain
_web_brain = WebBrain()


def _execute_sync_brain_search(candidates: list) -> Tuple[str, bool]:
    """
    Executa o laço sequencial de requisições de rede e retries síncronas 
    de forma enclausurada e isolada em uma thread pool dedicada.
    """
    for q in candidates:
        if not q:
            continue
            
        try:
            # Como a varredura do WebBrain realiza I/O síncrono de rede (HTTP requests/scraping), 
            # as chamadas rodam de forma blindada fora da thread analítica principal
            result = _web_brain.search_text(q, max_results=5)
            
            if result and len(str(result).strip()) > 30:
                result_str = str(result)
                logger.info("[WEB_BRAIN] Sucesso prático: %d chars extraídos (q: %.50s)", len(result_str), q)
                return result_str, True
                
        except Exception as e:
            logger.debug("[WEB_BRAIN] Falha na tentativa da query '%s': %s", q, e)
            
    return "", False


async def run_search_web_brain(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o robô WebBrain de buscas de código de forma assíncrona e não-bloqueante.
    Mapeia latência acumulada e sucesso de scraping para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "web_brain_practical_search_core"
    
    task = str(ctx.get("input", {}).get("task", ""))
    
    if not task or len(task) < 5:
        await asyncio.to_thread(record_error, SOURCE, "Task description empty", {"task": task})
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "", "success": False,
            "execution_metrics": {"model": resolved_model, "success": False, "latency": latency_ms, "cost": 0.0}
        }

    logger.info("[WEB_BRAIN] Gerando sub-queries fragmentadas focadas em exemplos práticos...")

    try:
        # Geração de queries locais por decomposição
        queries = generate_queries(task) or {}
        candidates = [
            queries.get("practical", ""), 
            queries.get("general", ""), 
            queries.get("technical", "")
        ]

        logger.info("[WEB_BRAIN] Despachando threads de scraping de rede em background...")
        
        # DESVIA TODO O LAÇO DE ACESSO À INTERNET, SCRAPING E RETRIES PARA A THREAD POOL ISOLADA
        result_content, is_success = await asyncio.to_thread(_execute_sync_brain_search, candidates)

        latency_ms = (time.time() - start_time) * 1000.0

        if is_success and result_content:
            # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dict unpack do ctx na RAM)
            return {
                "output": result_content,
                "success": True,
                "execution_metrics": {
                    "model": resolved_model,
                    "success": True,
                    "latency": latency_ms,
                    "cost": 0.0  # Motores abertos locais/web sem custo direto de tokens
                }
            }

        # Caso o scraping em todas as frentes de queries retorne dados nulos ou em branco
        await asyncio.to_thread(record_error, SOURCE, "WebBrain returned empty response for all variations", {"task": task[:100]})
        
        return {
            "output": "", "success": False,
            "execution_metrics": {"model": resolved_model, "success": False, "latency": latency_ms, "cost": 0.0}
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[WEB_BRAIN] Falha crítica no pipeline concorrente do WebBrain Node: %s", e)
        await asyncio.to_thread(record_error, SOURCE, str(e), {"task": task[:100]})
        
        return {
            "output": "", "success": False,
            "execution_metrics": {"model": resolved_model, "success": False, "latency": latency_ms, "cost": 0.0}
        }

