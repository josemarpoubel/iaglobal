"""CognitiveProxy — LLM Cognitive Proxy (Deterministic Orchestrator).

Proxy local que normaliza input, busca contexto (memória + web),
compila prompt estruturado anti-alucinação, roteia para modelo,
valida com crítico e registra aprendizado.

Pipeline:
  normalize → build_context → compile_prompt → route → validate → store → return
"""
# iaglobal/core/Cognitive_proxy.py

import re
import json
import time
from typing import Optional, List, Dict
from dataclasses import dataclass, field

from iaglobal._paths import MEMORIES_DB
from iaglobal.memory.term_short import ShortTermMemory
from iaglobal.memory.term_long import LongTermMemory
from iaglobal.tools.web_brain import WebBrain
from iaglobal.agents.critic_agent import CriticAgent, _get_critic
from iaglobal.agents.typing_agent import TypingService
from iaglobal.providers.provider_router import async_route_generate
from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.telemetry import ExecutionEvent
from iaglobal.execution.executor import blackjack_executar_local
from iaglobal.memory.memory import salvar
from iaglobal.memory.memory_vector import store, search
from iaglobal.memory.semantic_cache import SemanticCache
from iaglobal.core.retry_handler import RetryHandler
from iaglobal.core.governance import governance as _gov
from iaglobal.cognition.task_fingerprint import TaskFingerprint
from iaglobal.cognition.cognition_agents.task_classifier_agent import (
    TaskClassifierAgent,
)
from iaglobal.storage.batch_writer import batch_writer, Event as BatchEvent
from iaglobal.cognition.outcome_tracker import outcome_tracker, ExecutionOutcome
from iaglobal.graphs.state_store import SystemStateBuffer, SUCCESS, FAILED
from iaglobal.storage.snapshotter import snapshotter
from iaglobal.validation.validation_engine import FeedbackEngine, Decision

from iaglobal.utils.logger import logger
from iaglobal.utils.helpers import run_async_safe


@dataclass
class ProxyResult:
    success: bool
    output: str
    model_used: str = ""
    validation_passed: bool = True
    validation_attempts: int = 0
    context_sources: Dict = field(default_factory=dict)
    error: str = ""


