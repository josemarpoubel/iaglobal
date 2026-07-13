# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# ✅ `iaglobal/agents/reflexion_agent.py`

"""
iaglobal/agents/reflexion_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Agente de reflexão e auto-melhoria — Geração 8.

Responsabilidade única: analisar execuções, classificar problemas e propor
melhorias de código guiadas por um pipeline de reflexão estruturado.

Arquitetura interna:
  ┌──────────────────────────────────────────────────────────────┐
  │  ReflexionAgent                                              │
  │    ├─ ReflexionConfig      (parâmetros imutáveis)           │
  │    ├─ PromptTemplates      (prompts versionáveis/testáveis) │
  │    ├─ ReflexionResult      (resultado rico e tipado)        │
  │    ├─ ImprovementResult    (melhoria com diff semântico)    │
  │    └─ LLMGateway           (abstração sobre provider_router)│
  └──────────────────────────────────────────────────────────────┘

Princípios:
  • Prompts desacoplados da lógica — PromptTemplates é testável isoladamente
  • Resultados ricos — ReflexionResult/ImprovementResult em vez de str pura
  • Fallback explícito — ReflexionResult.is_fallback distingue resposta real
    de degradação graceful
  • Observabilidade — StructuredLogger com campos uniformes em todo log
  • DI completa — LLMGateway injetável, facilitando testes com mocks
  • Retrocompatibilidade — assinaturas públicas preservadas, retornos str
    quando necessário para contratos existentes
"""

from __future__ import annotations

import time
import textwrap
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Protocol, Union

from iaglobal.models.task import Task
from iaglobal.agents.agent_base import AgentBase
from iaglobal.reflection.reflexion_engine import extract_code_block
from iaglobal.utils.logger import logger as _base_logger
from iaglobal.agents.critic_agent import _get_critic

# Mantém import para shadow-mode (caminho antigo ainda funcional)
from iaglobal.providers.provider_router import route_generate

# ─────────────────────────────────────────────────────────────────────────────
# Logging estruturado (alinhado com a convenção do multi_agent evoluído)
# ─────────────────────────────────────────────────────────────────────────────


class _StructuredLogger:
    """Wrapper leve que força campos contextuais em todo log do agente."""

    def __init__(self, base: logging.Logger, ctx: dict | None = None) -> None:
        self._log = base
        self._ctx: dict = ctx or {}

    def bind(self, **kw: object) -> "_StructuredLogger":
        return _StructuredLogger(self._log, {**self._ctx, **kw})

    def _fmt(self, msg: str, extra: dict) -> str:
        merged = {**self._ctx, **extra}
        pairs = " ".join(f"{k}={v!r}" for k, v in merged.items())
        return f"{msg} | {pairs}" if pairs else msg

    def info(self, msg: str, **kw: object) -> None:
        self._log.info(self._fmt(msg, kw))

    def warning(self, msg: str, **kw: object) -> None:
        self._log.warning(self._fmt(msg, kw))

    def error(self, msg: str, **kw: object) -> None:
        self._log.error(self._fmt(msg, kw))

    def debug(self, msg: str, **kw: object) -> None:
        self._log.debug(self._fmt(msg, kw))


log = _StructuredLogger(_base_logger, {"agent": "ReflexionAgent"})


# ─────────────────────────────────────────────────────────────────────────────
# Enums de domínio
# ─────────────────────────────────────────────────────────────────────────────


class ProblemCategory(str, Enum):
    """Categorias de problema identificáveis na reflexão."""

    LOGIC_ERROR = "logic_error"
    RUNTIME_ERROR = "runtime_error"
    PERFORMANCE = "performance"
    CODE_QUALITY = "code_quality"
    MISSING_HANDLING = "missing_handling"
    UNKNOWN = "unknown"


class ReflexionStatus(str, Enum):
    """Status de uma operação de reflexão."""

    SUCCESS = "success"
    FALLBACK = "fallback"  # resposta de degradação graceful
    ERROR = "error"


# ─────────────────────────────────────────────────────────────────────────────
# Tipos de resultado ricos
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SandboxContext:
    """
    Contexto de execução em sandbox — representa o estado observado.
    Substitui o dict genérico `resultado_sandbox` do original.
    """

    success: bool
    output: str = ""
    error: str = ""
    execution_ms: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "SandboxContext":
        return cls(
            success=bool(d.get("sucesso", False)),
            output=str(d.get("output", "")),
            error=str(d.get("erro", "")),
            execution_ms=float(d.get("execution_ms", 0.0)),
        )

    @property
    def status_label(self) -> str:
        return "Sucesso" if self.success else "Falha"


