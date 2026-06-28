# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_local_knowledge.py

"""
Local Knowledge Node — Consulta memórias locais (LTM, STM, CBOR2) de forma não-bloqueante.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any, List

from iaglobal.evolution.agents.knowledge_agent import knowledge
from iaglobal.memory.term_long import LongTermMemory
from iaglobal.memory.term_short import ShortTermMemory
from iaglobal._paths import CORE_DB

logger = logging.getLogger(__name__)

# Instanciação lazy protegida das memórias locais
_ltm = LongTermMemory(db_path=CORE_DB)
_stm = ShortTermMemory()
_MIN_KNOWLEDGE_CHARS = 200


def _query_local(task: str) -> List[Dict[str, Any]]:
    """Função auxiliar isolada para execução segura e concorrente em thread pool."""
    results = []

    # 1. Consulta ao knowledge.json
    try:
        entries = knowledge.retrieve_relevant(task, max_results=3) or []
        for e in entries:
            if isinstance(e, dict):
                content = e.get("content", "")[:500]
                if len(content) > 30:
                    results.append({"source": "knowledge.json", "content": content, "relevance": 1.0})
    except Exception as err:
        logger.debug("[LOCAL_KNOWLEDGE] Falha ao ler knowledge.json: %s", err)

    # 2. Consulta à Long-Term Memory (LTM)
    try:
        ltm_results = _ltm.retrieve(task, top_k=3) or []
        for m in ltm_results:
            if isinstance(m, dict):
                content = m.get("content", "")[:500]
                if len(content) > 30:
                    results.append({"source": "ltm", "content": content, "relevance": 0.9})
    except Exception as err:
        logger.debug("[LOCAL_KNOWLEDGE] Falha ao ler LTM: %s", err)

    # 3. Consulta ao banco de vetores em CBOR2
    try:
        from iaglobal.memory.memory_vector import MemoryVector
        _mem_vec = MemoryVector()
        vec_results = _mem_vec.search(task, top_k=3) or []
        for m in vec_results:
            content = m if isinstance(m, str) else m.get("content", "")
            if content and len(str(content)) > 30:
                results.append({"source": "cbor2", "content": str(content)[:500], "relevance": 0.8})
    except Exception as err:
        logger.debug("[LOCAL_KNOWLEDGE] Falha ao ler banco CBOR2: %s", err)

    # 4. Consulta à Short-Term Memory (STM)
    try:
        recent = _stm.get_recent(5) or []
        for m in recent:
            content = str(m)[:500]
            if len(content) > 30:
                results.append({"source": "stm", "content": content, "relevance": 0.7})
    except Exception as err:
        logger.debug("[LOCAL_KNOWLEDGE] Falha ao ler STM: %s", err)

    return results


async def run_local_knowledge(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a varredura assíncrona de memórias locais sem travar a thread principal.
    Mapeia latência e acertos de cache locais para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "local_knowledge_deterministic_cache"
    
    task = str(ctx.get("input", {}).get("task", ""))
    
    if not task or len(task) < 5:
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "", 
            "local_found": False, 
            "total_chars": 0,
            "execution_metrics": {"model": resolved_model, "success": True, "latency": latency_ms, "cost": 0.0}
        }

    logger.info("[LOCAL_KNOWLEDGE] Iniciando varredura paralela em camadas de memórias locais...")

    try:
        # Desvia a computação e leituras síncronas de arquivos e DB para uma thread pool isolada
        results = await asyncio.to_thread(_query_local, task)
        total_chars = sum(len(r["content"]) for r in results) if results else 0
        latency_ms = (time.time() - start_time) * 1000.0

        if results:
            lines = [f"• [{r['source']}] {r['content']}" for r in results]
            combined = "\n\n".join(lines)

            logger.info("[LOCAL_KNOWLEDGE] Sucesso! %d entradas recuperadas (%d caracteres lidos).", 
                        len(results), total_chars)

            # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
            return {
                "output": combined,
                "local_knowledge": results,
                "local_found": True,
                "total_chars": total_chars,
                "execution_metrics": {
                    "model": resolved_model,
                    "success": True,
                    "latency": latency_ms,
                    "cost": 0.0  # Infraestrutura puramente local e offline
                }
            }

        logger.info("[LOCAL_KNOWLEDGE] Varredura finalizada. Nenhum conhecimento local correspondente encontrado.")
        
        return {
            "output": "",
            "local_knowledge": [],
            "local_found": False,
            "total_chars": 0,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[LOCAL_KNOWLEDGE] Falha crítica no processamento de memórias locais: %s", e)
        
        return {
            "output": "",
            "local_knowledge": [],
            "local_found": False,
            "total_chars": 0,
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

