# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
SearchMiddleware — Injeta contexto web + RAG local em prompts antes de chamadas LLM.

Para agentes não-críticos (Coder, Debugger, Tester, Planner...).
O modelo qwen2.5:0.5b tem atenção limitada — contexto ultra-compacto.

Fontes:
  1. Web via DuckDuckGo (snippets apenas, 2 resultados max)
  2. RAG local via banco vetorial (Top 2 chunks, 300 chars cada)

FASE 1 (RAG Autônomo): ConfidenceTracker — skip busca se confiança > 0.8
"""

import asyncio
import hashlib
import re
import time
from typing import List, Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.search_middleware")


_PORTUGUESE_STOP_WORDS = frozenset({
    "a", "ao", "aos", "as", "com", "como", "criar", "da", "das", "de", "do",
    "dos", "e", "em", "fazer", "na", "nas", "no", "nos", "o", "os", "para",
    "pela", "pelas", "pelo", "pelos", "por", "que", "se", "ser", "seu", "sua",
    "tem", "ter", "um", "uma", "voce", "você", "é",
})


class SearchMiddleware:
    """
    Injeta contexto web + RAG local ultra-compacto em prompts.

    Cache interno (dict) evita buscas repetidas para o mesmo prompt.
    Formato ultra-direto [CONTEXTO][INSTRUÇÃO][PROMPT] para qwen2.5:0.5b.

    FASE 1: ConfidenceTracker — skip busca se confiança > 0.8
