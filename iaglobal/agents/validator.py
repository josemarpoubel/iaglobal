# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/agents/validator.py

"""SemanticValidator — Validação semântica e estrutural de código para pipelines."""
from __future__ import annotations

import ast
import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from iaglobal.utils.logger import logger
from iaglobal.agents.agent_base import AgentBase

from iaglobal.agents.semantic_validator import RuleRegistry, ScoreAggregator, LanguageDetector

# --- 1. Contratos de Dados Rígidos (Essencial para Pipelines) ---
@dataclass
class RuleResult:
    rule_name: str
    passed: bool
    score: float
    message: str = ""
    category: str = "general"

@dataclass
class ValidationResult:
    valid: bool
    score: float
    language: str
    rule_results: List[RuleResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialização limpa para o próximo agente da pipeline."""
        return {
            "valid": self.valid,
            "score": self.score,
            "language": self.language,
            "errors": self.errors,
            "suggestions": self.suggestions,
            "execution_time_ms": self.execution_time_ms,
            "failed_rules": [r.rule_name for r in self.rule_results if not r.passed],
        }

# --- 2. Agente Refatorado ---
class SemanticValidatorAgent(AgentBase):
    def __init__(self, pass_threshold: float = 80.0, registry: Optional[RuleRegistry] = None, timeout: float = 60.0):
        super().__init__(agent_name="semanticvalidator")
        self.pass_threshold = pass_threshold
        self.registry = registry or RuleRegistry.default()
        self.timeout = timeout

    async def validate_async(self, code: str, task: str) -> ValidationResult:
        start_time = time.perf_counter()

        # 1. Fail-fast para código vazio (Economiza processamento)
        if not code or not code.strip():
            return ValidationResult(
                valid=False, score=0.0, language="unknown",
                errors=["Código vazio ou nulo fornecido para validação."]
            )

        try:
            # 2. Detectar linguagem de forma segura (Não bloqueia o event loop)
            language = await self._safe_detect_language(code)
            
            # 3. Avaliar regras em paralelo, protegendo o event loop de operações CPU-bound
            tasks = [
                self._evaluate_rule_safe(rule, code, task, language) 
                for rule in self.registry.rules
            ]
            
            # Aplica timeout global na validação
            results = await asyncio.wait_for(
                asyncio.gather(*tasks), 
                timeout=self.timeout
            )
            
            # Filtra regras que falharam internamente (retornaram None)
            valid_results = [r for r in results if r is not None]
            
            # 4. Agregar resultados
            score, by_cat, errors, suggestions = ScoreAggregator.aggregate(valid_results)
            
            execution_time = (time.perf_counter() - start_time) * 1000
            
            logger.info(
                "[VALIDATOR] score=%.2f valid=%s lang=%s time=%.2fms errors=%d",
                score, score >= self.pass_threshold, language, execution_time, len(errors)
            )

            return ValidationResult(
                valid=score >= self.pass_threshold,
                score=score,
                rule_results=valid_results,
                errors=errors,
                suggestions=suggestions,
                language=language,
                execution_time_ms=execution_time
            )

        except asyncio.TimeoutError:
            logger.error("[VALIDATOR] Timeout de %ss atingido na validação.", self.timeout)
            return ValidationResult(
                valid=False, score=0.0, language="unknown",
                errors=[f"Validação excedeu o timeout de {self.timeout}s."]
            )
        except Exception as e:
            logger.exception("[VALIDATOR] Erro inesperado na validação.")
            return ValidationResult(
                valid=False, score=0.0, language="unknown",
                errors=[f"Erro interno no validador: {str(e)}"]
            )

    async def _safe_detect_language(self, code: str) -> str:
        """Wrapper para detecção de linguagem que não bloqueia o event loop."""
        try:
            # Se for assíncrono (ex: LLM), aguarda. Se for síncrono (ex: regex), roda em thread.
            if asyncio.iscoroutinefunction(LanguageDetector.detect):
                return await LanguageDetector.detect(code)
            else:
                return await asyncio.to_thread(LanguageDetector.detect, code)
        except Exception as e:
            logger.warning("[VALIDATOR] Falha ao detectar linguagem: %s. Assumindo 'python'.", e)
            return "python"

    async def _evaluate_rule_safe(self, rule, code: str, task: str, language: str) -> Optional[RuleResult]:
        """
        Avalia uma regra de forma resiliente.
        Regras que usam `ast` são CPU-bound e bloqueiam o event loop se rodadas direto no async.
        """
        rule_name = getattr(rule, 'name', rule.__class__.__name__)
        try:
            # Executa em thread para não bloquear o event loop (crucial para ast.parse)
            if asyncio.iscoroutinefunction(rule.evaluate):
                result = await rule.evaluate(code, task, language)
            else:
                result = await asyncio.to_thread(rule.evaluate, code, task, language)
                
            return result
            
        except SyntaxError as e:
            # ⚠️ O "Pulo do Gato": Erro de sintaxe no código do LLM é um RESULTADO da regra, não um crash do sistema!
            return RuleResult(
                rule_name=rule_name,
                passed=False,
                score=0.0,
                message=f"Erro de sintaxe no código: {e.msg} (linha {e.lineno})",
                category="syntax"
            )
        except Exception as e:
            logger.warning("[VALIDATOR] Regra '%s' falhou com erro inesperado: %s", rule_name, e)
            return None
