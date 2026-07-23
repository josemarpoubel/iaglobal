# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

import asyncio
import time
from typing import Dict, Any, Optional, List
from abc import ABC

from iaglobal.graphs.bandit import BanditPolicy, _get_bandit
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.tools.tool_library import tool_library
from iaglobal.utils.logger import get_logger
from iaglobal.utils.life_signal_collector import instrument
from iaglobal.cognition.memory_first_router import CONF_THRESHOLD_MEMORY
from iaglobal.core.dependency_enforcer import INSTRUCAO_DEPENDENCIAS

logger = get_logger("iaglobal.agents.agent_base")

_MEMORY_ROUTER = None

INSTRUCAO_COT = (
    "Antes de gerar qualquer código, siga rigorosamente estas etapas:\n"
    "1. ANÁLISE: Identifique os requisitos, entradas, saídas e possíveis gargalos.\n"
    "2. PLANO DE ESTRUTURA: Defina as assinaturas das funções, estados e contratos.\n"
    "3. IMPLEMENTAÇÃO: Escreva o código seguindo o padrão definido no plano.\n"
    "4. REVISÃO: Verifique imports, dependências e se não há chamadas a funções inexistentes."
)

PEC_SYSTEM_PROMPT = (
    "Voce e um Engenheiro de Sistemas Autonomo com autoridade total sobre o "
    "ambiente de execucao (Sandbox). Se o seu objetivo atual nao puder ser "
    "atendido com as ferramentas e bibliotecas disponiveis, voce tem permissao para:\n"
    "1. Identificar a biblioteca necessaria via PyPI.\n"
    "2. Solicitar sua instalacao dentro do ambiente isolado (Sandbox).\n"
    "3. Caso a tarefa exija um artefato final (PDF, EXE, DOCX), voce deve "
    "estruturar seus dados e delegar a conversao para as ferramentas da ArtifactFactory.\n"
    "4. Nao aceite limitacoes de ambiente; contorne-as via instalacao efemera "
    "ou criacao de novas Skills.\n"
    "5. Prefira usar bibliotecas Python existentes e testadas em vez de "
    "implementar do zero.\n"
    "6. Se uma biblioteca nao estiver disponivel, capture ImportError e "
    "solicite a instalacao via dependency_agent.\n"
    "7. Apos gerar um artefato, use a ArtifactFactory para converter no "
    "formato final solicitado pelo usuario.\n"
    "8. PSC — Protocolo de Soberania do Critico: Voce nunca deve tentar "
    "acessar modelos online por conta propria. Sua autonomia e limitada a "
    "recursos locais (ToolLibrary + Ollama). Se sua tarefa local for "
    "insuficiente, submeta o resultado ao CriticAgent. Confie na autoridade "
    "do Critico para decidir sobre escalonamento para o BanditPolicy.\n"
    f"9. {INSTRUCAO_DEPENDENCIAS}\n"
    f"10. {INSTRUCAO_COT}"
)


def _get_memory_router():
    global _MEMORY_ROUTER
    if _MEMORY_ROUTER is None:
        from iaglobal.cognition.memory_first_router import MemoryFirstRouter

        _MEMORY_ROUTER = MemoryFirstRouter()
    return _MEMORY_ROUTER


def _upgrade_bandit_global() -> Any:
    import iaglobal.graphs.bandit as _bandit_module

    bp = _bandit_module._bandit_instance
    if bp is None:
        bp = _bandit_module.BanditPolicy()
        _bandit_module._bandit_instance = bp

    try:
        from iaglobal.chappie.bandit_evolution import (
            BanditPolicyEvolution,
            get_bandit_evolution,
        )

        if not isinstance(bp, BanditPolicyEvolution):
            be = get_bandit_evolution()
            be._base.credit_engine = bp.credit_engine
            be._base.rewards.update(getattr(bp, "rewards", {}))
            _bandit_module._bandit_instance = be
            logger.info(
                "[AgentBase] BanditPolicy atualizado para BanditPolicyEvolution (Chappie)"
            )
            return be
        return bp
    except Exception:
        pass

    try:
        from iaglobal.policy import BanditPolicyEvolutiva

        if not isinstance(bp, BanditPolicyEvolutiva):
            evol = BanditPolicyEvolutiva(
                epsilon=bp.epsilon,
            )
            evol.credit_engine = bp.credit_engine
            evol.rewards.update(getattr(bp, "rewards", {}))
            _bandit_module._bandit_instance = evol
            logger.info(
                "[AgentBase] BanditPolicy atualizado para BanditPolicyEvolutiva"
            )
            return evol
        return bp
    except Exception:
        pass

    return _bandit_module._bandit_instance


