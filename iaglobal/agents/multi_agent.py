# iaglobal/agents/multi_agent.py


"""
iaglobal/agents/multi_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Orquestrador multi-agente do ciclo metabólico iaglobal — Geração 8.


Arquitetura:

PipelineOrchestrator
  └─ PhaseRunner (CircuitBreaker por fase)
       ├─ ContextPhase      → CognitiveProxy
       ├─ PlannerPhase      → PlannerAgent + SuccessRegistry
       ├─ MultiCoderPhase   → AgentPool × AgentProfile[]
       ├─ CriticPhase       → CriticAgent + SemanticValidator
       ├─ EvalPhase         → CandidateEvaluator (ScoringPolicy)
       ├─ DebugPhase        → DebuggerAgent × MAX_ITERATIONS
       ├─ ReflexionPhase    → ReflexionAgent
       └─ MemoryPhase       → SuccessRegistry

Infraestrutura transversal:
  StructuredLogger    — campos uniformes em todo log
  ScoringPolicy       — magic numbers com semântica e nome
  AgentPool           — lifecycle de agentes com thread-lock
  CircuitBreaker      — proteção de fase com budget de falhas
  SuccessRegistry     — abstraction sobre sqlite3+cbor2
  CandidateEvaluator  — scoring isolado e testável
  PipelineState       — imutabilidade progressiva via .evolve()


Princípios:
  • Imutabilidade progressiva: PipelineState é substituído, não mutado
  • Dependency Injection em tudo que pode ser testado
  • SRP rigoroso: cada classe tem uma única razão para mudar
  • Fail-fast com resultado tipado (PhaseResult) ao invés de exceção nua
  • Observabilidade estruturada: todos os logs em formato de campo uniforme
"""

from __future__ import annotations

import re
import time
import sqlite3
import logging
import functools
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import (
    Any, Callable, Dict, Generator, List, Optional,
    Protocol, Sequence, Tuple, TypeVar, Union,
)

import cbor2

from iaglobal.models.task import Task
from iaglobal.models.agent_context import AgentContext
from iaglobal.agents.tester_agent import TesterAgent
from iaglobal.agents.planner_agent import PlannerAgent
from iaglobal.agents.critic_agent import CriticAgent
from iaglobal.agents.coder_agent import CoderAgent
from iaglobal.agents.debugger_agent import DebuggerAgent
from iaglobal.agents.reflexion_agent import ReflexionAgent
from iaglobal.agents.validator import SemanticValidatorAgent
from iaglobal.core.cognitive_proxy import CognitiveProxy
from iaglobal.core.governance import governance
from iaglobal.validation.engine import ValidationEngine
from iaglobal.execution.sandbox import executar_codigo_sandbox as executar_codigo
from iaglobal.memory.memory_error import (
    store_error,
    format_errors_for_prompt,
    query_relevant_errors,
)
from iaglobal.memory.memory_storage import store_success
from iaglobal.models.event_bus import bus, EventType
from iaglobal.utils.logger import logger as _base_logger
from iaglobal._paths import CORE_DB

# ─────────────────────────────────────────────────────────────────────────────
# Logging estruturado
# ─────────────────────────────────────────────────────────────────────────────

_T = TypeVar("_T")


class StructuredLogger:
    """Wrapper que força campos contextuais em todo log emitido."""

    def __init__(self, base: logging.Logger, context: Dict[str, Any] | None = None) -> None:
        self._log = base
        self._ctx: Dict[str, Any] = context or {}

    def bind(self, **kwargs: Any) -> "StructuredLogger":
        return StructuredLogger(self._log, {**self._ctx, **kwargs})

    def _fmt(self, msg: str, extra: Dict[str, Any]) -> str:
        merged = {**self._ctx, **extra}
        pairs = " ".join(f"{k}={v!r}" for k, v in merged.items())
        return f"{msg} | {pairs}" if pairs else msg

    def info(self, msg: str, **kw: Any) -> None:
        self._log.info(self._fmt(msg, kw))

    def warning(self, msg: str, **kw: Any) -> None:
        self._log.warning(self._fmt(msg, kw))

    def error(self, msg: str, **kw: Any) -> None:
        self._log.error(self._fmt(msg, kw))

    def debug(self, msg: str, **kw: Any) -> None:
        self._log.debug(self._fmt(msg, kw))


log = StructuredLogger(_base_logger)


# ─────────────────────────────────────────────────────────────────────────────
# Tipos e contratos
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AgentProfile:
    """Perfil imutável de um agente gerador."""
    name: str
    temperature: float
    style: str


# Perfis declarativos — adicionar novos sem tocar em lógica
AGENT_PROFILES: Tuple[AgentProfile, ...] = (
    AgentProfile("dev_fast",        temperature=0.3, style="fast"),
    AgentProfile("dev_safe",        temperature=0.1, style="safe"),
    AgentProfile("dev_exploratory", temperature=0.7, style="exploratory"),
)