@dataclass(frozen=True)
class ReflexionResult:
    """
    Resultado rico de uma análise de reflexão.

    O chamador pode inspecionar `status`, `categories` e `raw_analysis`
    sem depender de parsing de string.
    """

    raw_analysis: str
    status: ReflexionStatus
    categories: List[ProblemCategory] = field(default_factory=list)
    elapsed_ms: float = 0.0

    @property
    def is_fallback(self) -> bool:
        return self.status in (ReflexionStatus.FALLBACK, ReflexionStatus.ERROR)

    @property
    def as_str(self) -> str:
        """Retrocompatibilidade: expõe a análise como string."""
        return self.raw_analysis

    def __str__(self) -> str:
        return self.raw_analysis


@dataclass(frozen=True)
class ImprovementResult:
    """
    Resultado rico de uma sugestão de melhoria.

    `improved_code` é o código melhorado (ou o original em fallback).
    `changed` indica se houve diferença efetiva.
    """

    improved_code: str
    original_code: str
    status: ReflexionStatus
    elapsed_ms: float = 0.0

    @property
    def is_fallback(self) -> bool:
        return self.status in (ReflexionStatus.FALLBACK, ReflexionStatus.ERROR)

    @property
    def as_str(self) -> str:
        return self.improved_code

    def __str__(self) -> str:
        return self.improved_code


# ─────────────────────────────────────────────────────────────────────────────
# Configuração imutável do agente
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ReflexionConfig:
    """
    Parâmetros de operação do ReflexionAgent.

    Centraliza todas as constantes configuráveis, eliminando magic values
    espalhados pelo código.
    """

    max_reflexion_iterations: int = 5
    task_type_reflection: str = "reflection"
    task_type_improvement: str = "improvement"
    max_prompt_code_chars: int = 8_000  # trunca código muito longo nos prompts
    max_prompt_output_chars: int = 2_000  # trunca output de sandbox nos prompts
    max_prompt_analysis_chars: int = 4_000

    def truncate_code(self, code: str) -> str:
        if len(code) <= self.max_prompt_code_chars:
            return code
        half = self.max_prompt_code_chars // 2
        return f"{code[:half]}\n... [TRUNCADO] ...\n{code[-half:]}"

    def truncate_output(self, text: str) -> str:
        return text[: self.max_prompt_output_chars] if text else "(vazio)"

    def truncate_analysis(self, text: str) -> str:
        return text[: self.max_prompt_analysis_chars] if text else "(vazio)"


# ─────────────────────────────────────────────────────────────────────────────
# Templates de prompt — desacoplados e versionáveis
# ─────────────────────────────────────────────────────────────────────────────


class PromptTemplates:
    """
    Repositório de templates de prompt do ReflexionAgent.

    Separar prompts da lógica de negócio permite:
    - Testar a qualidade dos prompts isoladamente
    - Versionar prompts sem tocar na lógica
    - Substituir templates por prompt files em disco ou banco
    """

    @staticmethod
    def analysis(
        task: str,
        code: str,
        sandbox: SandboxContext,
        config: ReflexionConfig,
    ) -> str:
        return textwrap.dedent(f"""
            Você é um engenheiro de software sênior especializado em análise de qualidade.
            Avalie criticamente o código e sua execução em sandbox.

            ── TAREFA ────────────────────────────────────────────────────────
            {task}

            ── CÓDIGO GERADO ─────────────────────────────────────────────────
            {config.truncate_code(code)}

            ── RESULTADO DA EXECUÇÃO ─────────────────────────────────────────
            Status : {sandbox.status_label}
            Output : {config.truncate_output(sandbox.output)}
            Erro   : {config.truncate_output(sandbox.error) if sandbox.error else "nenhum"}

            ── INSTRUÇÃO ─────────────────────────────────────────────────────
            Forneça uma análise objetiva estruturada com:
            1. CATEGORIAS: classifique os problemas encontrados em uma ou mais das categorias:
               logic_error | runtime_error | performance | code_quality | missing_handling
               Se não houver problemas, escreva: CATEGORIAS: none
            2. CAUSAS: causas raiz do erro ou degradação (se houver)
            3. PROBLEMAS DE LÓGICA: desvios em relação à tarefa esperada
            4. MELHORIAS CONCRETAS: sugestões acionáveis e priorizadas

            Seja direto, técnico e objetivo. Não repita o código.
        """).strip()

    @staticmethod
    def improvement(
        task: str,
        analysis: str,
        code: str,
        config: ReflexionConfig,
    ) -> str:
        return textwrap.dedent(f"""
            Você é um arquiteto de software especialista em refatoração.
            Com base na análise abaixo, reescreva o código corrigindo problemas
            e melhorando qualidade sem alterar a lógica essencial.

            ── TAREFA ────────────────────────────────────────────────────────
            {task}

            ── ANÁLISE ───────────────────────────────────────────────────────
            {config.truncate_analysis(analysis)}

            ── CÓDIGO ATUAL ──────────────────────────────────────────────────
            {config.truncate_code(code)}

            ── REGRAS ABSOLUTAS ──────────────────────────────────────────────
            • Retorne APENAS código Python válido
            • Não adicione explicações, comentários externos ou markdown
            • Preserve a lógica original; corrija apenas o necessário
            • Corrija todos os problemas identificados na análise acima
        """).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Gateway LLM — abstração sobre provider_router
