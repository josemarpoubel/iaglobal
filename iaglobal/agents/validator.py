# iaglobal/agents/validator.py

"""SemanticValidator — Validação semântica e estrutural de código."""

from __future__ import annotations

import ast
import asyncio
import logging

from typing import Dict, Any, List, Optional

from iaglobal.validation.engine import FeedbackEngine

from iaglobal.utils.logger import logger as module_logger

logger = logging.getLogger("ia-global")

# If module_logger provides configuration, keep it as fallback
if module_logger:
    logger = module_logger

# iaglobal/agents/validator.py

class SemanticValidatorAgent:
    def __init__(self, pass_threshold=80.0, registry=None):
        self.pass_threshold = pass_threshold
        self.registry = registry or RuleRegistry.default()

    async def validate_async(self, code: str, task: str) -> ValidationResult:
        # 1. Detectar linguagem de forma assíncrona
        language = await LanguageDetector.detect(code)
        
        # 2. Avaliar regras (exemplo simplificado de lógica de engine)
        results = []
        for rule in self.registry.rules:
            result = await rule.evaluate(code, task, language)
            if result:
                results.append(result)
        
        # 3. Agregar resultados
        score, by_cat, errors, suggestions = ScoreAggregator.aggregate(results)
        
        return ValidationResult(
            valid=score >= self.pass_threshold,
            score=score,
            rule_results=results,
            errors=errors,
            suggestions=suggestions,
            language=language
        )