@dataclass(frozen=True)
class ScoringPolicy:
    """
    Encapsula todas as decisões de pontuação com semântica explícita.
    Permite ajuste por configuração sem caçar magic numbers.
    """
    # Peso das dimensões no score final
    weight_tests: float = 0.50
    weight_critic: float = 0.50

    # Score mínimo para considerar uma solução bem-sucedida
    success_threshold: float = 80.0

    # Penalidades
    penalty_per_line: float = 0.05   # verbose demais
    penalty_per_second: float = 2.0  # lento demais
    max_line_penalty: float = 5.0
    max_time_penalty: float = 5.0

    # Score base quando sandbox falha mas há testes parciais
    sandbox_failure_multiplier: float = 0.80

    def score_from_tests(self, passed: int, total: int, sandbox_ok: bool) -> float:
        if sandbox_ok:
            return 100.0
        if total == 0:
            return 0.0
        return (passed / total) * 100.0 * self.sandbox_failure_multiplier

    def critic_score(self, critiques: Sequence[str]) -> float:
        if not critiques:
            return 0.0
        approved = any("OK" in c or "approved" in c.lower() for c in critiques)
        return 100.0 if approved else 50.0

    def blend(
        self,
        test_score: float,
        critic_score: float,
        line_count: int,
        exec_seconds: float,
        has_critiques: bool,
    ) -> float:
        if has_critiques:
            base = test_score * self.weight_tests + critic_score * self.weight_critic
        else:
            base = test_score

        line_penalty = min(line_count * self.penalty_per_line, self.max_line_penalty)
        time_penalty = min(exec_seconds * self.penalty_per_second, self.max_time_penalty)
        return round(max(0.0, base - line_penalty - time_penalty), 2)

    @property
    def is_successful(self) -> Callable[[float], bool]:
        return lambda score: score >= self.success_threshold


@dataclass
class CandidateResult:
    """Resultado tipado de avaliação de um candidato."""
    agent_name: str
    code: str
    score: float
    tests_passed: int
    tests_total: int
    exec_seconds: float
    error_output: str = ""

    @property
    def is_viable(self) -> bool:
        return self.score > 0.0


@dataclass
class PipelineState:
    """
    Estado imutável-progressivo do pipeline.

    Cada fase retorna uma NOVA instância via `evolve(**changes)`,
    garantindo rastreabilidade sem mutação implícita.
    """
    task: str
    knowledge: str = ""
    plan: Dict[str, Any] = field(default_factory=dict)
    candidates: Dict[str, str] = field(default_factory=dict)
    candidate_results: List[CandidateResult] = field(default_factory=list)
    best: Optional[CandidateResult] = None
    reflections: List[Dict[str, Any]] = field(default_factory=list)
    debug_iterations: int = 0

    @property
    def is_successful(self) -> bool:
        return self.best is not None and self.best.score >= ScoringPolicy().success_threshold

    @property
    def best_code(self) -> str:
        return self.best.code if self.best else ""

    def evolve(self, **changes: Any) -> "PipelineState":
        """Retorna nova instância com campos atualizados (copy-on-write)."""
        import dataclasses
        return dataclasses.replace(self, **changes)


@dataclass(frozen=True)
class PhaseResult:
    """Resultado tipado de uma fase do pipeline."""
    state: PipelineState
    ok: bool
    phase_name: str
    elapsed: float
    error: str = ""

    @classmethod
    def success(cls, name: str, state: PipelineState, elapsed: float) -> "PhaseResult":
        return cls(state=state, ok=True, phase_name=name, elapsed=elapsed)

    @classmethod
    def failure(cls, name: str, state: PipelineState, elapsed: float, error: str) -> "PhaseResult":
        return cls(state=state, ok=False, phase_name=name, elapsed=elapsed, error=error)


# ─────────────────────────────────────────────────────────────────────────────
# Infraestrutura: AgentPool, CircuitBreaker, SuccessRegistry
# ─────────────────────────────────────────────────────────────────────────────

class AgentPool:
    """
    Pool de agentes com lifecycle gerenciado.
    Evita instanciação repetida dentro de loops (custo de inicialização).
    Thread-safe via lock por profile key.
    """

    def __init__(self) -> None:
        self._coders: Dict[str, CoderAgent] = {}
        self._lock = threading.Lock()

    def get_coder(self, profile: AgentProfile) -> CoderAgent:
        key = f"{profile.temperature}:{profile.style}"
        with self._lock:
            if key not in self._coders:
                self._coders[key] = CoderAgent(
                    temperatura=profile.temperature,
                    estilo=profile.style,
                )
            return self._coders[key]

    def fresh_planner(self) -> PlannerAgent:
        return PlannerAgent()

    def fresh_critic(self) -> CriticAgent:
        return CriticAgent()

    def fresh_debugger(self) -> DebuggerAgent:
        return DebuggerAgent()

    def fresh_reflexion(self) -> ReflexionAgent:
        return ReflexionAgent()

    def fresh_semantic(self) -> SemanticValidatorAgent:
        return SemanticValidatorAgent()


