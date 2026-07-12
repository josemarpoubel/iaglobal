# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_search.py

"""
Search Node — Orquestra buscas massivas em paralelo com controle de lotes e cache em disco.
Totalmente em conformidade com as diretrizes e regras estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any, Callable, List, Tuple

from iaglobal.tools.search import async_search_tool
from iaglobal.tools.web_brain import WebBrain
from iaglobal.agents.search_agent import SearchAgent
from iaglobal.graphs.nodes._search_wikipedia import _wikipedia_async
from iaglobal.graphs.nodes._search_sources import (
    google_playwright_search, bing_playwright_search,
    github_search, stackoverflow_search, grokipedia_search,
    startpage_search, mojeek_search, qwant_search,
    duckduckgo_text_search, youcom_search, yacy_search,
)
from iaglobal.graphs.nodes._search_router import run_search_router
from iaglobal.graphs.nodes._disk_swap import save_search, load_search
from iaglobal.graphs.nodes._search_enhanced import (
    ddg_enhanced_search,
    playwright_search,
    bs4_deep_search,
)
from iaglobal.graphs.nodes._search_capabilities import get_search_skip_list
from iaglobal.memory.memory_error import record_error
from iaglobal.agents.agent_base import AgentBase

logger = logging.getLogger(__name__)
SOURCE = "search"

# Inicialização limpa de singletons utilitários
_web_brain = WebBrain()
_search_agent = SearchAgent()
_search_llm_agent = AgentBase(agent_name="search_node")

# DECISÃO (Defect 2 — FECHADO como não-issue): o search_node NÃO precisa de um
# node_id explícito. O SearchAgent herda de AgentBase -> bandit.generate recebe
# node_id="search_agent" (não-crítico); e route_generate() cai em node_id
# "provider_router" (também não-crítico). Em ambos os caminhos a membrana
# confina a Ollama local pelo flag global external_access_only_critic (default
# True). Busca não é tarefa cloud-crítica, logo nenhum node_id adicional é
# necessário — adicionar um seria ruído sem ganho de fitness.


async def _try_source(name: str, fn: Callable, task: str, timeout: int = 12) -> str:
    """Executa fontes síncronas e assíncronas isolando timeouts e travamentos de thread."""
    try:
        # Verifica se o alvo retornado já é uma corrotina ou função assíncrona pura
        if asyncio.iscoroutinefunction(fn):
            r = await asyncio.wait_for(fn(task), timeout=timeout)
        else:
            # Invoca funções síncronas com segurança em pool de threads dedicada
            r = await asyncio.wait_for(asyncio.to_thread(fn, task), timeout=timeout)
            
        result_str = str(r) if r else ""
        if len(result_str) > 30:
            logger.info("[SEARCH] Fonte '%s' OK: %d caracteres extraídos.", name, len(result_str))
            return result_str
    except asyncio.TimeoutError:
        logger.debug("[SEARCH] Timeout atingido para a fonte: %s (limite de %ds)", name, timeout)
    except Exception as e:
        logger.debug("[SEARCH] Falha controlada na fonte %s: %s", name, e)
    return ""


# Wrappers nomeados para evitar lambdas anônimas e permitir inspeção estática correta
async def _async_router_wrapper(task: str): return await run_search_router(task)
async def _async_search_agent_wrapper(task: str): return await _search_agent.process_task(task)
async def _async_web_brain_wrapper(task: str): return await _web_brain.search_text(task, max_results=5)
SOURCES: List[Tuple[str, Callable, int]] = [
    ("ddg_text", duckduckgo_text_search, 15),
    ("google_pw", google_playwright_search, 25),
    ("bing_pw", bing_playwright_search, 20),
    ("router", _async_router_wrapper, 20),
    ("duckduckgo", async_search_tool, 15),
    ("ddg_enhanced", ddg_enhanced_search, 15),
    ("playwright_js", playwright_search, 25),
    ("bs4_deep", bs4_deep_search, 15),
    ("search_agent", _async_search_agent_wrapper, 12),
    ("web_brain", _async_web_brain_wrapper, 12),
    ("startpage", startpage_search, 10),
    ("mojeek", mojeek_search, 10),
    ("qwant", qwant_search, 10),
    ("youcom", youcom_search, 12),
    ("yacy", yacy_search, 15),
    ("github", github_search, 10),
    ("stackoverflow", stackoverflow_search, 10),
    ("grokipedia", grokipedia_search, 10),
    ("wikipedia", _wikipedia_async, 10),
]

_BATCH_SIZE = 4
_BATCH_DELAY = 1.0
_MIN_RESULTS = 2000  # Early-stop após acumular contexto web suficiente (ATP 10:1)


async def run_search(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa buscas paralelas massivas em background de forma assíncrona e resiliente.
    Mapeia latência acumulada e acertos de cache de disco para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "parallel_search_engine_v3"
    
    task = str(ctx.get("input", {}).get("task", ""))
    
    if not task or len(task) < 5:
        await asyncio.to_thread(record_error, SOURCE, "Empty task string", {"task": task})
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "", "search_results": "", "success": False,
            "execution_metrics": {"model": resolved_model, "success": False, "latency": latency_ms, "cost": 0.0}
        }

    # Skip-list de capacidade: fontes pesadas (Playwright/YaCy) ausentes no ambiente
    # são eliminadas ANTES do agendamento, poupando ATP e threads (ver _search_capabilities).
    # Também responde à medição sugerida: quantas vezes as fontes pesadas seriam tentadas.
    skip = await get_search_skip_list()
    active_sources = [(n, fn, t) for (n, fn, t) in SOURCES if n not in skip]
    if skip:
        logger.info("[SEARCH] skip-list ativo: %s — %d/%d fontes ativas (economia de ATP)",
                    sorted(skip), len(active_sources), len(SOURCES))

    # Isolamento 1: Desvia a leitura síncrona do cache em disco para Thread Pool
    cached = await asyncio.to_thread(load_search, SOURCE, task)
    if cached:
        logger.info("[SEARCH] Cache em disco atingido (Hit): %d caracteres restaurados.", len(cached))
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": cached,
            "search_results": cached,
            "success": True,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0  # Cache local sem requisições de rede
            }
        }

    logger.info("[SEARCH] Cache Miss. Iniciando orquestração em lote de %d fontes de busca...", len(active_sources))
    all_results = []

    try:
        for batch_start in range(0, len(active_sources), _BATCH_SIZE):
            batch = active_sources[batch_start:batch_start + _BATCH_SIZE]
            
            # Agenda a execução concorrente do lote atual
            tasks = [_try_source(name, fn, task, timeout) for name, fn, timeout in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for (name, _, _), result in zip(batch, results):
                if result and isinstance(result, str):
                    # Isolamento 2: Desvia a gravação síncrona do arquivo de swap para Thread Pool
                    await asyncio.to_thread(save_search, name, task, result)
                    all_results.append(f"=== {name.upper()} ===\n{result}")
            
            total_chars = sum(len(r) for r in all_results)
            if total_chars >= _MIN_RESULTS:
                logger.info("[SEARCH] Carga ideal atingida (%d caracteres em %d fontes) — Parada antecipada.", 
                            total_chars, len(all_results))
                break
                
            # Staggering delay assíncrono controlado entre lotes
            if batch_start + _BATCH_SIZE < len(active_sources):
                await asyncio.sleep(_BATCH_DELAY)

        combined = "\n\n".join(all_results)
        latency_ms = (time.time() - start_time) * 1000.0

        if combined:
            # Isolamento 3: Persistência do agregado consolidado em background
            await asyncio.to_thread(save_search, SOURCE, task, combined)
            logger.info("[SEARCH] Varredura concluída. Total: %d caracteres de %d/%d fontes ativas.", 
                        len(combined), len(all_results), len(active_sources))
            
            return {
                "output": combined,
                "search_results": combined,
                "success": True,
                "execution_metrics": {
                    "model": resolved_model,
                    "success": True,
                    "latency": latency_ms,
                    "cost": ctx.get("estimated_cost", 0.0)  # Motores abertos locais/web sem custo direto
                }
            }

        # Fallback: todas as fontes de busca falharam (sandbox bloqueia rede)
        logger.warning("[SEARCH] Todas as %d fontes falharam. Gerando contexto via LLM local...", len(active_sources))
        await asyncio.to_thread(record_error, SOURCE, "All sources empty or timed out, using LLM fallback", {"task": task[:100]})
        try:
            # Usa AgentBase para chamar BanditPolicy com semáforo
            fallback_text = await _search_llm_agent._call_llm(
                prompt=f"Forneça informações técnicas detalhadas sobre: {task}\n\n"
                       "Inclua conceitos fundamentais, exemplos de código relevantes, "
                       "boas práticas e possíveis desafios de implementação.",
                task_type="search_fallback",
                system_prompt="Você é um assistente técnico especializado.\n"
                              "Retorne APENAS fatos e informações objetivas, sem saudações.",
                timeout=60.0
            )
            if len(fallback_text) > 50:
                logger.info("[SEARCH] Fallback LLM gerou %d caracteres", len(fallback_text))
                return {
                    "output": fallback_text,
                    "search_results": fallback_text,
                    "success": True,
                    "execution_metrics": {"model": "llm_fallback", "success": True, "latency": latency_ms, "cost": 0.0}
                }
        except Exception as llm_err:
            logger.warning("[SEARCH] Fallback LLM tambem falhou: %s", llm_err)

        return {
            "output": "", "search_results": "", "success": False,
            "execution_metrics": {"model": resolved_model, "success": False, "latency": latency_ms, "cost": 0.0}
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[SEARCH] Falha crítica durante o processamento concorrente do nó de buscas: %s", e)
        await asyncio.to_thread(record_error, SOURCE, str(e), {"task": task[:100]})
        
        return {
            "output": "", "search_results": "", "success": False,
            "execution_metrics": {"model": resolved_model, "success": False, "latency": latency_ms, "cost": 0.0}
        }