FASE 2: QueryExpander — gera queries relacionadas
FASE 3: SourceValidator — valida credibilidade das fontes
FASE 4: SnippetSynthesizer — sintetiza snippets em resumo coerente
FASE 5: SearchMemory — persiste buscas no Obsidian
    """

    SEARCH_REQUIRED_AGENTS = {
        "coder", "debugger", "tester", "planner",
        "multi_coder", "backend_builder", "frontend_builder",
        "api_builder", "database_builder", "pm", "architect",
    }

    _cache: dict[str, tuple[float, str]] = {}
    _CACHE_TTL = 300.0

    # Limites para qwen2.5:0.5b — contexto ultra-compacto
    _WEB_MAX_RESULTS = 2
    _RAG_MAX_RESULTS = 2
    _CHUNK_MAX_CHARS = 300

    # FASE 1: ConfidenceTracker
    _confidence_threshold = 0.8

    # FASE 2: QueryExpander
    _query_expander = None

    # FASE 4: SnippetSynthesizer
    _snippet_synthesizer = None
    _enable_synthesis = False  # Desabilitado por padrão (custo LLM)

    # FASE 5: SearchMemory
    _search_memory = None

    @classmethod
    def enable_synthesis(cls, enabled: bool = True):
        """Habilita/desabilita síntese com LLM."""
        cls._enable_synthesis = enabled
        logger.info("[SEARCH] Síntese %s", "habilitada" if enabled else "desabilitada")

    @classmethod
    async def _search_memory(cls, query: str) -> Optional[List[dict]]:
        """FASE 5: Busca no Obsidian antes de buscar na web."""
        try:
            from iaglobal.search.search_memory import search_memory
            return await search_memory(query)
        except Exception as e:
            logger.debug("[SEARCH] Erro ao buscar no Obsidian: %s", e)
            return None

    @classmethod
    def _format_memory_results(cls, results: List[dict]) -> str:
        """FASE 5: Formata resultados do Obsidian."""
        lines = ["## Obsidian (cache persistente)"]
        for r in results:
            url = r.get("url", "N/A")
            snippet = r.get("snippet", "")
            score = r.get("_source_score")
            score_str = f" (score={score:.2f})" if score else ""
            lines.append(f"- {snippet}{score_str}")
        return "\n".join(lines)

    @classmethod
    async def _update_memory_usage(cls, query: str):
        """FASE 5: Atualiza contador de uso no Obsidian."""
        # Implementação futura quando SearchMemory suportar update
        pass

    @classmethod
    async def _save_to_memory_async(cls, query: str, context: str, node_id: str, task_hash: str):
        """FASE 5: Salva busca no Obsidian (non-blocking)."""
        try:
            await asyncio.sleep(2)  # Aguardar agente completar
            
            # Parse do contexto para extrair snippets
            snippets = cls._parse_context_snippets(context)
            
            if not snippets:
                return
            
            from iaglobal.search.search_memory import save_search
            
            # Salvar com success=True (assumido, FASE 6 implementará feedback real)
            await save_search(
                query=query,
                results=snippets,
                success=True,
                agent_id=node_id,
                task_hash=task_hash,
            )
            
            logger.debug("[SEARCH] %s: salvo no Obsidian", node_id)
            
        except Exception as e:
            logger.debug("[SEARCH] Erro ao salvar no Obsidian: %s", e)

    @classmethod
    async def enrich(cls, prompt: str, node_id: str) -> str:
        """Enriquece o prompt com contexto web + RAG local para agentes não-críticos."""
        if not node_id or "critic" in node_id.lower():
            return prompt

        agent_key = node_id.lower().replace("_agent", "").replace("agent_", "")
        if agent_key not in cls.SEARCH_REQUIRED_AGENTS:
            return prompt

        # FASE 1: Check ConfidenceTracker antes de buscar
        task_hash = hashlib.sha3_512(prompt.encode()).hexdigest()[:16]
        
        from iaglobal.search.confidence_tracker import should_search
        if not should_search(node_id, task_hash, cls._confidence_threshold):
            logger.debug(
                "[SEARCH] %s: skip — confiança alta (threshold=%.2f)",
                node_id, cls._confidence_threshold
            )
            return prompt

        query = cls._extract_query(prompt)
        if not query:
            return prompt

        # FASE 5: Check SearchMemory antes de buscar na web
        cached_results = await cls._search_memory(query)
        if cached_results:
            logger.info(
                "[SEARCH] %s: hit no Obsidian (%d resultados)",
                node_id, len(cached_results)
            )
            context = cls._format_memory_results(cached_results)
            enriched = cls._inject(prompt, context)
            
            # Atualizar uso
            await cls._update_memory_usage(query)
            
            return enriched

        # FASE 2: Query Expansion
        expanded_queries = await cls._expand_query(query)
        all_queries = [query] + expanded_queries[:2]  # Original + 2 expandidas

        # Buscar todas em paralelo
        context = await cls._search_multi_query(all_queries)
        if not context:
            return prompt

        # FASE 4: Síntese (opcional, se habilitado)
        if cls._enable_synthesis and context:
            context = await cls._synthesize_context(context)

        enriched = cls._inject(prompt, context)
        logger.info(
            "[SEARCH_MIDDLEWARE] %s: +%d chars | queries=%d",
            node_id, len(enriched) - len(prompt), len(all_queries),
        )

        # FASE 1: Agendar feedback pós-execução (non-blocking)
        asyncio.ensure_future(cls._record_feedback_async(node_id, task_hash, enriched))
        
        # FASE 5: Salvar no Obsidian (non-blocking)
        asyncio.ensure_future(cls._save_to_memory_async(query, context, node_id, task_hash))

        return enriched

    @classmethod
    async def _search_cached(cls, query: str) -> str:
        """Busca web + RAG local com cache."""
        key = hashlib.md5(query.encode()).hexdigest()
        now = time.time()

        cached = cls._cache.get(key)
        if cached and (now - cached[0]) < cls._CACHE_TTL:
            return cached[1]

        web_task = asyncio.wait_for(
            asyncio.to_thread(cls._search_web_sync, query), timeout=1.2
        )
        rag_task = asyncio.to_thread(cls._search_rag_sync, query)

        results = await asyncio.gather(web_task, rag_task, return_exceptions=True)
        if isinstance(results[0], asyncio.TimeoutError):
            logger.warning("[SEARCH_MIDDLEWARE] Web search timed out (1.2s) — RAG only")
            web_result = ""
        else:
            web_result = results[0] if not isinstance(results[0], Exception) else ""
        rag_result = results[1] if not isinstance(results[1], Exception) else ""

        context = cls._merge(web_result, rag_result)
        cls._cache[key] = (now, context)
        return context

    @classmethod
    def _extract_query(cls, prompt: str) -> Optional[str]:
        """Extrai termos de busca do prompt ignorando código e boilerplate."""
        text = prompt.strip()[:600]

        text = re.sub(
            r'(Você é um especialista|Retorne APENAS|NÃO inclua|'
            r'TIPO DE PROBLEMA|INSTRUÇÃO|TAREFA|SAÍDA ESPERADA|'
            r'================).*?\n', '', text,
        )
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'=+\s*.*?=+\s*', '', text)

        lines = [
            l.strip() for l in text.split('\n')
            if l.strip() and len(l.strip()) > 15
        ]
        if not lines:
            return None

        raw = ' '.join(lines[:2])
        raw = re.sub(r'\s+', ' ', raw).strip()[:120]

        words = [w for w in raw.split() if w.lower() not in _PORTUGUESE_STOP_WORDS]
        query = ' '.join(words) if words else raw
        return query if len(query) > 10 else None

    # ── busca web (ultra-compacta) ──────────────────────────

    @classmethod
    def _sanitize(cls, text: str, max_chars: int = 300) -> str:
        """Remove quebras excessivas, espaços duplicados e caracteres invisíveis."""
        text = text.replace("\r", " ").replace("\t", " ")
        text = re.sub(r'\n{2,}', '\n', text)
        return " ".join(text.split())[:max_chars]

    @classmethod
    def _search_web_with_validation(cls, query: str) -> str:
        """Busca DuckDuckGo com validação de fontes (FASE 3)."""
        try:
            from ddgs import DDGS
            from iaglobal.search.source_validator import SourceValidator
            
            validator = SourceValidator(min_score=0.6)
            
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=cls._WEB_MAX_RESULTS * 2))  # Buscar mais para filtrar depois

            if not results:
                return ""

            # Validar fontes
            validated = validator.filter_by_score(results, min_score=0.6)
            
            # Pegar top 2 após validação
            lines = []
            for r in validated[:cls._WEB_MAX_RESULTS]:
                body = cls._sanitize(r.get("body", ""), cls._CHUNK_MAX_CHARS)
                if body:
                    score = r.get("_source_score", 0.0)
                    lines.append(f"- {body} (score={score:.2f})")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.debug("[SEARCH_MIDDLEWARE] DDGS com validação falhou: %s", e)
            # Fallback para busca sem validação
            return cls._search_web_sync(query)

    @classmethod
    def _search_web_sync(cls, query: str) -> str:
        """Busca DuckDuckGo — apenas snippets, no max 2 resultados."""
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=cls._WEB_MAX_RESULTS))

            if not results:
                return ""

            lines = []
            for r in results:
                body = cls._sanitize(r.get("body", ""), cls._CHUNK_MAX_CHARS)
                if body:
                    lines.append(f"- {body}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug("[SEARCH_MIDDLEWARE] DDGS falhou: %s", e)
            return ""

# ── FASE 1: Feedback loop (non-blocking) ────────────────────

    @classmethod
    async def _synthesize_context(cls, context: str) -> str:
        """
        FASE 4: Sintetiza contexto em resumo coerente.

        Args:
            context: Contexto bruto (formato "## Web\n...\n## Local\n...")

        Returns:
            Contexto sintetizado (resumo + fontes)
        """
        try:
            from iaglobal.search.snippet_synthesizer import get_snippet_synthesizer
            
            # Parse do contexto para extrair snippets
            snippets = cls._parse_context_snippets(context)
            
            if not snippets:
                return context  # Retorna original se não conseguiu parsear
            
            # Sintetizar
            synthesizer = get_snippet_synthesizer()
            synthesis = await synthesizer.synthesize(snippets)
            
            if not synthesis:
                return context  # Retorna original se síntese falhou
            
            # Formatrar contexto sintetizado
            synthesized = cls._format_synthesis(synthesis)
            
            logger.info(
                "[SEARCH] Síntese: %d snippets → %d chars",
                len(snippets), len(synthesis.summary)
            )
            
            return synthesized
            
        except Exception as e:
            logger.debug("[SEARCH] Erro na síntese: %s", e)
            return context  # Fallback para contexto original

    @classmethod
    def _parse_context_snippets(cls, context: str) -> List[dict]:
        """Parse contexto para extrair snippets estruturados."""
        snippets = []
        
        # Parse simples: cada linha começando com "- " é um snippet
        for line in context.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                content = line[2:]
                
                # Extrair score se presente
                score = None
                score_match = re.search(r'\(score=(\d+\.\d+)\)$', content)
                if score_match:
                    score = float(score_match.group(1))
                    content = content[:score_match.start()].strip()
                
                snippets.append({
                    "url": "",  # Não tem URL no contexto parseado
                    "snippet": content,
                    "score": score,
                })
        
        return snippets if snippets else []

    @classmethod
    def _format_synthesis(cls, synthesis) -> str:
        """Formata síntese para injeção no prompt."""
        lines = ["## Síntese", synthesis.summary, ""]
        
        if synthesis.contradictions:
            lines.append("## Contradições Detectadas")
            for c in synthesis.contradictions:
                if c:
                    lines.append(f"- {c}")
            lines.append("")
        
        if synthesis.sources_used:
            lines.append("## Fontes")
            for url in synthesis.sources_used:
                lines.append(f"- {url}")
        
        return "\n".join(lines)

    @classmethod
    async def _record_feedback_async(cls, node_id: str, task_hash: str, enriched_prompt: str):
        """
        Registra feedback pós-execução (non-blocking).

        Este método é chamado após o enriquecimento do prompt,
        mas o feedback real (se ajudou ou não) será registrado
        pelo agente após completar a tarefa.

        Por enquanto, apenas registra que a busca foi disparada.
        FASE 6 implementará o feedback completo via CreditAssignmentEngine.
        """
        try:
            # Aguardar agente completar (simplificação: 2 segundos)
            await asyncio.sleep(2)

            # Por enquanto, apenas log
            logger.debug(
                "[SEARCH] %s: feedback pendente (FASE 6 implementará CreditAssignment)",
                node_id
            )

        except Exception as e:
            logger.debug("[SEARCH] Erro ao agendar feedback: %s", e)

    # ── FASE 2: Query Expansion ────────────────────────────────

    @classmethod
    async def _expand_query(cls, query: str) -> List[str]:
        """Gera queries relacionadas via QueryExpander."""
        try:
            from iaglobal.search.query_expander import get_query_expander
            expander = get_query_expander()
            return await expander.expand(query, max_queries=2)
        except Exception as e:
            logger.debug("[SEARCH] Query expansion falhou: %s", e)
            return []

    @classmethod
    async def _search_multi_query(cls, queries: List[str]) -> str:
        """Busca para múltiplas queries e deduplica resultados."""
        tasks = [cls._search_single_query(q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filtrar erros e vazios
        valid_results = [r for r in results if not isinstance(r, Exception) and r]

        if not valid_results:
            return ""

        # Deduplicar (remover linhas repetidas)
        all_lines = []
        seen = set()
        for result in valid_results:
            for line in result.split("\n"):
                line_hash = hashlib.md5(line.encode()).hexdigest()
                if line_hash not in seen:
                    seen.add(line_hash)
                    all_lines.append(line)

        return "\n".join(all_lines)

    @classmethod
    async def _search_single_query(cls, query: str) -> str:
        """Busca web + RAG para uma única query com validação de fontes (FASE 3)."""
        try:
            # Busca web com validação de fontes (FASE 3)
            web_result = await asyncio.wait_for(
                asyncio.to_thread(cls._search_web_with_validation, query), timeout=1.5
            )
            
            # Busca RAG
            rag_result = await asyncio.to_thread(cls._search_rag_sync, query)

            # Mesclar
            parts = []
            if web_result:
                parts.append(f"## Web\n{web_result}")
            if rag_result:
                parts.append(f"## Local\n{rag_result}")

            return "\n".join(parts)

        except Exception as e:
            logger.debug("[SEARCH] Erro na busca: %s", e)
            return ""

    # ── RAG local (ultra-compacto) ──────────────────────────

    @classmethod
    def _search_rag_sync(cls, query: str) -> str:
        """Busca no banco vetorial local — Top 2 chunks, 300 chars cada."""
        try:
            from iaglobal.memory.memory_vector import search as vector_search
            results = vector_search(query, top_k=cls._RAG_MAX_RESULTS)
        except Exception as e:
            logger.debug("[SEARCH_MIDDLEWARE] Vector search indisponível: %s", e)
            results = []

        if not results:
            return ""

        lines = []
        for score, item in results:
            text = cls._sanitize(item.get("text", ""), cls._CHUNK_MAX_CHARS)
            mtype = item.get("type", "memória")
            if text:
                lines.append(f"- [{mtype}] {text}")
        return "\n".join(lines)

    # ── mesclagem e injeção ultra-direta ────────────────────

    @classmethod
    def _merge(cls, web: str, rag: str) -> str:
        """Combina resultados no formato ultra-direto [CONTEXTO]."""
        parts = []
        if web:
            parts.append("Web:\n" + web)
        if rag:
            parts.append("Memoria Local:\n" + rag)
        return "\n".join(parts)

    @classmethod
    def _inject(cls, prompt: str, context: str) -> str:
        """Formato ultra-direto para qwen2.5:0.5b: [CONTEXTO][INSTRUÇÃO][PROMPT]."""
        if not context:
            return prompt
        return (
            "[CONTEXTO]\n"
            f"{context}\n"
            "[INSTRUÇÃO]\n"
            "Responda ao prompt do usuario usando APENAS as informacoes acima. "
            "Seja direto. Se for codigo, escreva apenas codigo e comentarios curtos.\n"
            "[PROMPT]\n"
            f"{prompt}"
        )