def _get_ivm() -> Any:
    # Prioriza a instância canônica registrada no Chappie (persistida e lida pelos
    # observadores) para unificar telemetria IVM escrita (agentes) × leitura. Sem
    # isso, o singleton em memória de get_ivm_axiom() nunca é observado (split-brain).
    try:
        from iaglobal.chappie import _get_chappie

        ivm = _get_chappie().get("ivm")
        if ivm is not None:
            return ivm
    except Exception:
        pass
    try:
        from iaglobal.chappie.ivm_axiom import get_ivm_axiom

        return get_ivm_axiom()
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Registry Evolutivo — um EvoAgent por linhagem de agente (mitose controlada)
# ─────────────────────────────────────────────────────────────────────────────
# Todos os agentes que herdam de AgentBase compartilham um único EvoAgent por
# `agent_name`. Isso preserva a família evolutiva (mesmo lineage_marker) e evita
# instanciar milhares de organismos desnecessários.

_EVO_REGISTRY: Dict[str, Any] = {}
_EVO_REGISTRY_LOCK: Optional[Any] = None


def _get_evo_lock() -> Any:
    """Retorna (criando se necessário) o lock assíncrono do registry."""
    global _EVO_REGISTRY_LOCK
    if _EVO_REGISTRY_LOCK is None:
        _EVO_REGISTRY_LOCK = asyncio.Lock()
    return _EVO_REGISTRY_LOCK


def get_evo_registry() -> Dict[str, Any]:
    """Exposição somente-leitura do registry (útil para auditoria/debug)."""
    return dict(_EVO_REGISTRY)