class CircuitBreaker:
    """
    Proteção de fase com timeout por thread e budget de falhas.

    Se uma fase falhar `max_failures` vezes consecutivas, abre o circuito
    e retorna PhaseResult.failure imediatamente sem chamar o callable.
    """

    def __init__(self, max_failures: int = 3, timeout_seconds: float = 60.0) -> None:
        self._max_failures = max_failures
        self._timeout = timeout_seconds
        self._failures: Dict[str, int] = {}
        self._lock = threading.Lock()

    def is_open(self, phase_name: str) -> bool:
        with self._lock:
            return self._failures.get(phase_name, 0) >= self._max_failures

    def record_failure(self, phase_name: str) -> None:
        with self._lock:
            self._failures[phase_name] = self._failures.get(phase_name, 0) + 1

    def record_success(self, phase_name: str) -> None:
        with self._lock:
            self._failures[phase_name] = 0

    @contextmanager
    def guard(self, phase_name: str) -> Generator[None, None, None]:
        if self.is_open(phase_name):
            raise RuntimeError(f"CircuitBreaker aberto para fase '{phase_name}'")
        try:
            yield
            self.record_success(phase_name)
        except Exception:
            self.record_failure(phase_name)
            raise


class SuccessRegistry:
    """
    Abstraction sobre sqlite3 + cbor2 para busca de soluções anteriores.

    Isola completamente o acesso a banco do pipeline, com connection pooling
    por thread e query parametrizada.
    """

    _local = threading.local()

    def __init__(self, db_path: str = str(CORE_DB)) -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def find_similar(self, task: str, limit: int = 20) -> Optional[Dict[str, Any]]:
        """Retorna a solução mais recente semanticamente similar à task."""
        task_lower = task.lower()
        try:
            rows = self._conn().execute(
                "SELECT data FROM success_registry ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        except sqlite3.Error as exc:
            log.warning("SuccessRegistry.find_similar falhou", error=str(exc))
            return None

        for (blob,) in rows:
            if not blob:
                continue
            try:
                record = cbor2.loads(blob)
                stored_task = str(record.get("task", ""))
                if task_lower not in stored_task.lower():
                    continue
                code = record.get("codigo") or record.get("code") or record.get("solution")
                if not code:
                    continue
                return {
                    "code": code.decode("utf-8") if isinstance(code, bytes) else code,
                    "task": stored_task,
                }
            except Exception:
                continue
        return None

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None


# ─────────────────────────────────────────────────────────────────────────────
# Avaliação de candidatos
# ─────────────────────────────────────────────────────────────────────────────

class CandidateEvaluator:
    """
    Responsabilidade única: avaliar um candidato de código e retornar CandidateResult.

    Separa completamente a lógica de scoring do orquestrador.
    """

    def __init__(
        self,
        tester: TesterAgent,
        policy: ScoringPolicy | None = None,
    ) -> None:
        self._tester = tester
        self._policy = policy or ScoringPolicy()

    def evaluate(
        self,
        profile_name: str,
        code: str,
        task: str,
        subtask_desc: str,
        critiques: Sequence[str],
    ) -> CandidateResult:
        t0 = time.perf_counter()

        test_code = self._tester.gerar_bateria_testes(subtask_desc, code)
        full_code = self._tester.amalgamar_codigo_e_teste(code, test_code)
        sandbox_result = executar_codigo(full_code)

        exec_seconds = time.perf_counter() - t0
        output = sandbox_result.get("output", "").strip()
        sandbox_ok = sandbox_result.get("sucesso", False)

        total, failed = _parse_test_output(output)
        passed = total - failed

        test_score = self._policy.score_from_tests(passed, total, sandbox_ok)
        critic_score = self._policy.critic_score(critiques)
        final_score = self._policy.blend(
            test_score=test_score,
            critic_score=critic_score,
            line_count=len(code.splitlines()),
            exec_seconds=exec_seconds,
            has_critiques=bool(critiques),
        )

        if test_score >= self._policy.success_threshold and sandbox_ok:
            saved = self._tester.gerar_salvar_e_executar(code, subtask_desc)
            if saved.get("sucesso"):
                log.info("Teste persistido", agent=profile_name, file=saved.get("arquivo", ""))

        bus.publish(
            EventType.SOLUTION_GENERATED,
            {
                "agent": profile_name,
                "score": final_score,
                "tests_passed": passed,
                "tests_total": total,
                "execution_time": round(exec_seconds, 4),
                "task": task[:100],
            },
            source="CandidateEvaluator.evaluate",
        )

        log.info(
            "Candidato avaliado",
            agent=profile_name,
            score=final_score,
            tests=f"{passed}/{total}",
            sandbox=sandbox_ok,
            exec_s=round(exec_seconds, 3),
        )
        return CandidateResult(
            agent_name=profile_name,
            code=code,
            score=final_score,
            tests_passed=passed,
            tests_total=total,
            exec_seconds=exec_seconds,
            error_output=output,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Fases do pipeline
# ─────────────────────────────────────────────────────────────────────────────

class Phase(ABC):
    """Contrato de fase: recebe PipelineState, devolve PhaseResult."""

    name: str = "unnamed_phase"

    @abstractmethod
    def run(self, state: PipelineState) -> PhaseResult:
        ...


def _timed_phase(fn: Callable[["Phase", PipelineState], PipelineState]) -> Callable[["Phase", PipelineState], PhaseResult]:
    """Decorator: mede elapsed, captura exceções, devolve PhaseResult."""
    @functools.wraps(fn)
    def wrapper(self: "Phase", state: PipelineState) -> PhaseResult:
        t0 = time.perf_counter()
        try:
            new_state = fn(self, state)
            elapsed = time.perf_counter() - t0
            log.info(f"Fase concluída", phase=self.name, elapsed_s=round(elapsed, 2))
            return PhaseResult.success(self.name, new_state, elapsed)
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            log.error(f"Fase falhou", phase=self.name, error=str(exc), elapsed_s=round(elapsed, 2))
            return PhaseResult.failure(self.name, state, elapsed, str(exc))
    return wrapper  # type: ignore[return-value]


class ContextPhase(Phase):
    """Fase 1-3: CognitiveProxy constrói contexto unificado."""

    name = "context"

    def __init__(self, proxy: CognitiveProxy) -> None:
        self._proxy = proxy

    @_timed_phase
    def run(self, state: PipelineState) -> PipelineState:
        governance.validate_call("search", {"query": state.task}, "busca web via proxy")
        try:
            context, sources = self._proxy._build_context(state.task)
        except Exception as exc:
            log.warning("CognitiveProxy falhou, usando contexto vazio", error=str(exc))
            context, sources = {"memory": [], "web": [], "stm": [], "ltm": []}, {}

        mem_text = _fmt_context_items(context.get("memory", []))
        web_text = _fmt_context_items(context.get("web", []))
        knowledge = f"[MEMÓRIA]\n{mem_text}\n\n[WEB]\n{web_text}"

        log.info(
            "Contexto construído",
            mem=sources.get("memory", 0),
            web=sources.get("web", 0),
            ltm=sources.get("ltm", 0),
            stm=sources.get("stm", 0),
        )
        return state.evolve(knowledge=knowledge)


class PlannerPhase(Phase):
    """Fase 4: PlannerAgent decompõe a tarefa em subtarefas."""

    name = "planner"

    def __init__(self, pool: AgentPool, registry: SuccessRegistry) -> None:
        self._pool = pool
        self._registry = registry

    @_timed_phase
    def run(self, state: PipelineState) -> PipelineState:
        governance.validate_call("planner", {"task": state.task})
        planner = self._pool.fresh_planner()

        previous = self._registry.find_similar(state.task)
        historical_code = previous.get("code", "") if previous else ""
        log.debug("Histórico encontrado", chars=len(historical_code))

        plan = planner.criar_plano_execucao(state.task, historical_code)
        if not plan or not isinstance(plan, dict):
            bus.publish(
                EventType.SANITY_BARRIER_TRIGGERED,
                {"failed_node": "PlannerAgent", "error": "Plano inválido", "task": state.task[:200]},
                source="PlannerPhase",
            )
            store_error(
                prompt=f"sanity_barrier:planner_falhou:{state.task[:100]}",
                response="Plano inválido",
                critique="Sanity Barrier",
                corrected="",
                error_type="SanityBarrier",
            )
            raise ValueError("Plano inválido retornado pelo PlannerAgent")

        n = len(plan.get("subtarefas", []))
        log.info("Plano criado", subtarefas=n, complexidade=plan.get("complexidade", "?"))
        return state.evolve(plan=plan)


class MultiCoderPhase(Phase):
    """Fase 5: Gera candidatos em paralelo por perfil de agente."""

    name = "multi_coder"

    def __init__(self, pool: AgentPool, profiles: Tuple[AgentProfile, ...] = AGENT_PROFILES) -> None:
        self._pool = pool
        self._profiles = profiles

    @_timed_phase
    def run(self, state: PipelineState) -> PipelineState:
        governance.validate_call("coder", {"task": state.task})

        errors = query_relevant_errors(state.task, limit=2)
        error_ctx = format_errors_for_prompt(errors)
        log.debug("Erros históricos carregados", count=len(errors))

        candidates: Dict[str, str] = {}
        for profile in self._profiles:
            t0 = time.perf_counter()
            try:
                coder = self._pool.get_coder(profile)
                code = coder.gerar_codigo(
                    state.task,
                    contexto=state.knowledge,
                    erros_contexto=error_ctx,
                )
                elapsed = time.perf_counter() - t0
                if code:
                    candidates[profile.name] = code
                    log.info(
                        "Candidato gerado",
                        agent=profile.name,
                        chars=len(code),
                        elapsed_s=round(elapsed, 2),
                    )
                else:
                    log.warning("Candidato vazio", agent=profile.name, elapsed_s=round(elapsed, 2))
            except Exception as exc:
                log.error("Falha ao gerar candidato", agent=profile.name, error=str(exc))

        return state.evolve(candidates=candidates)


class CriticPhase(Phase):
    """Fase 6: Avalia cada candidato com Critic + SemanticValidator."""

    name = "critic"

    def __init__(self, pool: AgentPool) -> None:
        self._pool = pool

    @_timed_phase
    def run(self, state: PipelineState) -> PipelineState:
        governance.validate_call("critic", {"task": state.task, "output": ""})

        critic = self._pool.fresh_critic()
        semantic = self._pool.fresh_semantic()

        # Armazenamos críticas por nome de candidato no plan temporariamente;
        # passamos para EvalPhase via state.plan["_critiques"] (campo interno)
        critiques: Dict[str, List[str]] = {}

        for name, code in state.candidates.items():
            candidate_critiques: List[str] = []
            try:
                note = critic.avaliar_solucao(state.task, code)
                candidate_critiques.append(note)
            except Exception as exc:
                candidate_critiques.append(f"REJECT: {exc}")
                log.warning("Crítica falhou", agent=name, error=str(exc))

            try:
                sem = semantic.validate(code, state.task)
                if not sem.get("valid"):
                    candidate_critiques.append(
                        f"REJECT: {'; '.join(sem.get('errors', []))}"
                    )
            except Exception:
                pass

            critiques[name] = candidate_critiques

        bus.publish(
            EventType.CRITIC_SWARM_COMPLETED,
            {"task": state.task[:100], "candidates": len(state.candidates)},
            source="CriticPhase",
        )

        # Injeta críticas no plano como campo interno (sem poluir o schema)
        enriched_plan = {**state.plan, "_critiques": critiques}
        return state.evolve(plan=enriched_plan)


class EvalPhase(Phase):
    """Fase 7: Testa e ranqueia candidatos, seleciona o melhor."""

    name = "eval"

    def __init__(self, evaluator: CandidateEvaluator, policy: ScoringPolicy) -> None:
        self._evaluator = evaluator
        self._policy = policy

    def run(self, state: PipelineState) -> PhaseResult:
        t0 = time.perf_counter()
        critiques: Dict[str, List[str]] = state.plan.get("_critiques", {})
        subtask_desc = state.task  # fallback; caller injeta desc real

        results: List[CandidateResult] = []
        for name, code in state.candidates.items():
            result = self._evaluator.evaluate(
                profile_name=name,
                code=code,
                task=state.task,
                subtask_desc=subtask_desc,
                critiques=critiques.get(name, []),
            )
            results.append(result)

        results.sort(key=lambda r: r.score, reverse=True)
        best = results[0] if results else None

        bus.publish(
            EventType.RANKING_COMPLETED,
            {
                "task": state.task[:100],
                "best_score": best.score if best else 0.0,
                "rankings": [{"agent": r.agent_name, "score": r.score} for r in results],
            },
            source="EvalPhase",
        )

        elapsed = time.perf_counter() - t0
        if not results:
            return PhaseResult.failure(self.name, state, elapsed, "Nenhum candidato avaliado")

        new_state = state.evolve(candidate_results=results, best=best)
        log.info(
            "Ranking concluído",
            best=best.agent_name if best else "none",
            score=best.score if best else 0.0,
            total=len(results),
            elapsed_s=round(elapsed, 2),
        )
        return PhaseResult.success(self.name, new_state, elapsed)


class DebugPhase(Phase):
    """Fase 8: Loop de depuração com budget de iterações."""

    name = "debug"

    MAX_ITERATIONS: int = 3

    def __init__(self, pool: AgentPool, evaluator: CandidateEvaluator) -> None:
        self._pool = pool
        self._evaluator = evaluator

    @_timed_phase
    def run(self, state: PipelineState) -> PipelineState:
        if state.is_successful or not state.best:
            return state

        governance.validate_call("debugger", {"code": state.best_code, "error": ""})
        debugger = self._pool.fresh_debugger()
        critic = self._pool.fresh_critic()
        reflexion_agent = self._pool.fresh_reflexion()

        current_best = state.best
        reflections = list(state.reflections)
        iterations = 0

        while not self._policy_check(current_best) and iterations < self.MAX_ITERATIONS:
            iterations += 1
            error_msg = current_best.error_output or f"Score insuficiente: {current_best.score}"

            fixed_code = debugger.corrigir_codigo(current_best.code, error_msg, state.task)
            if not fixed_code or fixed_code == current_best.code:
                log.info("Debug sem progresso, interrompendo", iteration=iterations)
                break

            iter_name = f"debug_{iterations}"
            result = self._evaluator.evaluate(
                profile_name=iter_name,
                code=fixed_code,
                task=state.task,
                subtask_desc=state.task,
                critiques=[],
            )

            check = critic.avaliar_com_scores(state.task, fixed_code)
            if check.get("approved", False):
                result = CandidateResult(
                    agent_name=iter_name,
                    code=fixed_code,
                    score=100.0,
                    tests_passed=result.tests_passed,
                    tests_total=result.tests_total,
                    exec_seconds=result.exec_seconds,
                    error_output="",
                )

            reflection = reflexion_agent.analisar_resultado(
                fixed_code,
                {"sucesso": result.score >= ScoringPolicy().success_threshold},
                state.task,
            )
            reflections.append({
                "iteration": iterations,
                "error": error_msg[:200],
                "reflection": reflection[:500],
                "score": result.score,
            })

            bus.publish(
                EventType.DEBUG_ITERATION,
                {
                    "task": state.task[:100],
                    "iteration": iterations,
                    "score": result.score,
                    "success": result.score >= ScoringPolicy().success_threshold,
                },
                source="DebugPhase",
            )

            if result.score > current_best.score:
                current_best = result

            if self._policy_check(current_best):
                break

        log.info("Debug loop concluído", iterations=iterations, score=current_best.score)
        return state.evolve(
            best=current_best,
            reflections=reflections,
            debug_iterations=iterations,
        )

    @staticmethod
    def _policy_check(result: CandidateResult) -> bool:
        return result.score >= ScoringPolicy().success_threshold


class ReflexionPhase(Phase):
    """Fase 9: Reflexão final sobre o resultado do pipeline."""

    name = "reflexion"

    def __init__(self, pool: AgentPool) -> None:
        self._pool = pool

    @_timed_phase
    def run(self, state: PipelineState) -> PipelineState:
        agent = self._pool.fresh_reflexion()
        reflection = agent.analisar_resultado(
            state.best_code,
            {"sucesso": state.is_successful},
            state.task,
        )
        reflections = [*state.reflections, {"iteration": "final", "reflection": reflection[:500]}]
        bus.publish(
            EventType.REFLECTION_COMPLETED,
            {"task": state.task[:100], "analysis": reflection[:200]},
            source="ReflexionPhase",
        )
        return state.evolve(reflections=reflections)


class MemoryPhase(Phase):
    """Fase 10: Persiste solução bem-sucedida na memória de longo prazo."""

    name = "memory"

    @_timed_phase
    def run(self, state: PipelineState) -> PipelineState:
        if not state.best_code:
            log.warning("Nada a salvar na memória, código vazio")
            return state

        complexity = state.plan.get("complexidade", "")
        store_success(state.task, state.best_code, {"complexidade": complexity})
        bus.publish(
            EventType.MEMORY_SAVED,
            {"memory_type": "success", "task": state.task[:100], "codigo_length": len(state.best_code)},
            source="MemoryPhase",
        )
        return state


# ─────────────────────────────────────────────────────────────────────────────
# PhaseRunner: executa fases com CircuitBreaker e abort-on-critical
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PhaseRunner:
    """
    Executa uma sequência de fases com:
    - CircuitBreaker por fase
    - Abort em fases marcadas como críticas
    - Log estruturado de cada transição
    """

    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    critical_phases: frozenset[str] = field(
        default_factory=lambda: frozenset({"planner"})
    )

    def run_all(
        self,
        phases: Sequence[Phase],
        initial_state: PipelineState,
    ) -> PipelineState:
        state = initial_state
        for phase in phases:
            try:
                with self.breaker.guard(phase.name):
                    result = phase.run(state)
            except RuntimeError as exc:
                # Circuito aberto
                log.error("CircuitBreaker impediu execução de fase", phase=phase.name, error=str(exc))
                if phase.name in self.critical_phases:
                    log.error("Fase crítica bloqueada, abortando pipeline", phase=phase.name)
                    return state
                continue

            if not result.ok:
                log.warning("Fase retornou falha", phase=phase.name, error=result.error)
                if phase.name in self.critical_phases:
                    log.error("Fase crítica falhou, abortando pipeline", phase=phase.name)
                    return state
                # Fases não-críticas: continua com estado anterior
            else:
                state = result.state

        return state


# ─────────────────────────────────────────────────────────────────────────────
# Orquestrador principal
# ─────────────────────────────────────────────────────────────────────────────

class PipelineOrchestrator:
    """
    Orquestrador principal do pipeline multi-agente.

    Responsabilidade: compor e executar fases para cada subtarefa do plano.
    NÃO contém lógica de negócio — delega para fases especializadas.

    Injeção de dependência total: todos os colaboradores são passados via __init__.
    """

    def __init__(
        self,
        workdir: Optional[str] = None,
        proxy: Optional[CognitiveProxy] = None,
        pool: Optional[AgentPool] = None,
        registry: Optional[SuccessRegistry] = None,
        policy: Optional[ScoringPolicy] = None,
        breaker: Optional[CircuitBreaker] = None,
        profiles: Tuple[AgentProfile, ...] = AGENT_PROFILES,
    ) -> None:
        self._workdir = workdir
        self._proxy = proxy or CognitiveProxy(web_enabled=True, retry_enabled=True)
        self._pool = pool or AgentPool()
        self._registry = registry or SuccessRegistry()
        self._policy = policy or ScoringPolicy()
        self._breaker = breaker or CircuitBreaker()
        self._profiles = profiles

        tester = TesterAgent(workdir=workdir)
        self._evaluator = CandidateEvaluator(tester=tester, policy=self._policy)
        self._runner = PhaseRunner(breaker=self._breaker)

    # ─── Pipeline público ───────────────────────────────────────────────────

    def resolve(self, task: Union[str, Task], max_iters: int = 3) -> str:
        t0 = time.perf_counter()
        task_str = str(task)
        governance.validate_call("multi_agent", {"task": task_str})
        log.info("Pipeline iniciado", task=task_str[:80], proxy_web=self._proxy.webbrain is not None)

        bus.publish(EventType.TASK_CREATED, {"task": task_str[:200]}, source="PipelineOrchestrator.resolve")

        # Estado inicial imutável
        initial = PipelineState(task=task_str)

        # Fase de contexto (uma vez por pipeline)
        context_result = ContextPhase(proxy=self._proxy).run(initial)
        state = context_result.state if context_result.ok else initial

        # Fase de planejamento
        plan_result = PlannerPhase(pool=self._pool, registry=self._registry).run(state)
        if not plan_result.ok or not plan_result.state.plan.get("subtarefas"):
            log.error("Pipeline abortado: plano inválido")
            return "[SANITY BARRIER] Pipeline interrompido: plano inválido."
        state = plan_result.state

        subtasks = state.plan.get("subtarefas", [])
        accumulated_code = ""

        for idx, subtask in enumerate(subtasks, 1):
            subtask_desc = subtask.get("descricao", "")
            log.info("Iniciando subtarefa", idx=idx, total=len(subtasks), desc=subtask_desc[:60])

            subtask_task = self._build_subtask_prompt(
                task_str=task_str,
                plan=state.plan,
                subtask=subtask,
                accumulated_code=accumulated_code,
                knowledge=state.knowledge,
            )
            subtask_state = PipelineState(task=subtask_task, knowledge=state.knowledge)

            subtask_state = self._runner.run_all(
                phases=self._build_subtask_phases(subtask_desc),
                initial_state=subtask_state,
            )

            if subtask_state.best_code:
                accumulated_code = subtask_state.best_code
            else:
                log.warning("Subtarefa sem resultado", idx=idx)
                bus.publish(
                    EventType.EXECUTION_FAILED,
                    {"subtask": subtask_desc, "error": "Nenhuma solução gerada", "task": task_str[:100]},
                    source="PipelineOrchestrator.resolve",
                )

        # Fases finais (reflexão + memória) no estado global
        final_state = state.evolve(
            best=PipelineState(task=task_str).evolve(
                best=_make_best_result(accumulated_code)
            ).best if accumulated_code else None
        )
        self._runner.run_all(
            phases=[ReflexionPhase(self._pool), MemoryPhase()],
            initial_state=final_state,
        )

        elapsed = time.perf_counter() - t0
        log.info(
            "Pipeline concluído",
            subtasks=len(subtasks),
            code_chars=len(accumulated_code),
            elapsed_s=round(elapsed, 2),
        )
        return accumulated_code

    # ─── Helpers privados ───────────────────────────────────────────────────

    def _build_subtask_phases(self, subtask_desc: str) -> List[Phase]:
        """Constrói sequência de fases para uma subtarefa."""
        return [
            MultiCoderPhase(pool=self._pool, profiles=self._profiles),
            CriticPhase(pool=self._pool),
            _EvalPhaseWithDesc(evaluator=self._evaluator, policy=self._policy, desc=subtask_desc),
            DebugPhase(pool=self._pool, evaluator=self._evaluator),
        ]

    @staticmethod
    def _build_subtask_prompt(
        task_str: str,
        plan: Dict[str, Any],
        subtask: Dict[str, Any],
        accumulated_code: str,
        knowledge: str,
    ) -> str:
        """Constrói o prompt completo para uma subtarefa."""
        planner = PlannerAgent()
        context = planner.injetar_plano_no_prompt(plan, subtask["id"])
        parts = [task_str, "", context]
        if accumulated_code:
            parts += [
                "\n[CÓDIGO ETAPAS ANTERIORES]:",
                f"{accumulated_code[:300]}...",
                "Construa incrementalmente.",
            ]
        return "\n".join(parts)

    # ─── API de compatibilidade (wrappers diretos) ─────────────────────────

    def critique(self, code: str, task: Union[str, Task]) -> str:
        governance.validate_call("critic", {"task": str(task), "output": code})
        return self._pool.fresh_critic().avaliar_solucao(str(task), code)

    def debug(self, code: str, error: str, task: Union[str, Task]) -> str:
        governance.validate_call("debugger", {"code": code, "error": error})
        return self._pool.fresh_debugger().corrigir_codigo(code, error, str(task))

    def reflect(self, code: str, result: dict, task: Union[str, Task]) -> str:
        return self._pool.fresh_reflexion().analisar_resultado(code, result, str(task))


class _EvalPhaseWithDesc(EvalPhase):
    """Variante de EvalPhase que injeta a descrição da subtarefa."""

    def __init__(self, evaluator: CandidateEvaluator, policy: ScoringPolicy, desc: str) -> None:
        super().__init__(evaluator=evaluator, policy=policy)
        self._desc = desc

    def run(self, state: PipelineState) -> PhaseResult:
        # Injeta descrição via evolve temporário
        patched = state.evolve(task=f"{state.task}\n\n[DESC]: {self._desc}")
        result = super().run(patched)
        # Restaura task original no estado retornado
        if result.ok:
            return PhaseResult.success(result.phase_name, result.state.evolve(task=state.task), result.elapsed)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Utilitários puros (sem estado, sem side-effects)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_test_output(output: str) -> Tuple[int, int]:
    """Extrai (total_tests, failures) do output de unittest."""
    total = 0
    failures = 0
    m = re.search(r"Ran\s+(\d+)\s+tests", output)
    if m:
        total = int(m.group(1))
    m = re.search(r"failures=(\d+)", output)
    if m:
        failures += int(m.group(1))
    m = re.search(r"errors=(\d+)", output)
    if m:
        failures += int(m.group(1))
    return total, failures


def _fmt_context_items(items: list) -> str:
    """Formata itens de contexto heterogêneos em texto legível."""
    if not items:
        return "(vazio)"
    lines: List[str] = []
    for item in items[:3]:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            _, data = item
            text = data.get("text", str(data)) if isinstance(data, dict) else str(data)
        elif isinstance(item, dict):
            text = item.get("content") or item.get("text") or str(item)
        else:
            text = str(item)
        lines.append(str(text)[:150])
    return "\n".join(lines) or "(vazio)"


def _make_best_result(code: str) -> CandidateResult:
    """Cria um CandidateResult sintético a partir de código acumulado."""
    return CandidateResult(
        agent_name="accumulated",
        code=code,
        score=ScoringPolicy().success_threshold,
        tests_passed=0,
        tests_total=0,
        exec_seconds=0.0,
    )


def extract_pure_code(text: str) -> str:
    """Remove markdown fences de um bloco de código."""
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"^```(?:python|py)?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```$", "", text)
    return text.strip()


def is_valid_python(code: str) -> bool:
    return ValidationEngine().validate(code).valid


# ─────────────────────────────────────────────────────────────────────────────
# Wrappers de compatibilidade (API pública preservada)
# ─────────────────────────────────────────────────────────────────────────────

def _default_orchestrator() -> PipelineOrchestrator:
    """Factory para wrappers: cria orquestrador com DI padrão."""
    return PipelineOrchestrator(proxy=CognitiveProxy(web_enabled=True, retry_enabled=True))


def resolver(task: Union[str, Task], max_iters: int = 3) -> str:
    return _default_orchestrator().resolve(task, max_iters)


def gerar_solucoes(task: Any, conhecimento: Optional[Dict] = None) -> Dict[str, str]:
    log.info("gerar_solucoes chamado", task=str(task)[:80])
    errors = query_relevant_errors(str(task), limit=2)
    error_ctx = format_errors_for_prompt(errors)
    context = conhecimento.get("codigo", "") if conhecimento else ""
    pool = AgentPool()
    solutions: Dict[str, str] = {}
    for profile in AGENT_PROFILES:
        try:
            code = pool.get_coder(profile).gerar_codigo(
                task, contexto=context, erros_contexto=error_ctx
            )
            if code:
                solutions[profile.name] = code
        except Exception as exc:
            log.error("gerar_solucoes falhou para perfil", agent=profile.name, error=str(exc))
    return solutions


def criticar(codigo: str, task: Any) -> str:
    return _default_orchestrator().critique(codigo, task)


def debuggar(codigo: str, erro: str, task: Any) -> str:
    return _default_orchestrator().debug(codigo, erro, task)


def processar_testar_solucoes(
    solucoes: Dict[str, str], task: Any
) -> List[Tuple[float, str, str, str]]:
    log.info("processar_testar_solucoes chamado", solutions=len(solucoes))
    tester = TesterAgent()
    evaluator = CandidateEvaluator(tester=tester)
    results: List[CandidateResult] = []
    for name, code in solucoes.items():
        r = evaluator.evaluate(name, code, str(task), str(task), [])
        results.append(r)
    results.sort(key=lambda r: r.score, reverse=True)
    return [(r.score, r.agent_name, r.code, r.error_output) for r in results]


def buscar_solucao_anterior(task_id: str) -> Optional[Dict[str, Any]]:
    return SuccessRegistry().find_similar(str(task_id))


# ─────────────────────────────────────────────────────────────────────────────
# Alias de retrocompatibilidade (nomes antigos → novo)
# ─────────────────────────────────────────────────────────────────────────────

class Multi_Agent(PipelineOrchestrator):
    """
    Alias de retrocompatibilidade.
    Novos consumidores devem usar PipelineOrchestrator diretamente.
    """

    def resolver(self, task: Union[str, Task], max_iters: int = 3) -> str:
        return self.resolve(task, max_iters)
