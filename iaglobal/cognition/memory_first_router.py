# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""MemoryFirstRouter — Consulta memória local antes de chamar LLM externo.

Orquestração em 6 níveis:
   0. Cache exato (db.get_cached_search)
   1. STM + LTM + Vector + knowledge.json (via no_local_knowledge)
   2. Obsidian Subconsciente (sussurrar_intuicao)
   2.5 MetabolicDataAdapter (dados metabólicos reais em JSON — CBOR2/SQLite/JSON → LLM)
   3. LLM local (Ollama pequeno) para síntese
   4. LLM externo (só se critic aprovar)
"""

import asyncio
from typing import Optional, Dict, List
from dataclasses import dataclass

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.cognition.memory_first_router")


@dataclass
class MemoryResult:
    found: bool = False
    content: str = ""
    source: str = ""  # "cache" | "local_knowledge" | "obsidian" | "local_llm"
    confidence: float = 0.0
    latency_ms: float = 0.0


_MIN_KNOWLEDGE_CHARS = 50
CONF_THRESHOLD_MEMORY = 0.85  # Abaixo disso, memória é rejeitada — força LLM
_CONF_DECAY_PER_RESOLUTION = (
    0.10  # Cada resolução exclusivamente via memória reduz conf
)


class MemoryFirstRouter:
    """Router que consulta memória local antes de delegar para LLM externo."""

    def __init__(self):
        self._local_knowledge_node = None
        self._memory_resolution_count: Dict[
            str, int
        ] = {}  # node_id -> consecutive memory-only resos

    def get_effective_confidence(self, node_id: str, base_conf: float) -> float:
        """Retorna confidence efetivo para um nó, considerando degradação.

        Cada resolução exclusivamente via memória (sem LLM) reduz o confidence
        em _CONF_DECAY_PER_RESOLUTION. Quando o valor cai abaixo de
        _CONF_THRESHOLD_MEMORY, a memória é rejeitada e o sistema força LLM.
        """
        count = self._memory_resolution_count.get(node_id, 0)
        decay = count * _CONF_DECAY_PER_RESOLUTION
        return max(0.0, base_conf - decay)

    def record_memory_resolution(self, node_id: str) -> None:
        """Registra que node_id resolveu exclusivamente via memória (sem LLM)."""
        self._memory_resolution_count[node_id] = (
            self._memory_resolution_count.get(node_id, 0) + 1
        )

    def record_llm_resolution(self, node_id: str) -> None:
        """Registra que node_id usou LLM — zera o contador de degradação."""
        self._memory_resolution_count.pop(node_id, None)

    async def route(
        self,
        task: str,
        task_type: str,
        tags: Optional[List[str]] = None,
        min_chars: int = _MIN_KNOWLEDGE_CHARS,
    ) -> MemoryResult:
        """Tenta encontrar resposta na memória local.

        Args:
            task: Prompt/tarefa do agente
            task_type: Tipo de tarefa (ex: "code_generation", "critique")
            tags: Tags para consulta ao subconsciente
            min_chars: Mínimo de caracteres para considerar resposta válida

        Returns:
            MemoryResult com found=True se encontrou resposta local
        """
        start = asyncio.get_event_loop().time()

        # Nível 0: Cache exato (hash da task)
        result = await self._try_cache(task)
        if result.found:
            return result

        # Nível 1: Conhecimento local (STM + LTM + Vector + knowledge.json)
        result = await self._try_local_knowledge(task)
        if result.found and len(result.content) >= min_chars:
            result.latency_ms = (asyncio.get_event_loop().time() - start) * 1000
            return result

        # Nível 2: Subconsciente (Obsidian)
        result = await self._try_obsidian(task, tags or [])
        if result.found and len(result.content) >= min_chars:
            result.latency_ms = (asyncio.get_event_loop().time() - start) * 1000
            return result

        # Nível 2.5: MetabolicDataAdapter — dados reais do sistema em JSON
        result = await self._try_metabolic_context(task, tags or [])
        if result.found and len(result.content) >= min_chars:
            result.latency_ms = (asyncio.get_event_loop().time() - start) * 1000
            return result

        # Não encontrou nada relevante
        elapsed = (asyncio.get_event_loop().time() - start) * 1000
        logger.info(
            "[MEMORY_FIRST] Cache miss | task_type=%s | elapsed=%.0fms",
            task_type,
            elapsed,
        )
        return MemoryResult(latency_ms=elapsed)

    async def _try_cache(self, task: str) -> MemoryResult:
        """Nível 0: Cache exato por hash."""
        try:
            from iaglobal.memory.db_manager import db

            cache_key = str(hash(task))
            cached = await asyncio.to_thread(db.get_cached_search, cache_key)
            if cached and len(cached) >= _MIN_KNOWLEDGE_CHARS:
                logger.info("[MEMORY_FIRST] Cache hit | len=%d", len(cached))
                return MemoryResult(
                    found=True, content=cached, source="cache", confidence=0.95
                )
        except Exception as e:
            logger.debug("[MEMORY_FIRST] Cache error: %s", e)
        return MemoryResult()

    async def _try_local_knowledge(self, task: str) -> MemoryResult:
        """Nível 1: STM + LTM + Vector + knowledge.json."""
        try:
            from iaglobal.graphs.nodes.no_local_knowledge import run_local_knowledge

            ctx = {"input": {"task": task}, "memory": {}}
            result = await run_local_knowledge(ctx)
            output = result.get("output", "")
            local_found = result.get("local_found", False)
            if local_found and output and len(output) >= _MIN_KNOWLEDGE_CHARS:
                logger.info(
                    "[MEMORY_FIRST] Local knowledge hit | len=%d | sources=%d",
                    len(output),
                    len(result.get("local_knowledge", [])),
                )
                return MemoryResult(
                    found=True, content=output, source="local_knowledge", confidence=0.8
                )
        except Exception as e:
            logger.debug("[MEMORY_FIRST] Local knowledge error: %s", e)
        return MemoryResult()

    async def _try_obsidian(self, task: str, tags: List[str]) -> MemoryResult:
        """Nível 2: Subconsciente (vault Obsidian)."""
        try:
            from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

            api = SubconsciousAPI()
            if tags:
                intuicao = await api.sussurrar_intuicao(tags)
            else:
                from iaglobal.obsidian.learning_system import LearningSystem

                ls = LearningSystem()
                intuicao = await ls.processar_requisicao_agente(
                    "memory_first", task, tags or []
                )
            if (
                intuicao
                and "Sem memórias" not in intuicao
                and len(intuicao) >= _MIN_KNOWLEDGE_CHARS
            ):
                logger.info(
                    "[MEMORY_FIRST] Obsidian hit | len=%d | tags=%s",
                    len(intuicao),
                    tags,
                )
                return MemoryResult(
                    found=True, content=intuicao, source="obsidian", confidence=0.75
                )
        except Exception as e:
            logger.debug("[MEMORY_FIRST] Obsidian error: %s", e)
        return MemoryResult()

    async def _try_metabolic_context(self, task: str, tags: List[str]) -> MemoryResult:
        """Nível 2.5: Dados metabólicos reais do sistema em JSON para LLM.

        Lê epigenetic markers, pools metabólicos, memória coletiva da OmniMind,
        knowledge base e registros SQLite — tudo convertido para JSON limpo.
        """
        try:
            from iaglobal.storage.metabolic_adapter import metabolic_adapter

            context_json = await metabolic_adapter.build_context(task)
            if context_json and len(context_json) >= _MIN_KNOWLEDGE_CHARS:
                logger.info(
                    "[MEMORY_FIRST] Metabolic context hit | len=%d | tags=%s",
                    len(context_json),
                    tags,
                )
                return MemoryResult(
                    found=True,
                    content=context_json,
                    source="metabolic_context",
                    confidence=0.85,
                )
        except Exception as e:
            logger.debug("[MEMORY_FIRST] Metabolic context error: %s", e)
        return MemoryResult()

    async def store_result(self, task: str, content: str, source: str = "llm") -> None:
        """Armazena resultado nos níveis de cache para consultas futuras."""
        tasks = []
        try:
            from iaglobal.memory.db_manager import db

            cache_key = str(hash(task))
            tasks.append(asyncio.to_thread(db.cache_search_result, cache_key, content))
        except Exception:
            pass
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