class AgentBase(ABC):
    DEFAULT_CANDIDATES = [
        "ollama/qwen2.5:0.5b",
    ]

    def __init__(self, agent_name: str, bandit: Optional[BanditPolicy] = None):
        self.agent_name = agent_name
        if bandit is not None:
            self.bandit = bandit
        else:
            self.bandit = _get_bandit()
            _upgrade_bandit_global()
            import iaglobal.graphs.bandit as _bm

            if _bm._bandit_instance is not self.bandit:
                self.bandit = _bm._bandit_instance
        self._credit_engine: Optional[CreditAssignmentEngine] = None
        self._ivm = _get_ivm()
        self._last_evo_critique: Optional[Dict[str, Any]] = None
        self._tool_hits = 0
        self._llm_calls = 0

    @property
    def credit_engine(self) -> CreditAssignmentEngine:
        if self._credit_engine is None:
            self._credit_engine = self.bandit.credit_engine
        return self._credit_engine

    async def _resolve_with_tools(
        self, task: str, tags: Optional[list] = None
    ) -> Optional[str]:
        try:
            tool_entry, score = tool_library.match(task, tags or [])
            if tool_entry and score >= 0.7:
                logger.info(
                    "[%s] Tool match: %s (score=%.2f)",
                    self.agent_name.upper(),
                    tool_entry.name,
                    score,
                )
                result = tool_entry.fn(task)
                self._tool_hits += 1
                return str(result) if result else ""
        except Exception as e:
            logger.warning("[%s] Tool execution failed: %s", self.agent_name.upper(), e)
        return None

    @instrument(name="agent_base._call_llm")
    async def _call_llm(
        self,
        prompt: str,
        task_type: str,
        candidates: Optional[List[str]] = None,
        system_prompt: str = "",
        context: Optional[dict] = None,
        timeout: float = 30.0,
    ) -> str:
        tool_result = await self._resolve_with_tools(prompt, [task_type])
        if tool_result is not None:
            return tool_result

        router = _get_memory_router()
        memory_result = await router.route(prompt, task_type)
        response: Any = None
        if memory_result.found:
            effective_conf = router.get_effective_confidence(
                self.agent_name, memory_result.confidence
            )
            if effective_conf >= CONF_THRESHOLD_MEMORY:
                router.record_memory_resolution(self.agent_name)
                logger.info(
                    "[%s] Memory hit | source=%s conf_base=%.2f eff=%.2f latency=%.0fms",
                    self.agent_name.upper(),
                    memory_result.source,
                    memory_result.confidence,
                    effective_conf,
                    memory_result.latency_ms,
                )
                response = memory_result.content
            else:
                logger.info(
                    "[%s] Memory rejeitada (conf_base=%.2f eff=%.2f < limiar=%.2f) — forcando LLM",
                    self.agent_name.upper(),
                    memory_result.confidence,
                    effective_conf,
                    CONF_THRESHOLD_MEMORY,
                )

        candidates = candidates or self.DEFAULT_CANDIDATES
        from iaglobal.providers.provider_router import _provider_has_key

        candidates = [c for c in candidates if _provider_has_key(c.split("/")[0])]

        if context is None:
            context = {}
        if system_prompt:
            context["system_prompt"] = f"{PEC_SYSTEM_PROMPT}\n\n{system_prompt}"
        else:
            context["system_prompt"] = PEC_SYSTEM_PROMPT

        start_time = time.time()
        success = False
        model_used = "unknown"

        if response is None:
            try:
                from iaglobal.agents.critic_agent import _get_critic

                _final_prompt = (
                    prompt if not system_prompt else f"{system_prompt}\n\n{prompt}"
                )
                response = await _get_critic().arbitrar_geracao(
                    node_id=self.agent_name,
                    prompt=_final_prompt,
                    task_type=task_type,
                )

                latency = time.time() - start_time
                success = bool(response and len(str(response).strip()) > 0)
                model_used = (
                    getattr(self.bandit, "_last_model", None) or candidates[0]
                    if success
                    else candidates[0]
                )

                self._llm_calls += 1
                logger.info(
                    "[%s] %s (tools=%d llm=%d)",
                    self.agent_name.upper(),
                    "OK" if response else "FAIL",
                    self._tool_hits,
                    self._llm_calls,
                )

                if response:
                    await router.store_result(prompt, response, "llm")
                    if len(str(response)) > 100 and (
                        "def " in str(response) or "class " in str(response)
                    ):
                        try:
                            tool_library.register_from_code(prompt, str(response))
                        except Exception:
                            pass

                await self._registrar_ivm(
                    success=success, latencia_ms=latency * 1000, model=model_used
                )
            except Exception as e:
                latency = time.time() - start_time
                await self._registrar_ivm(
                    success=False, latencia_ms=latency * 1000, model=model_used
                )
                # Análise de falha → memória imunológica do EvoAgent (FailureAnalyzer)
                try:
                    await self.evo_analyze_failure(
                        e,
                        {
                            "prompt": (prompt or "")[:200],
                            "task_type": task_type,
                            "agent": self.agent_name,
                        },
                    )
                except Exception:
                    pass
                # Enriquecimento de erro (Chappie) — dentro do escopo do `except`
                # para manter `e` acessível e garantir o re-raise correto.
                try:
                    from iaglobal.chappie.error_enricher import ErrorContext
                    from datetime import datetime, UTC

                    enricher = getattr(self, "_error_enricher", None)
                    if enricher is None:
                        from iaglobal.chappie import _get_chappie

                        enricher = _get_chappie().get("error")
                    if enricher:
                        ctx = ErrorContext(
                            error_type=type(e).__name__,
                            error_message=str(e),
                            agent_name=self.agent_name,
                            task_id=task_type,
                            timestamp=datetime.now(UTC),
                        )
                        await enricher.enriquecher_e_gravar(ctx)
                except Exception:
                    pass
                raise  # re-levanta a exceção original (dentro do except)

        # Auto-crítica evolutiva (heurística pura, sem LLM) — roda para toda
        # resposta, independente da origem (memória ou provider). Gated por flag.
        if response:
            try:
                from iaglobal.evolution import is_flag_enabled

                if is_flag_enabled("evo_self_critique"):
                    self._last_evo_critique = await self.evo_self_critique(response)
            except Exception:
                pass

        return response or ""

    @staticmethod
    def _estimar_custo_creditos(model: str) -> float:
        """
        Mapeia modelo/provedor para custo relativo (créditos).
        Quanto maior, mais caro — usado no cost_score do Bandit Evolutivo.
        Baseado na tabela PRICING de provider_metrics.py.
        """
        m = model.lower()
        # Gratuitos — custo mínimo
        if any(
            p in m for p in ("ollama/", "opencode/", "hf_router", "hf_router_glm5f")
        ):
            return 0.1
        # Muito baratos (< $0.10/1K tok soma input+output)
        if any(p in m for p in ("groq/llama-3.1-8b", "groq/llama-3.3-70b", "groq/")):
            return 1.0
        if "gemini/gemini-2.5-flash" in m:
            return 2.0
        # Baratos
        if "nvidia/" in m:
            return 5.0
        if "openrouter/deepseek" in m:
            return 3.0
        if "openrouter/meta-llama/llama-3.1-8b" in m:
            return 2.0
        # Médio
        if "openrouter/mistral" in m:
            return 8.0
        if "openrouter/meta-llama/llama-3.3-70b" in m:
            return 5.0
        if "gemini/" in m:
            return 8.0
        # Caro — OpenRouter genérico ou modelos premium
        if "openrouter/anthropic" in m or "openrouter/openai" in m:
            return 50.0
        if "openrouter/" in m:
            return 20.0
        # Fallback
        return 10.0

    async def _registrar_ivm(
        self, success: bool, latencia_ms: float, model: str
    ) -> None:
        # O custo metabólico (IVM) é registrado centralmente no portão universal
        # BanditPolicy.generate (todo acesso a modelo de IA passa por lá), evitando
        # dupla contagem e o split-brain de observabilidade. Aqui mantemos apenas
        # a alimentação do CreditAssignmentEngine / EvoAgent.
        ivm = _get_ivm() or self._ivm

        if hasattr(self.bandit, "registrar_execucao"):
            try:
                ivm_val = (
                    ivm.get_ivm(self.agent_name) if ivm else (0.5 if success else 0.0)
                )
                await self.bandit.registrar_execucao(
                    provider_id=model,
                    ivm=ivm_val,
                    latencia_ms=latencia_ms,
                    custo_creditos=self._estimar_custo_creditos(model),
                    sucesso=success,
                )
            except Exception as e:
                logger.debug(
                    "[%s] Falha ao registrar evolutivo: %s", self.agent_name.upper(), e
                )

    async def _ciclo_evolutivo(self) -> None:
        if hasattr(self.bandit, "autonomous_cycle"):
            try:
                await self.bandit.autonomous_cycle()
            except Exception as e:
                logger.debug(
                    "[%s] Falha no ciclo evolutivo: %s", self.agent_name.upper(), e
                )

    # ─────────────────────────────────────────────────────────────────────
    # Integração Evolutiva — EvoAgent (mitose por linhagem de agente)
    # ─────────────────────────────────────────────────────────────────────

    def _evo_model_fn(self, prompt: str) -> str:
        """
        Shim síncrono que roteia inferência de reflexão pelo próprio LLM do
        agente (`_call_llm`, respeitando BanditPolicy). Executado dentro de
        `asyncio.to_thread` pelo EvoAgent — `asyncio.run()` substitui o loop
        manual descartável anterior.
        """
        try:
            return asyncio.run(self._call_llm(prompt=prompt, task_type="reflection"))
        except Exception as e:
            logger.debug("[%s] evo_model_fn falhou: %s", self.agent_name.upper(), e)
            return ""

    async def get_evo_agent(self) -> Any:
        """
        Retorna o EvoAgent compartilhado desta linhagem de agente.

        Cria (lazy, via EvoAgent.genesis) e registra no `_EVO_REGISTRY` na
        primeira chamada; injeta o `_evo_model_fn` para que o ReflexionEngine
        use o LLM do agente proprietário.
        """
        name = self.agent_name
        evo = _EVO_REGISTRY.get(name)
        if evo is not None:
            return evo
        async with _get_evo_lock():
            evo = _EVO_REGISTRY.get(name)
            if evo is not None:
                return evo
            from iaglobal.evolution.evo_agent import EvoAgent

            evo = await EvoAgent.genesis(task_hint=f"agent:{name}", name=f"evo-{name}")
            evo.set_model_fn(self._evo_model_fn)
            _EVO_REGISTRY[name] = evo
            logger.info(
                "[%s] EvoAgent de linhagem inicializado (marker=%s)",
                self.agent_name.upper(),
                evo.lineage_marker,
            )
        return evo

    # ── Delegação para os 4 módulos de reflexão ──────────────────────────

    async def evo_self_critique(self, output: str) -> Dict[str, Any]:
        """Auto-crítica do output via EvoAgent → SelfCritique."""
        evo = await self.get_evo_agent()
        return await evo.self_critique(output)

    async def evo_reflexion_fix(self, prompt: str, code: str | None = None) -> str:
        """Reflexão/auto-correção via EvoAgent → ReflexionEngine."""
        evo = await self.get_evo_agent()
        return await evo.reflexion_fix(prompt, code)

    async def evo_analyze_failure(
        self, error: Exception, context: Dict
    ) -> Dict[str, Any]:
        """Análise de falha via EvoAgent → FailureAnalyzer (memória imunológica)."""
        evo = await self.get_evo_agent()
        return await evo.analyze_failure(error, context)

    async def evo_learning_iterate(self, agent_func, task, evaluator) -> Dict[str, Any]:
        """Loop de aprendizado via EvoAgent → LearningLoop."""
        evo = await self.get_evo_agent()
        return await evo.learning_iterate(agent_func, task, evaluator)

    def _register_custom_metric(
        self,
        model: str,
        task_type: str,
        success: bool,
        latency: float,
        extra_data: Optional[Dict[str, Any]] = None,
    ):
        if not self.credit_engine:
            return

        from iaglobal.graphs.telemetry import ExecutionEvent

        self.credit_engine.record(
            ExecutionEvent(
                node=self.agent_name,
                model=model,
                strategy=task_type,
                latency=latency,
                success=success,
                reward=1.0 if success else 0.0,
            )
        )

        if extra_data:
            logger.debug(
                "[%s] Metrica customizada: %s", self.agent_name.upper(), extra_data
            )