# ─────────────────────────────────────────────────────────────────────────────


class LLMGatewayProtocol(Protocol):
    """
    Contrato do gateway LLM.
    Permite substituição por mock em testes sem tocar no agente.
    """

    async def generate(
        self, task: str, prompt: str, task_type: str
    ) -> Optional[str]: ...


@dataclass
class ProviderLLMGateway:
    """
    Implementação concreta do gateway usando provider_router.
    Isola completamente a dependência do provider do agente.
    """

    async def generate(self, task: str, prompt: str, task_type: str) -> Optional[str]:
        import os

        if os.environ.get("ARBITER_MODE", "enforce") == "shadow":
            # Shadow: decide via crítico, executa via caminho antigo
            await _get_critic().arbitrar_geracao(
                node_id="reflexion",
                prompt=prompt,
                task_type=task_type,
            )
            response = await route_generate("", prompt, task_type=task_type)
            return str(response) if response else None
        response = await _get_critic().arbitrar_geracao(
            node_id="reflexion",
            prompt=prompt,
            task_type=task_type,
        )
        return response or None


# ─────────────────────────────────────────────────────────────────────────────
# Parser de categorias
# ─────────────────────────────────────────────────────────────────────────────


def _extract_categories(analysis: str) -> List[ProblemCategory]:
    """
    Extrai categorias estruturadas da análise textual do LLM.
    Busca a linha 'CATEGORIAS: ...' e mapeia tokens para o enum.
    """
    mapping = {c.value: c for c in ProblemCategory}
    for line in analysis.splitlines():
        if "CATEGORIAS:" in line.upper():
            tokens = line.split(":", 1)[-1].strip().lower().split()
            found = [mapping[t] for t in tokens if t in mapping]
            return found if found else [ProblemCategory.UNKNOWN]
    return []


# ─────────────────────────────────────────────────────────────────────────────
# ReflexionAgent
# ─────────────────────────────────────────────────────────────────────────────


