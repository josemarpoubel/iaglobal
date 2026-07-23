# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
RepairEngine — Orquestrador de reparos baseado em capacidades.

Arquitetura:
  ErrorDescriptor
        ↓
  RepairEngine (seleciona estratégia por capacidade)
        ↓
  RepairStrategy (declara handles = {...})
        ↓
  RepairReport (com attempt, chain, telemetry)

Uso:
  engine = RepairEngine()
  report = engine.repair(code, error, context)

  if report.success:
      return report.after_code
"""

from __future__ import annotations

import asyncio
import time
import logging
from typing import Optional, Dict, Any, List, Type
from dataclasses import dataclass, field

from iaglobal.diagnostics.error_descriptor import (
    ErrorDescriptor,
    ErrorCategory,
    ErrorCause,
)
from iaglobal.diagnostics.error_classifier import error_classifier
from iaglobal.diagnostics.repair_strategies import (
    RepairStrategy,
    SyntaxRepairStrategy,
    JsonRecoveryStrategy,
    UnicodeRepairStrategy,
    ImportFallbackStrategy,
    GenericRetryStrategy,
)
from iaglobal.diagnostics.python_normalizer import normalize_before_repair


logger = logging.getLogger("iaglobal")


@dataclass
class RepairReport:
    """
    Relatório de reparo enriquecido.

    Atributos:
        success: Se reparo foi bem-sucedido
        before_code: Código original
        after_code: Código após reparo (None se falhou)
        descriptor: ErrorDescriptor completo
        strategy_used: Nome da estratégia usada
        attempt: Número da tentativa (1, 2, 3...)
        parent_report: Report anterior (se re-tentativa)
        repair_chain: Lista de reports anteriores (cadeia completa)
        execution_metrics: Métricas de execução
        diagnostics: Diagnósticos adicionais
    """

    success: bool
    before_code: str
    after_code: Optional[str]
    descriptor: ErrorDescriptor
    strategy_used: str
    attempt: int = 1
    parent_report: Optional["RepairReport"] = None
    repair_chain: List["RepairReport"] = field(default_factory=list)
    execution_metrics: Dict[str, Any] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def get_diagnostics(self) -> Dict[str, Any]:
        """Retorna diagnóstico completo para logging."""
        return {
            "success": self.success,
            "strategy": self.strategy_used,
            "attempt": self.attempt,
            "domain": self.descriptor.domain.value,
            "cause": self.descriptor.cause.value,
            "severity": self.descriptor.severity.value,
            "classifier_confidence": self.descriptor.classifier_confidence,
            "repair_confidence": self.descriptor.repair_confidence,
            "execution_time": self.execution_metrics.get("latency", 0.0),
            "chain_length": len(self.repair_chain),
        }

    def get_chain_summary(self) -> List[Dict[str, Any]]:
        """Retorna resumo da cadeia de reparos."""
        chain = []
        current = self

        while current:
            chain.append(
                {
                    "attempt": current.attempt,
                    "strategy": current.strategy_used,
                    "success": current.success,
                    "confidence": current.descriptor.repair_confidence,
                }
            )
            current = current.parent_report

        return list(reversed(chain))

    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        return (
            f"RepairReport({status} {self.strategy_used}, "
            f"attempt={self.attempt}, "
            f"domain={self.descriptor.domain.value})"
        )


class RepairEngine:
    """
    Engine de reparos baseada em capacidades.

    Estratégias se auto-registram declarando:
      handles = {ErrorCategory.SYNTAX, ErrorCategory.LEXICAL}

    O engine resolve automaticamente baseado no ErrorDescriptor.
    """

    def __init__(self):
        self._strategies: Dict[ErrorCategory, List[RepairStrategy]] = {}
        self._register_default_strategies()

    def _register_default_strategies(self):
        """Registra estratégias padrão."""
        strategies = [
            SyntaxRepairStrategy(),
            JsonRecoveryStrategy(),
            UnicodeRepairStrategy(),
            ImportFallbackStrategy(),
            GenericRetryStrategy(),
        ]

        for strategy in strategies:
            self.register_strategy(strategy)

    def register_strategy(self, strategy: RepairStrategy):
        """
        Registra estratégia por capacidade.

        Estratégia declara:
          handles = {ErrorCategory.SYNTAX, ErrorCategory.LEXICAL}
        """
        for category in strategy.handles:
            if category not in self._strategies:
                self._strategies[category] = []
            self._strategies[category].append(strategy)

        logger.debug(
            f"Strategy {strategy.name} registered for categories: "
            f"{[c.value for c in strategy.handles]}"
        )

    def _select_strategy(self, descriptor: ErrorDescriptor) -> Optional[RepairStrategy]:
        """
        Seleciona estratégia baseada em capacidade.

        Prioridade:
          1. Estratégia específica para domínio
          2. Primeira estratégia disponível
          3. Fallback genérico
        """
        # Tenta estratégias do domínio
        strategies = self._strategies.get(descriptor.domain, [])

        if strategies:
            # Retorna primeira estratégia (pode implementar lógica própria de prioridade)
            return strategies[0]

        # Fallback: tenta encontrar qualquer estratégia que aceite
        for category_strategies in self._strategies.values():
            if category_strategies:
                return category_strategies[0]

        return None

    async def repair(
        self,
        code: str,
        error: Any,
        context: Optional[Dict[str, Any]] = None,
        max_attempts: int = 3,
    ) -> RepairReport:
        """
        Executa reparo de código.

        Args:
            code: Código original
            error: Exceção ou erro
            context: Contexto (component, code, etc.)
            max_attempts: Máximo de tentativas

        Returns:
            RepairReport completo
        """
        context = context or {}

        # 1. Classifica erro
        descriptor = error_classifier.classify(error, context)

        logger.info(f"Classified error: {descriptor}")

        # 2. Verifica se é recuperável
        if not descriptor.can_attempt_repair():
            logger.warning(f"Error not recoverable: {descriptor}")
            return RepairReport(
                success=False,
                before_code=code,
                after_code=None,
                descriptor=descriptor,
                strategy_used="none",
                attempt=1,
                diagnostics={"reason": "not_recoverable"},
            )

        # 3. Seleciona estratégia
        strategy = self._select_strategy(descriptor)

        if not strategy:
            logger.warning(f"No strategy for domain: {descriptor.domain}")
            return RepairReport(
                success=False,
                before_code=code,
                after_code=None,
                descriptor=descriptor,
                strategy_used="none",
                attempt=1,
                diagnostics={"reason": "no_strategy"},
            )

        # 4. Executa reparo
        return await self._execute_repair(
            code=code,
            descriptor=descriptor,
            strategy=strategy,
            context=context,
            max_attempts=max_attempts,
        )

    async def _execute_repair(
        self,
        code: str,
        descriptor: ErrorDescriptor,
        strategy: RepairStrategy,
        context: Dict[str, Any],
        max_attempts: int,
        parent_report: Optional[RepairReport] = None,
    ) -> RepairReport:
        """Executa reparo com estratégia selecionada."""

        start_time = time.time()
        attempt = 1

        # Pipeline de normalização sintática (antes do reparo)
        # Isso reduz erros de indentação, imports, etc.
        normalized_code, syntax_valid, norm_result = normalize_before_repair(
            code, str(descriptor.error_message)
        )

        # Se normalização succeeded, usa código normalizado
        if syntax_valid:
            logger.debug(
                f"Código normalizado com sucesso. "
                f"Ruff format: {len(norm_result.ruff_format_errors)} errors, "
                f"Ruff check: {len(norm_result.ruff_check_errors)} warnings"
            )
            current_code = normalized_code
        else:
            # Normalização falhou, usa código original e deixa estratégia lidar
            logger.debug(
                f"Normalização falhou: {norm_result.syntax_error}. "
                f"Usando código original."
            )
            current_code = code

        repair_chain = parent_report.repair_chain.copy() if parent_report else []

        while attempt <= max_attempts:
            logger.info(
                f"Attempting repair (attempt={attempt}/{max_attempts}): "
                f"strategy={strategy.name}, domain={descriptor.domain.value}"
            )

            try:
                # Executa estratégia
                result = await strategy.execute(
                    code=current_code,
                    descriptor=descriptor,
                    context=context,
                )

                # Atualiza descriptor
                descriptor.add_repair_attempt(
                    strategy_name=strategy.name,
                    success=result.success,
                    confidence=result.confidence,
                )

                # Calcula métricas
                latency = time.time() - start_time
                execution_metrics = {
                    "success": result.success,
                    "latency": latency,
                    "cost": 0.0,  # Pode ser preenchido por estratégia
                    "model": result.model,
                    "attempt": attempt,
                }

                # Sucesso
                if result.success:
                    descriptor.repair_confidence = result.confidence

                    report = RepairReport(
                        success=True,
                        before_code=code,
                        after_code=result.after_code,
                        descriptor=descriptor,
                        strategy_used=strategy.name,
                        attempt=attempt,
                        parent_report=parent_report,
                        repair_chain=repair_chain,
                        execution_metrics=execution_metrics,
                        diagnostics={
                            "strategy_confidence": result.confidence,
                            "changes_made": result.changes_made,
                        },
                    )

                    logger.info(f"Repair successful: {report}")
                    return report

                # Falha: tenta próxima estratégia ou re-tenta
                if attempt < max_attempts:
                    # Tenta mesma estratégia novamente (pode haver variação)
                    current_code = result.after_code or current_code
                    attempt += 1
                    continue

                # Falhou todas as tentativas
                report = RepairReport(
                    success=False,
                    before_code=code,
                    after_code=None,
                    descriptor=descriptor,
                    strategy_used=strategy.name,
                    attempt=attempt,
                    parent_report=parent_report,
                    repair_chain=repair_chain,
                    execution_metrics=execution_metrics,
                    diagnostics={
                        "reason": "all_attempts_failed",
                        "total_attempts": attempt,
                    },
                )

                logger.warning(f"Repair failed after {attempt} attempts: {report}")
                return report

            except Exception as e:
                logger.exception(f"Strategy execution failed: {e}")

                if attempt < max_attempts:
                    attempt += 1
                    continue

                # Falha catastrófica
                return RepairReport(
                    success=False,
                    before_code=code,
                    after_code=None,
                    descriptor=descriptor,
                    strategy_used=strategy.name,
                    attempt=attempt,
                    parent_report=parent_report,
                    repair_chain=repair_chain,
                    execution_metrics={
                        "success": False,
                        "latency": time.time() - start_time,
                        "cost": 0.0,
                        "model": "unknown",
                    },
                    diagnostics={
                        "reason": "strategy_exception",
                        "exception": str(e),
                    },
                )

        # Should not reach here
        return RepairReport(
            success=False,
            before_code=code,
            after_code=None,
            descriptor=descriptor,
            strategy_used="unknown",
            attempt=max_attempts,
            diagnostics={"reason": "unexpected_failure"},
        )

    def get_capabilities(self) -> Dict[str, List[str]]:
        """Retorna capacidades do engine (categorias → estratégias)."""
        return {
            category.value: [s.name for s in strategies]
            for category, strategies in self._strategies.items()
        }


# Singleton global
repair_engine = RepairEngine()
