# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
SearchMiddleware — Injeta contexto web + RAG local em prompts antes de chamadas LLM.

Para agentes não-críticos (Coder, Debugger, Tester, Planner...).
Formato ultra-direto [CONTEXTO][INSTRUÇÃO][PROMPT] para janela pequena de contexto.

Fontes:
1. Web via DuckDuckGo (snippets apenas, 2 resultados max)
2. RAG local via banco vetorial (Top 2 chunks, 300 chars cada)
3. Obsidian (cache persistente) — verificado antes da web

Fluxo do enrich():
  1. Identifica agente real (via delegate_for se caller é critic)
  2. Classifica se busca web é necessária
  3. Verifica ConfidenceTracker (FASE 1) — skip se confiança alta
  4. Consulta cache Obsidian (FASE 5) — retorna se houver hit
  5. Expande query (FASE 2) e busca paralela web + RAG
  6. Síntese opcional via LLM (FASE 4)
  7. Injeta contexto no prompt
  8. Agenda persistência Obsidian + feedback (fire-and-forget)
"""

import asyncio
import hashlib
import re
import time
from typing import List, Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.search_middleware")

# ═══════════════════════════════════════════════════════════════════════
# Constantes de módulo — pré-compiladas uma vez, reutilizadas N vezes
# ═══════════════════════════════════════════════════════════════════════

_PORTUGUESE_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "ao",
        "aos",
        "as",
        "com",
        "como",
        "criar",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "fazer",
        "na",
        "nas",
        "no",
        "nos",
        "o",
        "os",
        "para",
        "pela",
        "pelas",
        "pelo",
        "pelos",
        "por",
        "que",
        "se",
        "ser",
        "seu",
        "sua",
        "tem",
        "ter",
        "um",
        "uma",
        "voce",
        "você",
        "é",
    }
)

_WEB_INDICATORS: frozenset[str] = frozenset(
    {
        "react",
        "vue",
        "angular",
        "svelte",
        "next.js",
        "nuxt",
        "flask",
        "fastapi",
        "django",
        "express",
        "spring boot",
        "tailwind",
        "bootstrap",
        "material-ui",
        "chakra",
        "antd",
        "tensorflow",
        "pytorch",
        "scikit-learn",
        "pandas",
        "numpy",
        "tema escuro",
        "dark mode",
        "dark theme",
        "modo claro",
        "responsivo",
        "mobile-first",
        "desktop",
        "layout",
        "dashboard",
        "gráfico",
        "chart",
        "visualização",
        "animação",
        "transição",
        "hover",
        "efeito",
        "api",
        "rest",
        "graphql",
        "websocket",
        "grpc",
        "stripe",
        "paypal",
        "oauth",
        "jwt",
        "auth0",
        "aws",
        "azure",
        "gcp",
        "heroku",
        "vercel",
        "netlify",
        "firebase",
        "supabase",
        "mongodb atlas",
        "imposto",
        "lei",
        "regulamento",
        "gdpr",
        "lgpd",
        "preço",
        "custo",
        "cotação",
        "taxa de câmbio",
        "2024",
        "2025",
        "2026",
        "atual",
        "mais recente",
        "docker",
        "kubernetes",
        "ci/cd",
        "github actions",
        "redis",
        "postgresql",
        "mysql",
        "mongodb",
        "elasticsearch",
        "rabbitmq",
        "kafka",
        "celery",
    }
)

_INTERNAL_INDICATORS: frozenset[str] = frozenset(
    {
        "analise",
        "análise",
        "diagnóstico",
        "debug",
        "depure",
        "otimize",
        "otimizar",
        "performance",
        "gargalo",
        "bottleneck",
        "refatore",
        "refatorar",
        "melhore",
        "melhorar",
        "clean code",
        "teste",
        "testes",
        "pytest",
        "unittest",
        "cobertura",
        "documente",
        "documentação",
        "readme",
        "comentário",
        "iaglobal",
        "pipeline",
        "agente",
        "skill",
        "bandit",
        "fluxo de trabalho",
        "workflow",
        "arquitetura",
        "estrutura",
    }
)

_PROMPT_SCRUB_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"(Você é um especialista|Retorne APENAS|NÃO inclua|"
        r"TIPO DE PROBLEMA|INSTRUÇÃO|TAREFA|SAÍDA ESPERADA|"
        r"================).*?\n",
        re.DOTALL,
    ),
    re.compile(r"```.*?```", re.DOTALL),
    re.compile(r"=+\s*.*?=+\s*"),
]

_QUERY_MIN_LENGTH: int = 10
_LONG_LINE_THRESHOLD: int = 15
_TASK_HASH_TRUNCATE: int = 16
_CACHE_TTL: float = 300.0
_WEB_MAX_RESULTS: int = 2
_RAG_MAX_RESULTS: int = 2
_CHUNK_MAX_CHARS: int = 300
_CONFIDENCE_THRESHOLD: float = 0.8


# ═══════════════════════════════════════════════════════════════════════
# SearchMiddleware
# ═══════════════════════════════════════════════════════════════════════


class SearchMiddleware:
    """
    Injeta contexto web + RAG local ultra-compacto em prompts.

    Cache interno (dict) evita buscas repetidas para o mesmo prompt.
    Formato ultra-direto [CONTEXTO][INSTRUÇÃO][PROMPT] para janela de contexto pequena.

    FASE 1: ConfidenceTracker — skip busca se confiança > threshold
    FASE 2: QueryExpander — gera queries relacionadas (opcional)
    FASE 3: SourceValidator — filtra fontes de baixa credibilidade
    FASE 4: SnippetSynthesizer — sintese snippets em resumo coerente (opcional)
    FASE 5: SearchMemory — persiste buscas no Obsidian (fire-and-forget)
    """

    SEARCH_REQUIRED_AGENTS: frozenset[str] = frozenset(
        {
            "coder",
            "debugger",
            "tester",
            "planner",
            "multi_coder",
            "backend_builder",
            "frontend_builder",
            "api_builder",
            "database_builder",
            "pm",
            "architect",
        }
    )

    # Cache em memória (chave: sha256(query), valor: (timestamp, context_str))
    _cache: dict[str, tuple[float, str]] = {}

    # Síntese habilitada apenas via chamada explícita (custo LLM)
    _enable_synthesis: bool = False

    def __init__(self) -> None:
        raise RuntimeError("SearchMiddleware é classe estática — não instancie.")

    # ══════════════════════════════════════════════════════════════════
    # Controle de classe
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    def enable_synthesis(cls, enabled: bool = True) -> None:
        """Habilita ou desabilita síntese de contexto via LLM (FASE 4)."""
        cls._enable_synthesis = enabled
        logger.info("[SEARCH] Síntese %s", "habilitada" if enabled else "desabilitada")

    # ══════════════════════════════════════════════════════════════════
    # FASE 5 — Obsidian SearchMemory
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    async def _search_memory(cls, query: str) -> Optional[List[dict]]:
        """Consulta Obsidian para resultados em cache persistente antes da web."""
        try:
            from iaglobal.search.search_memory import search_memory

            return await search_memory(query)
        except ImportError:
            logger.debug("[SEARCH] search_memory indisponível")
            return None
        except Exception as exc:
            logger.debug("[SEARCH] Obsidian indisponível: %s", exc)
            return None

    @classmethod
    def _format_memory_results(cls, results: List[dict]) -> str:
        """Formata resultados do Obsidian para injeção no prompt."""
        lines: list[str] = ["## Obsidian (cache persistente)"]
        for r in results:
            snippet = r.get("snippet", "")
            score = r.get("_source_score")
            score_str = f" (score={score:.2f})" if score is not None else ""
            if snippet:
                lines.append(f"- {snippet}{score_str}")
        return "\n".join(lines)

    @classmethod
    async def _save_to_memory_async(
        cls,
        query: str,
        context: str,
        node_id: str,
        task_hash: str,
    ) -> None:
        """Persiste busca no Obsidian sem bloquear o fluxo principal."""
        try:
            snippets = cls._parse_context_snippets(context)
            if not snippets:
                return
            from iaglobal.search.search_memory import save_search

            await save_search(
                query=query,
                results=snippets,
                success=True,
                agent_id=node_id,
                task_hash=task_hash,
            )
            logger.debug("[SEARCH] %s: busca salva no Obsidian", node_id)
        except ImportError:
            logger.debug("[SEARCH] search_memory.save_search indisponível")
        except Exception as exc:
            logger.debug("[SEARCH] Falha ao salvar no Obsidian: %s", exc)

    @classmethod
    async def _record_feedback_async(
        cls,
        node_id: str,
        task_hash: str,
        enriched_prompt: str,
    ) -> None:
        """
        Registra que uma busca foi disparada.

        Nota: o feedback real (útil / não-útil) será registrado pelo
        CreditAssignmentEngine após execução do agente (FASE 6).
        """
        try:
            await asyncio.sleep(2)
            logger.debug(
                "[SEARCH] %s: feedback pendente (FASE 6 registrará CreditAssignment)",
                node_id,
            )
        except Exception as exc:
            logger.debug("[SEARCH] Falha ao agendar feedback: %s", exc)

    # ══════════════════════════════════════════════════════════════════
    # Classificação de busca
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    def _needs_web_search(cls, prompt: str, node_id: str) -> bool:
        """
        Decide se o prompt requer busca web externa.

        Compara contagem de indicadores web vs indicadores de tarefa interna
        usando frozensets pré-compilados (compilados uma vez no módulo).

        Retorna True se há evidência de que informação externa é necessária.
        """
        prompt_lower = prompt.lower()

        web_score = sum(1 for ind in _WEB_INDICATORS if ind in prompt_lower)
        internal_score = sum(1 for ind in _INTERNAL_INDICATORS if ind in prompt_lower)

        if internal_score > web_score:
            logger.debug(
                "[SEARCH] Task INTERNA: web=%d internal=%d | agent=%s",
                web_score,
                internal_score,
                node_id,
            )
            return False

        if web_score >= 1:
            matched = [ind for ind in _WEB_INDICATORS if ind in prompt_lower][:5]
            logger.debug(
                "[SEARCH] Task WEB: web=%d internal=%d | matches=%s | agent=%s",
                web_score,
                internal_score,
                matched,
                node_id,
            )
            return True

        logger.debug(
            "[SEARCH] Task genérica: web=%d internal=%d | agent=%s",
            web_score,
            internal_score,
            node_id,
        )
        return False

    # ══════════════════════════════════════════════════════════════════
    # Extração de query
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    def _extract_query(cls, prompt: str) -> Optional[str]:
        """
        Extrai termos de busca relevantes removendo boilerplate e código.

        Usa regex pré-compilados do módulo para evitar reconstrução a cada chamada.
        """
        text = prompt.strip()[:600]

        for pattern in _PROMPT_SCRUB_PATTERNS:
            text = pattern.sub("", text)

        lines = [
            l.strip()
            for l in text.split("\n")
            if l.strip() and len(l.strip()) > _LONG_LINE_THRESHOLD
        ]
        if not lines:
            return None

        raw = " ".join(lines[:2])
        raw = re.sub(r"\s+", " ", raw).strip()[:120]

        words = [w for w in raw.split() if w.lower() not in _PORTUGUESE_STOP_WORDS]
        query = " ".join(words) or raw

        return query if len(query) > _QUERY_MIN_LENGTH else None

    # ══════════════════════════════════════════════════════════════════
    # FASE 2 — Query Expansion
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    async def _expand_query(cls, query: str) -> List[str]:
        """Gera queries relacionadas via QueryExpander (máximo 2 variações)."""
        try:
            from iaglobal.search.query_expander import get_query_expander

            expander = get_query_expander()
            return await expander.expand(query, max_queries=2)
        except ImportError:
            logger.debug("[SEARCH] query_expander indisponível")
            return []
        except Exception as exc:
            logger.debug("[SEARCH] QueryExpander falhou: %s", exc)
            return []

    # ══════════════════════════════════════════════════════════════════
    # FASE 3 — Busca web com validação de fontes
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    def _search_web_with_validation(cls, query: str) -> str:
        """Busca DuckDuckGo e filtra resultados por credibilidade (FASE 3)."""
        try:
            from ddgs import DDGS
            from iaglobal.search.source_validator import SourceValidator

            validator = SourceValidator(min_score=0.6)
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=cls._WEB_MAX_RESULTS * 2))
                validated = validator.filter_by_score(results, min_score=0.6)

            lines: list[str] = []
            for r in validated[: cls._WEB_MAX_RESULTS]:
                body = cls._sanitize(r.get("body", ""), cls._CHUNK_MAX_CHARS)
                if body:
                    score = r.get("_source_score", 0.0)
                    lines.append(f"- {body} (score={score:.2f})")
            return "\n".join(lines)

        except ImportError:
            logger.debug("[SEARCH] ddgs indisponível — usando fallback síncrono")
            return ""
        except Exception as exc:
            logger.debug("[SEARCH] Busca validada falhou: %s", exc)
            return ""

    @classmethod
    def _search_web_sync(cls, query: str) -> str:
        """Busca DuckDuckGo sem validação de fontes (fallback, mais rápido)."""
        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=cls._WEB_MAX_RESULTS))

            lines: list[str] = []
            for r in results:
                body = cls._sanitize(r.get("body", ""), cls._CHUNK_MAX_CHARS)
                if body:
                    lines.append(f"- {body}")
            return "\n".join(lines)

        except ImportError:
            logger.debug("[SEARCH] ddgs não instalado")
            return ""
        except Exception as exc:
            logger.debug("[SEARCH] Busca web falhou: %s", exc)
            return ""

    # ══════════════════════════════════════════════════════════════════
    # RAG local
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    def _search_rag_sync(cls, query: str) -> str:
        """Consulta banco vetorial local — top 2 chunks, 300 chars cada."""
        try:
            from iaglobal.memory.memory_vector import search as vector_search

            results = vector_search(query, top_k=cls._RAG_MAX_RESULTS)
        except ImportError:
            logger.debug("[SEARCH] memory_vector indisponível")
            return ""
        except Exception as exc:
            logger.debug("[SEARCH] RAG falhou: %s", exc)
            return []

        if not results:
            return ""

        lines: list[str] = []
        for score, item in results:
            text = cls._sanitize(item.get("text", ""), cls._CHUNK_MAX_CHARS)
            mtype = item.get("type", "memória")
            if text:
                lines.append(f"- [{mtype}] {text}")
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════
    # Cache e mesclagem
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    def _get_cache_key(cls, query: str) -> str:
        """Gera chave de cache estável (SHA-256)."""
        return hashlib.sha256(query.encode()).hexdigest()

    @classmethod
    async def _search_cached(cls, query: str) -> str:
        """
        Busca web + RAG com cache em memória (TTL configurável).

        .. deprecated::
            Método mantido como utilidade separada. O fluxo principal
            de busca usa agora _search_multi_query com cache distribuído
            via Obsidian (FASE 5). Mantido para compatibilidade retroativa.
        """
        key = cls._get_cache_key(query)
        now = time.time()
        cached = cls._cache.get(key)
        if cached and (now - cached[0]) < cls._CACHE_TTL:
            return cached[1]

        web_task = asyncio.wait_for(
            asyncio.to_thread(cls._search_web_with_validation, query),
            timeout=1.5,
        )
        rag_task = asyncio.to_thread(cls._search_rag_sync, query)
        results = await asyncio.gather(web_task, rag_task, return_exceptions=True)

        web_result = (
            ""
            if isinstance(results[0], (Exception, asyncio.TimeoutError))
            else results[0]
        )
        rag_result = "" if isinstance(results[1], Exception) else results[1]

        context = cls._merge(web_result, rag_result)
        cls._cache[key] = (now, context)
        return context

    @classmethod
    def _merge(cls, web: str, rag: str) -> str:
        """Combina resultados web e RAG no formato padrão."""
        parts: list[str] = []
        if web:
            parts.append(f"## Web\n{web}")
        if rag:
            parts.append(f"## Memoria Local\n{rag}")
        return "\n\n".join(parts)

    # ══════════════════════════════════════════════════════════════════
    # FASE 4 — Síntese de snippet (opcional)
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    async def _synthesize_context(cls, context: str) -> str:
        """Agrega snippets em resumo coerente via snippet_synthesizer."""
        try:
            from iaglobal.search.snippet_synthesizer import get_snippet_synthesizer

            snippets = cls._parse_context_snippets(context)
            if not snippets:
                return context
            synthesizer = get_snippet_synthesizer()
            synthesis = await synthesizer.synthesize(snippets)
            if not synthesis:
                return context
            logger.info(
                "[SEARCH] Síntese: %d snippets → %d chars",
                len(snippets),
                len(synthesis.summary),
            )
            return cls._format_synthesis(synthesis)
        except ImportError:
            logger.debug("[SEARCH] snippet_synthesizer indisponível")
            return context
        except Exception as exc:
            logger.debug("[SEARCH] Síntese indisponível: %s", exc)
            return context

    @classmethod
    def _parse_context_snippets(cls, context: str) -> List[dict]:
        """Extrai snippets estruturados do formato markdown."""
        snippets: list[dict] = []
        for line in context.split("\n"):
            stripped = line.strip()
            if not stripped.startswith("- "):
                continue
            content = stripped[2:]
            score_match = re.search(r"\(score=(\d+\.\d+)\)$", content)
            if score_match:
                score = float(score_match.group(1))
                content = content[: score_match.start()].strip()
            else:
                score = None
            snippets.append(
                {
                    "url": "",
                    "snippet": content,
                    "score": score,
                }
            )
        return snippets

    @classmethod
    def _format_synthesis(cls, synthesis: object) -> str:
        """Formata objeto de síntese para injeção no prompt."""
        lines: list[str] = ["## Síntese", synthesis.summary, ""]
        contradictions = getattr(synthesis, "contradictions", [])
        if contradictions:
            lines.append("## Contradições Detectadas")
            for c in contradictions:
                if c:
                    lines.append(f"- {c}")
            lines.append("")
        sources = getattr(synthesis, "sources_used", [])
        if sources:
            lines.append("## Fontes")
            for url in sources:
                lines.append(f"- {url}")
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════
    # FASE 2 — Multi-query paralela com deduplicação
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    async def _search_multi_query(cls, queries: List[str]) -> str:
        """Executa múltiplas queries em paralelo e deduplica resultados."""
        tasks = [cls._search_single_query(q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid_results = [r for r in results if not isinstance(r, Exception) and r]
        if not valid_results:
            return ""

        all_lines: list[str] = []
        seen: set[str] = set()
        for result in valid_results:
            for line in result.split("\n"):
                line_hash = hashlib.sha256(line.encode()).hexdigest()
                if line_hash not in seen:
                    seen.add(line_hash)
                    all_lines.append(line)
        return "\n".join(all_lines)

    @classmethod
    async def _search_single_query(cls, query: str) -> str:
        """Busca web (validada) + RAG para uma única query."""
        web_result = ""
        try:
            web_result = await asyncio.wait_for(
                asyncio.to_thread(cls._search_web_with_validation, query),
                timeout=1.5,
            )
        except asyncio.TimeoutError:
            logger.debug("[SEARCH] Timeout web (%s)", query)
        except ImportError:
            logger.debug("[SEARCH] ddgs não instalado")
        except Exception as exc:
            logger.debug("[SEARCH] Erro busca web (%s): %s", query, exc)

        rag_result = ""
        try:
            rag_result = await asyncio.to_thread(cls._search_rag_sync, query)
        except Exception as exc:
            logger.debug("[SEARCH] Erro RAG (%s): %s", query, exc)

        parts: list[str] = []
        if web_result:
            parts.append(f"## Web\n{web_result}")
        if rag_result:
            parts.append(f"## Memoria Local\n{rag_result}")
        return "\n".join(parts)

    # ══════════════════════════════════════════════════════════════════
    # Sanitização
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    def _sanitize(cls, text: str, max_chars: int = _CHUNK_MAX_CHARS) -> str:
        """Remove artefatos de formatação, caracteres Unicode perigosos e limita tamanho."""
        text = text.replace("\r", " ").replace("\t", " ")
        text = re.sub(r"\n{2,}", "\n", text)
        # Remove caracteres invisíveis/não-ASCII perigosos para código Python
        text = re.sub(r"[\u00b7\u2010-\u2015\u00a0\u1680\u2000-\u200f\u2028\u2029\u202f\u205f\u3000]", " ", text)
        return " ".join(text.split())[:max_chars]

    # ══════════════════════════════════════════════════════════════════
    # Injeção no prompt
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    def _inject(cls, prompt: str, context: str) -> str:
        """Formato ultra-compacto para janela de contexto pequena."""
        if not context:
            return prompt
        return (
            "[CONTEXTO]\n"
            f"{context}\n"
            "[INSTRUÇÃO]\n"
            "Responda ao prompt do usuário usando APENAS as informações acima. "
            "Seja direto. Se for código, escreva apenas código e comentários curtos.\n"
            "[PROMPT]\n"
            f"{prompt}"
        )

    # ══════════════════════════════════════════════════════════════════
    # Entry point principal
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    async def enrich(
        cls,
        prompt: str,
        node_id: str,
        context: dict | None = None,
    ) -> str:
        """
        Enriquece prompt com contexto web + RAG para agentes não-críticos.

        Fluxo:
          1. Identifica agente real (via delegate_for se caller é critic)
          2. Verifica se agente requer busca web
          3. Verifica ConfidenceTracker — skip se confiança alta
          4. Consulta cache Obsidian — retorna se houver hit
          5. Expande query e busca paralela web + RAG
          6. Síntese opcional via LLM (se habilitado)
          7. Injeta contexto no prompt
          8. Agenda persistência Obsidian + feedback (fire-and-forget)
        """
        if not node_id:
            return prompt

        # ── 1. Identifica agente real ──────────────────────────────
        actual_agent = node_id.lower()
        if "critic" in actual_agent:
            delegate = (context or {}).get("delegate_for", "")
            actual_agent = delegate.lower() if delegate else actual_agent

        if actual_agent == "critic":
            logger.debug("[SEARCH] Critic — pulando busca web")
            return prompt

        # ── 2. Classificação de busca ──────────────────────────────
        if not cls._needs_web_search(prompt, actual_agent):
            logger.debug("[SEARCH] Task não requer web — usando conhecimento local")
            return prompt

        # ── 3. ConfidenceTracker (FASE 1) ──────────────────────────
        task_hash = hashlib.sha3_512(prompt.encode()).hexdigest()[:_TASK_HASH_TRUNCATE]

        try:
            from iaglobal.search.confidence_tracker import should_search

            if not should_search(actual_agent, task_hash, _CONFIDENCE_THRESHOLD):
                logger.debug(
                    "[SEARCH] %s: skip — confiança alta (threshold=%.2f)",
                    actual_agent,
                    _CONFIDENCE_THRESHOLD,
                )
                return prompt
        except ImportError:
            logger.debug("[SEARCH] confidence_tracker indisponível")
        except Exception as exc:
            logger.debug("[SEARCH] ConfidenceTracker falhou: %s", exc)

        # ── 4. Extrai query ────────────────────────────────────────
        query = cls._extract_query(prompt)
        if not query:
            return prompt

        # ── 5. Busca no Obsidian (FASE 5) ──────────────────────────
        try:
            memory_results = await cls._search_memory(query)
            if memory_results:
                logger.info(
                    "[SEARCH] %s: hit Obsidian (%d resultados) | hash=%s",
                    node_id,
                    len(memory_results),
                    task_hash,
                )
                context_str = cls._format_memory_results(memory_results)
                enriched = cls._inject(prompt, context_str)
                asyncio.ensure_future(
                    cls._save_to_memory_async(query, context_str, node_id, task_hash)
                )
                return enriched
        except Exception as exc:
            logger.debug("[SEARCH] SearchMemory falhou: %s", exc)

        # ── 6. Query expansion + busca paralela (FASE 2) ────────────
        expanded = await cls._expand_query(query)
        all_queries = [query] + expanded[:_QUERY_MIN_LENGTH]
        raw_context = await cls._search_multi_query(all_queries)

        if not raw_context:
            logger.debug("[SEARCH] %s: sem resultados web/RAG", node_id)
            return prompt

        # ── 7. Síntese opcional (FASE 4) ───────────────────────────
        if cls._enable_synthesis:
            raw_context = await cls._synthesize_context(raw_context)

        enriched = cls._inject(prompt, raw_context)
        added_chars = len(enriched) - len(prompt)
        logger.info(
            "[SEARCH_MIDDLEWARE] %s: +%d chars | queries=%d | hash=%s",
            node_id,
            added_chars,
            len(all_queries),
            task_hash,
        )

        # ── 8. Persistência e feedback (fire-and-forget) ────────────
        asyncio.ensure_future(cls._record_feedback_async(node_id, task_hash, enriched))
        asyncio.ensure_future(
            cls._save_to_memory_async(query, raw_context, node_id, task_hash)
        )

        return enriched