class ReflexionAgent(AgentBase):
    """
    Agente de reflexão e auto-melhoria — Geração 8.

    Responsabilidades:
    ─ Analisar código + resultado de sandbox e produzir ReflexionResult rico
    ─ Sugerir código melhorado com base na análise (ImprovementResult)
    ─ Executar ciclo de auto-reflexão via reflexion_loop

    NÃO é responsabilidade deste agente:
    ─ Executar código (sandbox)
    ─ Decidir quando usar reflexão (orquestrador)
    ─ Persistir resultados (MemoryPhase)

    Injeção de Dependência:
        gateway  — implementação do LLM (default: ProviderLLMGateway)
        config   — parâmetros de operação (default: ReflexionConfig())
        templates— templates de prompt (default: PromptTemplates)
    """

    def __init__(
        self,
        gateway: Optional[LLMGatewayProtocol] = None,
        config: Optional[ReflexionConfig] = None,
        templates: Optional[type[PromptTemplates]] = None,
    ) -> None:
        self._gateway: LLMGatewayProtocol = gateway or ProviderLLMGateway()
        self._config = config or ReflexionConfig()
        self._templates = templates or PromptTemplates
        self._log = log.bind(config=type(self._config).__name__)

    # ─── Análise de resultado ─────────────────────────────────────────────

    async def analisar_resultado(
        self,
        codigo: str,
        resultado_sandbox: dict,
        task: Union[str, Task],
    ) -> str:
        """
        Analisa código + resultado de sandbox.

        Retrocompatibilidade: retorna str.
        Use `analisar_resultado_rich` para o resultado tipado completo.
        """
        result = await self.analisar_resultado_rich(codigo, resultado_sandbox, task)
        return result.as_str

    async def analisar_resultado_rich(
        self,
        codigo: str,
        resultado_sandbox: dict,
        task: Union[str, Task],
    ) -> ReflexionResult:
        """
        Analisa código + resultado de sandbox — versão rica e tipada.

        Args:
            codigo: código Python gerado pelo pipeline
            resultado_sandbox: dict com chaves sucesso/output/erro/execution_ms
            task: descrição da tarefa (str ou Task)

        Returns:
            ReflexionResult com análise, categorias de problema e status
        """
        task_str = str(task)
        sandbox = SandboxContext.from_dict(resultado_sandbox)
        self._log.info(
            "Analisando resultado",
            sandbox_status=sandbox.status_label,
            code_chars=len(codigo),
        )

        prompt = self._templates.analysis(task_str, codigo, sandbox, self._config)

        t0 = time.perf_counter()
        try:
            raw = await self._gateway.generate(
                task=task_str,
                prompt=prompt,
                task_type=self._config.task_type_reflection,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000

            if not raw:
                self._log.warning("Provider retornou resposta vazia, usando fallback")
                return self._fallback_analysis(elapsed_ms)

            categories = _extract_categories(raw)
            self._log.info(
                "Análise concluída",
                elapsed_ms=round(elapsed_ms, 1),
                categories=[c.value for c in categories],
            )
            return ReflexionResult(
                raw_analysis=raw,
                status=ReflexionStatus.SUCCESS,
                categories=categories,
                elapsed_ms=elapsed_ms,
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self._log.warning(
                "Falha na análise", error=str(exc), elapsed_ms=round(elapsed_ms, 1)
            )
            return self._fallback_analysis(elapsed_ms)

    # ─── Sugestão de melhoria ─────────────────────────────────────────────

    async def sugerir_melhoria_rich(
        self,
        codigo: str,
        analise: str,
        task: Union[str, Task],
    ) -> ImprovementResult:
        """
        Sugere código melhorado — versão rica e tipada.

        Args:
            codigo: código Python atual
            analise: análise de qualidade (texto ou ReflexionResult.as_str)
            task: descrição da tarefa

        Returns:
            ImprovementResult com código melhorado, flag de mudança e status
        """
        task_str = str(task)
        self._log.info(
            "Gerando melhoria", code_chars=len(codigo), analysis_chars=len(analise)
        )

        prompt = self._templates.improvement(task_str, analise, codigo, self._config)

        t0 = time.perf_counter()
        try:
            raw = await self._gateway.generate(
                task=task_str,
                prompt=prompt,
                task_type=self._config.task_type_improvement,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000

            if not raw:
                self._log.warning("Provider retornou resposta vazia, mantendo original")
                return self._fallback_improvement(codigo, elapsed_ms)

            improved = extract_code_block(raw)
            if not improved.strip():
                self._log.warning("Código extraído vazio, mantendo original")
                return self._fallback_improvement(codigo, elapsed_ms)

            self._log.info(
                "Melhoria gerada",
                elapsed_ms=round(elapsed_ms, 1),
                original_chars=len(codigo),
                improved_chars=len(improved),
                changed=improved.strip() != codigo.strip(),
            )
            return ImprovementResult(
                improved_code=improved,
                original_code=codigo,
                status=ReflexionStatus.SUCCESS,
                elapsed_ms=elapsed_ms,
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self._log.warning(
                "Falha ao gerar melhoria",
                error=str(exc),
                elapsed_ms=round(elapsed_ms, 1),
            )
            return self._fallback_improvement(codigo, elapsed_ms)

    # ─── Pipeline completo: análise → melhoria ────────────────────────────

    # ─── Fallbacks internos ───────────────────────────────────────────────

    @staticmethod
    def _fallback_analysis(elapsed_ms: float) -> ReflexionResult:
        return ReflexionResult(
            raw_analysis="Análise não disponível (provider indisponível ou resposta vazia).",
            status=ReflexionStatus.FALLBACK,
            categories=[],
            elapsed_ms=elapsed_ms,
        )

    @staticmethod
    def _fallback_improvement(original: str, elapsed_ms: float) -> ImprovementResult:
        return ImprovementResult(
            improved_code=original,
            original_code=original,
            status=ReflexionStatus.FALLBACK,
            elapsed_ms=elapsed_ms,
        )