class CognitiveProxy:
    """Proxy cognitivo determinístico com 6 estágios."""

    def __init__(
        self,
        web_enabled: bool = True,
        semantic_cache: bool = True,
        cache_threshold: float = 0.92,
        retry_enabled: bool = True,
    ):
        self.stm = ShortTermMemory(max_size=30, ttl_seconds=1800, db_path=MEMORIES_DB)
        self.ltm = LongTermMemory(max_size=200, db_path=MEMORIES_DB)
        self.webbrain = WebBrain() if web_enabled else None
        self.sem_cache = (
            SemanticCache(threshold=cache_threshold) if semantic_cache else None
        )
        self.retry = RetryHandler(llm_router=self._llm_call) if retry_enabled else None
        self._critic_degraded = False
        self.typing = TypingService()
        self.governance = _gov
        self.credit = CreditAssignmentEngine()
        self.bandit = BanditPolicy(self.credit)
        self.critic = CriticAgent(bandit=self.bandit)
        self.task_classifier = TaskClassifierAgent()
        self._batch = batch_writer
        self.state_buffer = SystemStateBuffer(max_size=500, snapshot_interval_ops=50)
        self.feedback = FeedbackEngine(snapshotter=snapshotter)

    def run_with_custom_prompt(
        self, user_input: str, custom_system: str = ""
    ) -> ProxyResult:
        """Run com system instruction personalizada."""
        query = self._normalize(user_input)
        fingerprint = self.task_classifier.classify(query)

        if self.sem_cache:
            cached = self.sem_cache.get(query)
            if cached:
                return ProxyResult(
                    success=True,
                    output=cached,
                    model_used="cache",
                    validation_passed=True,
                    validation_attempts=0,
                    context_sources={"cache": True},
                )

        context, sources = self._build_context(query)
        prompt = self._compile_prompt(query, context, custom_system=custom_system)

        raw_output, model = self._route(prompt, fingerprint)

        validated, attempts = self._validate(prompt, raw_output)

        if self.sem_cache and validated:
            self.sem_cache.set(query, validated)

        self._store_result(query, validated, fingerprint, success=True)
        return ProxyResult(
            success=True,
            output=validated,
            model_used=model,
            validation_passed=True,
            validation_attempts=attempts,
            context_sources=sources,
        )

    def run(self, user_input: str) -> ProxyResult:
        """Pipeline completo: normalize → classify → cache? → context → prompt → route → validate → store."""
        start_time = time.time()

        try:
            query = self._normalize(user_input)
            fingerprint = self.task_classifier.classify(query)
            logger.info(
                f"[COGNITIVE-PROXY] Iniciando: query={query[:60]}... "
                f"domain={fingerprint.domain} intent={fingerprint.intent}"
            )

            # Check semantic cache using fingerprint key
            if self.sem_cache:
                cache_key = f"{fingerprint.key()}:{query}"
                cached = self.sem_cache.get(cache_key)
                if cached:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"[COGNITIVE-PROXY] Semantic cache HIT: query={query[:40]}... "
                        f"response_len={len(cached)} elapsed={elapsed:.2f}s"
                    )
                    return ProxyResult(
                        success=True,
                        output=cached,
                        model_used="cache",
                        validation_passed=True,
                        validation_attempts=0,
                        context_sources={"cache": True},
                    )
                logger.debug(f"[COGNITIVE-PROXY] Semantic cache MISS: {query[:40]}...")

            # Track state in SystemStateBuffer
            self.state_buffer.set(fingerprint.key(), "running", output=None, attempt=0)

            context, sources = self._build_context(query)
            logger.info(
                f"[COGNITIVE-PROXY] Contexto construído: "
                f"mem={sources.get('memory', 0)} stm={sources.get('stm', 0)} "
                f"ltm={sources.get('ltm', 0)} web={sources.get('web', 0)}"
            )

            prompt = self._compile_prompt(query, context)
            logger.debug(f"[COGNITIVE-PROXY] Prompt compilado: {len(prompt)} chars")

            raw_output, model = self._route(prompt, fingerprint)
            validated, attempts = self._validate(prompt, raw_output)

            latency_ms = (time.time() - start_time) * 1000

            # Update state with result
            status = SUCCESS if validated else FAILED
            self.state_buffer.set(
                fingerprint.key(), status, output=validated, attempt=attempts
            )

            # Compress old entries periodically
            if self.state_buffer.size() > 200:
                self.state_buffer.compress_old_entries(keep_last=100)

            # Feed BanditPolicy with execution result
            self.credit.record(
                ExecutionEvent(
                    node="cognitive_proxy",
                    success=validated is not None,
                    latency=latency_ms,
                    model=model,
                    strategy=fingerprint.intent,
                )
            )

            # Emit async batch event
            self._batch.emit(
                BatchEvent(
                    event_type="cognitive_proxy_run",
                    payload=json.dumps(
                        {
                            "query": query[:200],
                            "validated_len": len(validated) if validated else 0,
                        }
                    ),
                    task_fingerprint=fingerprint.key(),
                    model=model,
                    latency_ms=latency_ms,
                    tokens_in=len(prompt),
                    tokens_out=len(validated) if validated else 0,
                    critical=False,
                )
            )

            # Store in semantic cache with fingerprint-aware key
            if self.sem_cache and validated:
                cache_key = f"{fingerprint.key()}:{query}"
                self.sem_cache.set(cache_key, validated)

            self._store_result(query, validated, fingerprint, success=True)
            self.stm.add(
                f"Q: {query}", {"type": "query", "fingerprint": fingerprint.key()}
            )
            self.stm.add(
                f"A: {validated[:100]}",
                {"type": "response", "fingerprint": fingerprint.key()},
            )

            # Record outcome for BanditPolicy/reputation
            provider = model.split("/")[0] if "/" in model else model
            outcome_tracker.record(
                ExecutionOutcome(
                    provider=provider,
                    model=model,
                    fingerprint=fingerprint.key(),
                    latency_ms=latency_ms,
                    token_cost=0.0,
                    success_score=1.0 if validated else 0.0,
                    tokens_in=len(prompt),
                    tokens_out=len(validated) if validated else 0,
                )
            )

            # Snapshot automático via SystemStateBuffer trigger
            if self.state_buffer.should_snapshot():
                snap_id = snapshotter.create_snapshot(
                    self.state_buffer.get_snapshot_data()
                )
                if snap_id:
                    self.state_buffer.mark_snapshot_done()
                    logger.debug(f"[COGNITIVE-PROXY] Snapshot automático: {snap_id}")

            elapsed = time.time() - start_time
            logger.info(
                f"[COGNITIVE-PROXY] Concluído: model={model} "
                f"response_len={len(validated)} valida_attempts={attempts} "
                f"elapsed={elapsed:.2f}s"
            )
            return ProxyResult(
                success=True,
                output=validated,
                model_used=model,
                validation_passed=True,
                validation_attempts=attempts,
                context_sources=sources,
            )
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[COGNITIVE-PROXY] Erro: {e} elapsed={elapsed:.2f}s")
            return ProxyResult(success=False, output="", error=str(e))

    # =========================================================================
    # 1. NORMALIZADOR DE INTENÇÃO (ANTI-AMBIGUIDADE)
    # =========================================================================
    def _normalize(self, text: str) -> str:
        """Normaliza input: strip, lower, remove ruído."""
        text = text.strip().lower() if text else ""
        text = re.sub(r"[^\w\s.,!?;:()\[\]{}=+\-*/@#%&|<>]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # =========================================================================
    # 2. CONSTRUTOR DE CONTEXTO (MEMÓRIA + WEB)
    # =========================================================================
    def _build_context(self, query: str) -> tuple:
        """NUNCA mandar prompt sem contexto estruturado."""
        sources = {}

        memory = search(query, top_k=3)
        sources["memory"] = len(memory)

        stm = self.stm.search(query, top_k=3)
        ltm = self.ltm.retrieve(query, top_k=3)
        sources["stm"] = len(stm)
        sources["ltm"] = len(ltm)

        web = []
        if self.webbrain:
            web = self.webbrain.search(query, max_results=3)
        sources["web"] = len(web)

        return {
            "memory": memory[:3],
            "stm": stm[:3],
            "ltm": ltm[:3],
            "web": web[:3],
        }, sources

    # =========================================================================
    # 3. COMPILADOR DE PROMPT (PEÇA MAIS IMPORTANTE — 80% DAS ALUCINAÇÕES)
    # =========================================================================
    def _compile_prompt(
        self, query: str, context: dict, custom_system: str = ""
    ) -> str:
        """Prompt rígido anti-alucinação."""
        mem_text = self._fmt_memory(context["memory"])
        stm_text = self._fmt_stm(context["stm"])
        ltm_text = self._fmt_ltm(context["ltm"])
        web_text = self._fmt_web(context["web"])
        state_ctx = self.state_buffer.get_compressed_context()

        system = custom_system or (
            "Você é um executor técnico. NÃO invente dados. "
            "Use apenas o contexto fornecido. "
            'Se não tiver certeza, diga "UNKNOWN". '
            "Não especule. Não crie bibliotecas inexistentes."
        )

        return f"""
[SYSTEM INSTRUCTION - OBRIGATÓRIO]
{system}

[REGRAS]
- Se não tiver certeza, diga "UNKNOWN"
- Não especule
- Não crie bibliotecas inexistentes
- Siga formato de código limpo
- Responda apenas com base no contexto abaixo

[MEMÓRIA VETORIAL]
{mem_text}

[MEMÓRIA DE CURTO PRAZO]
{stm_text}

[MEMÓRIA DE LONGO PRAZO]
{ltm_text}

[CONTEÚDO DA WEB]
{web_text}

{state_ctx}

[TAREFA]
{query}

[FORMATO DE SAÍDA]
- resposta objetiva
- código completo se necessário
- sem explicações desnecessárias
"""

    # =========================================================================
    # 4. ROUTER DE MODELOS (COM RETRY INTELIGENTE)
    # =========================================================================
    def _llm_call(self, model: str, prompt: str) -> Optional[str]:
        """Chamada LLM simples — usado pelo RetryHandler como router."""
        start = time.time()
        try:
            if model == "gpt_web_instruction":
                result = self._gpt_web_fallback(prompt)
                logger.info(
                    f"[COGNITIVE-PROXY] GPT Web fallback: prompt_len={len(prompt)}"
                )
                return result
            import os

            if os.environ.get("ARBITER_MODE", "enforce") == "shadow":
                run_async_safe(
                    _get_critic().arbitrar_geracao,
                    node_id="cognitive_proxy",
                    prompt=prompt,
                    task_type="cognitive_proxy",
                    context={"suggested_model": model},
                )
                result = run_async_safe(
                    async_route_generate,
                    model=model,
                    prompt=prompt,
                    task_type="cognitive_proxy",
                )
            else:
                result = run_async_safe(
                    _get_critic().arbitrar_geracao,
                    node_id="cognitive_proxy",
                    prompt=prompt,
                    task_type="cognitive_proxy",
                    context={"suggested_model": model},
                )
            elapsed = time.time() - start
            if result:
                logger.debug(
                    f"[COGNITIVE-PROXY] LLM ok: model={model} elapsed={elapsed:.2f}s "
                    f"response_len={len(result)}"
                )
                return result
            logger.warning(
                f"[COGNITIVE-PROXY] LLM empty response: model={model} elapsed={elapsed:.2f}s"
            )
            return None
        except Exception as e:
            elapsed = time.time() - start
            logger.debug(
                f"[COGNITIVE-PROXY] LLM fail: model={model} error={e} elapsed={elapsed:.2f}s"
            )
            return None

    def _gpt_web_fallback(self, prompt: str) -> Optional[str]:
        """Fallback externo — instrução técnica para ChatGPT Web com digitação humana."""
        logger.info(
            f"[COGNITIVE-PROXY] GPT Web fallback ativado: prompt_len={len(prompt)}"
        )

        estimated = self.typing.estimate_wait(prompt)
        logger.info(
            f"[COGNITIVE-PROXY] GPT Web: tempo estimado de digitação: {estimated:.1f}s"
        )

        result = self.typing.web_llm_call(prompt, model_name="chatgpt_web")

        logger.info(
            f"[COGNITIVE-PROXY] GPT Web fallback concluído: tempo_real={self.typing.agent.get_stats()['total_time']:.1f}s"
        )
        return result

    def _route(
        self, prompt: str, fingerprint: Optional[TaskFingerprint] = None
    ) -> tuple:
        """Roteia para modelo com retry inteligente e bandit para seleção.

        BanditPolicy é como guarda de trânsito: ele diz qual modelo vai
        para qual requisição baseado em score histórico (eficiência).
        Quem executa a chamada real é a pasta providers/.
        """
        start = time.time()

        # BanditPolicy seleciona o melhor modelo baseado em histórico
        candidates = self._get_model_candidates()
        fp_vector = fingerprint.to_vector() if fingerprint else candidates[0]
        fp_intent = fingerprint.intent if fingerprint else "general"
        model_name = self.bandit.select_model(
            node_id=fp_vector, task_type=fp_intent, candidates=candidates
        )

        logger.debug(
            f"[COGNITIVE-PROXY] Route: bandit_selected={model_name} candidates={candidates}"
        )

        if self.retry:
            result = self.retry.execute(prompt, model_name)
            elapsed = time.time() - start
            if result.success:
                self._record_bandit_result(result.model_used, True, elapsed)
                logger.info(
                    f"[COGNITIVE-PROXY] Route sucesso: model={result.model_used} "
                    f"attempts={result.attempts} level={result.escalation_level} "
                    f"elapsed={elapsed:.2f}s"
                )
                return result.output, result.model_used

            self._record_bandit_result(result.model_used or model_name, False, elapsed)
            logger.warning(
                f"[COGNITIVE-PROXY] Route retry esgotado: attempts={result.attempts} "
                f"error={result.error_type} level={result.escalation_level} "
                f"elapsed={elapsed:.2f}s"
            )
            return result.output or "", result.model_used

        # Sem retry: tenta modelo selecionado pelo bandit, depois fallback
        if len(prompt) > 4000:
            model_name = "ollama/qwen2.5:0.5b"
            logger.debug(
                f"[COGNITIVE-PROXY] Prompt longo ({len(prompt)}), forçando Ollama"
            )

        try:
            import os

            if os.environ.get("ARBITER_MODE", "enforce") == "shadow":
                run_async_safe(
                    _get_critic().arbitrar_geracao,
                    node_id="cognitive_proxy",
                    prompt=prompt,
                    task_type="cognitive_proxy",
                    context={"suggested_model": model_name},
                )
                result = run_async_safe(
                    async_route_generate,
                    model=model_name,
                    prompt=prompt,
                    task_type="cognitive_proxy",
                )
            else:
                result = run_async_safe(
                    _get_critic().arbitrar_geracao,
                    node_id="cognitive_proxy",
                    prompt=prompt,
                    task_type="cognitive_proxy",
                    context={"suggested_model": model_name},
                )
            if result:
                elapsed = time.time() - start
                self._record_bandit_result(model_name, True, elapsed)
                logger.info(
                    f"[COGNITIVE-PROXY] Route direto: model={model_name} elapsed={elapsed:.2f}s"
                )
                return result, model_name
        except Exception as e:
            logger.warning(
                f"[COGNITIVE-PROXY] Route fail: model={model_name} error={e}"
            )

        try:
            logger.info(f"[COGNITIVE-PROXY] Fallback para Ollama local")
            result = blackjack_executar_local("qwen2.5:0.5b", prompt)
            elapsed = time.time() - start
            self._record_bandit_result("ollama/qwen2.5:0.5b", bool(result), elapsed)
            logger.info(f"[COGNITIVE-PROXY] Fallback concluído: elapsed={elapsed:.2f}s")
            return result, "ollama/qwen2.5:0.5b"
        except Exception as e:
            elapsed = time.time() - start
            self._record_bandit_result("fallback", False, elapsed)
            logger.error(
                f"[COGNITIVE-PROXY] Fallback falhou: {e} elapsed={elapsed:.2f}s"
            )
            return f"Fallback error: {e}", "fallback"

    def _get_model_candidates(self) -> List[str]:
        """Retorna lista de modelos candidatos para o bandit."""
        return [
            "ollama/qwen2.5:0.5b",
            "groq/llama-3.1-8b-instant",
            "openrouter/meta-llama/llama-3.1-8b-instruct",
            "nvidia/mistralai/mistral-large-3-675b-instruct-2512",
            "opencode/nemotron-3-super-free",
        ]

    def _record_bandit_result(
        self,
        model: str,
        success: bool,
        latency: float,
        fingerprint: Optional[TaskFingerprint] = None,
        score: float = 1.0,
    ):
        """
        Alimenta o CreditAssignmentEngine com telemetria de execução rica.
        Agora rastreia estratégia específica (via fingerprint) e score de sucesso.
        """
        try:
            # Captura a intenção/estratégia real a partir do fingerprint,
            # em vez de usar o default "general".
            strategy = fingerprint.intent if fingerprint else "general"
            domain = fingerprint.domain if fingerprint else "unknown"

            # Cria o evento com metadados de evolução
            event = ExecutionEvent(
                node="cognitive_proxy",
                success=success,
                latency=latency,
                model=model,
                strategy=strategy,
                metadata={
                    "domain": domain,
                    "score": score,
                    "model_family": model.split("/")[0] if "/" in model else "unknown",
                },
            )

            # Registra no motor de crédito
            self.credit.record(event)

            logger.debug(
                f"[COGNITIVE-PROXY] Bandit record: model={model} "
                f"strategy={strategy} success={success} score={score:.2f}"
            )

        except Exception as e:
            # Upgrade de log: erro de aprendizado é um erro de sistema
            logger.error(
                f"[COGNITIVE-PROXY] Falha crítica ao registrar aprendizado: {e}"
            )

    # =========================================================================
    # 5. FEEDBACK ENGINE (VALIDAÇÃO FORMAL + PATCH SAFE APPLY)
    # =========================================================================
    def _validate(
        self, input_prompt: str, output: str, context: Optional[Dict] = None
    ) -> tuple:
        """Valida saída com FeedbackEngine + Critic (sensor de qualidade).

        Fluxo:
          1. FeedbackEngine valida sintaxe/AST/segurança
          2. Se código válido → aprovado
          3. Se inválido → Critic avalia qualidade semântica
          4. Proxy decide: aceitar, retry ou rollback
        """
        attempts = 0
        current_output = output

        # Validações rápidas
        has_unknown = "UNKNOWN" in current_output
        is_empty = not current_output or len(current_output.strip()) < 10

        if has_unknown:
            logger.info(f"[PROXY] Output contém UNKNOWN — aceitando (intencional)")
            return current_output, 0

        if is_empty:
            logger.warning(f"[PROXY] Output vazio — rejeitando")
            return current_output, 0

        # FeedbackEngine: validação formal (sintaxe + AST + segurança)
        fb_result = self.feedback.validate(current_output, context)
        attempts = 1

        if fb_result.valid:
            logger.debug(f"[PROXY] FeedbackEngine aprovou: score={fb_result.score}")
            return fb_result.code or current_output, attempts

        logger.info(
            f"[PROXY] FeedbackEngine rejeitou: {fb_result.errors} "
            f"decisão={fb_result.decision.value}"
        )

        # Se for ROLLBACK, tenta restaurar snapshot
        if fb_result.decision == Decision.ROLLBACK:
            snap_data = snapshotter.rollback()
            if snap_data:
                self.state_buffer.load_snapshot(snap_data)
                logger.info(f"[PROXY] Rollback executado: estado restaurado")

        # Critic como sensor passivo (APENAS score semântico)
        try:
            critic_result = run_async_safe(
                self.critic.avaliar,
                task=input_prompt[:500],
                prompt=input_prompt[:500],
                output=current_output,
            )

            score = critic_result.get("score", 0)
            issues = critic_result.get("issues", [])
            approved = critic_result.get("approved", False)

            if approved:
                logger.info(f"[PROXY] Critic aprovou: score={score} issues={issues}")
                return current_output, attempts

            logger.info(
                f"[PROXY] Critic rejeitou: score={score} issues={issues} "
                f"— Proxy decide continuar (critic é sensor, não juiz)"
            )

        except Exception as e:
            logger.debug(
                f"[PROXY] Critic sensor falhou: {e} — continuando sem avaliação"
            )
            self._critic_degraded = True

        return current_output, attempts

    # =========================================================================
    # 6. MEMÓRIA (APRENDIZADO REAL)
    # =========================================================================
    def _store_result(
        self,
        query: str,
        output: str,
        fingerprint: Optional[TaskFingerprint] = None,
        success: bool = True,
    ):
        """Registra resultado para aprendizado com fingerprint."""
        try:
            fp_key = fingerprint.key() if fingerprint else "unknown"
            memoria = f"COGNITIVE_PROXY | {fp_key} | Q: {query} | A: {output[:200]}"
            salvar(memoria)
            store(text=memoria, mtype="cognitive_proxy")
            self.ltm.store(
                output[:500],
                {"query": query, "fingerprint": fp_key, "success": success},
                source="cognitive_proxy",
            )
        except Exception as e:
            logger.debug(f"[COGNITIVE-PROXY] Store error: {e}")

    # =========================================================================
    # FORMATADORES DE CONTEXTO
    # =========================================================================
    def _fmt_memory(self, items: list) -> str:
        if not items:
            return "(sem memória vetorial)"
        lines = []
        for item in items[:3]:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                score, data = item
                text = (
                    data.get("text", str(data)) if isinstance(data, dict) else str(data)
                )
                lines.append(f"[score={score:.2f}] {text[:200]}")
            else:
                lines.append(str(item)[:200])
        return "\n".join(lines) or "(sem memória vetorial)"

    def _fmt_stm(self, items: list) -> str:
        if not items:
            return "(sem histórico recente)"
        return "\n".join(e.get("content", str(e))[:200] for e in items[:3])

    def _fmt_ltm(self, items: list) -> str:
        if not items:
            return "(sem memória de longo prazo)"
        lines = []
        for m in items[:3]:
            c = (m.get("content") or "")[:150]
            s = m.get("source", "?")
            lines.append(f"[{s}] {c}")
        return "\n".join(lines)

    def _fmt_web(self, items: list) -> str:
        if not items:
            return "(sem consulta web)"
        lines = []
        for r in items[:3]:
            c = (r.get("content") or "")[:200]
            s = r.get("source", "?")
            t = r.get("title", "")
            lines.append(f"[{s}] {t}: {c}")
        return "\n".join(lines)
