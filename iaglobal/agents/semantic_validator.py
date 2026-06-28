# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/agents/semantic_validator.py
"""
Semantic Validation Module - Implementation for code validation with rules and scoring.
"""

from __future__ import annotations

import ast
import re
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Pattern

from iaglobal.utils.helpers import run_async_safe


# =============================================================================
# Enums and Data Classes
# =============================================================================

class Language(Enum):
    PYTHON = "python"
    HTML = "html"
    GENERIC = "generic"


@dataclass
class RuleResult:
    name: str
    description: str
    passed: bool
    weight: float
    category: str
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    valid: bool
    score: float
    language: Language
    errors: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    rule_results: List[RuleResult] = field(default_factory=list)
    score_by_category: Dict[str, float] = field(default_factory=dict)
    elapsed_ms: float = 0.0

    def to_legacy_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "score": self.score,
            "errors": self.errors,
            "details": {
                "language": self.language.value,
                "rule_results": [
                    {
                        "name": r.name,
                        "passed": r.passed,
                        "weight": r.weight,
                        "category": r.category,
                        "suggestion": r.suggestion,
                    }
                    for r in self.rule_results
                ],
                "score_by_category": self.score_by_category,
            }
        }


# =============================================================================
# Language Detector
# =============================================================================

class LanguageDetector:
    @staticmethod
    async def detect(code: str) -> Language:
        code_stripped = code.strip()
        if not code_stripped:
            return Language.GENERIC

        if code_stripped.startswith("<!DOCTYPE html") or code_stripped.startswith("<html"):
            return Language.HTML

        python_indicators = ["def ", "class ", "import ", "from ", "async def", "await "]
        if any(indicator in code_stripped for indicator in python_indicators):
            return Language.PYTHON

        return Language.GENERIC


# =============================================================================
# Validation Rules
# =============================================================================

class ValidationRule:
    """Base class for validation rules."""

    def __init__(self, name: str, weight: float, category: str):
        self.name = name
        self.weight = weight
        self.category = category

    async def evaluate(self, code: str, task: str, language: Language) -> Optional[RuleResult]:
        raise NotImplementedError


class PythonStructureRule(ValidationRule):
    """Checks for function/class definitions in generative Python tasks."""

    def __init__(self):
        super().__init__("python_structure", weight=30.0, category="structure")

    async def evaluate(self, code: str, task: str, language: Language) -> Optional[RuleResult]:
        if language != Language.PYTHON:
            return None

        generative_keywords = ["criar", "criar uma", "criar um", "implementar", "escrever", "gerar", "função", "classe"]
        if not any(kw in task.lower() for kw in generative_keywords):
            return None

        try:
            tree = await asyncio.to_thread(ast.parse, code)
            has_func_or_class = any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                for node in ast.walk(tree)
            )

            if has_func_or_class:
                return RuleResult(self.name, "Possui estrutura (função/classe)", True, self.weight, self.category)
            else:
                return RuleResult(
                    self.name, "Código Python sem função ou classe", False, self.weight, self.category,
                    suggestion="Adicione uma definição de função (def) ou classe (class)"
                )
        except SyntaxError:
            return RuleResult(self.name, "Erro de sintaxe no código Python", False, self.weight, self.category)


class HtmlStructureRule(ValidationRule):
    """Checks for complete HTML structure."""

    def __init__(self):
        super().__init__("html_structure", weight=30.0, category="structure")

    async def evaluate(self, code: str, task: str, language: Language) -> Optional[RuleResult]:
        if language != Language.HTML:
            return None

        has_doctype = "<!DOCTYPE html" in code or "<!doctype html" in code.lower()
        has_html = "<html" in code.lower() and "</html>" in code.lower()
        has_body = "<body" in code.lower() and "</body>" in code.lower()

        if has_doctype and has_html and has_body:
            return RuleResult(self.name, "HTML completo com doctype, html e body", True, self.weight, self.category)
        else:
            missing = []
            if not has_doctype:
                missing.append("DOCTYPE")
            if not has_html:
                missing.append("tags <html>")
            if not has_body:
                missing.append("tags <body>")
            return RuleResult(
                self.name, f"HTML incompleto: faltando {', '.join(missing)}", False, self.weight, self.category,
                suggestion=f"Adicione {', '.join(missing)} ao documento HTML"
            )


class KeywordPresenceRule(ValidationRule):
    """Checks for required keyword in code when mentioned in task."""

    def __init__(self, name: str, weight: float, category: str, pattern: Pattern, label: str):
        super().__init__(name, weight, category)
        self.pattern = pattern
        self.label = label

    async def evaluate(self, code: str, task: str, language: Language) -> Optional[RuleResult]:
        if self.pattern.search(task) is None:
            return None

        found = self.pattern.search(code) is not None
        if found:
            return RuleResult(self.name, f"{self.label} presente no código", True, self.weight, self.category)
        else:
            return RuleResult(
                self.name, f"{self.label} ausente no código", False, self.weight, self.category,
                suggestion=f"Adicione {self.label} ao código"
            )


class PythonImportHashlibRule(ValidationRule):
    """Checks for hashlib import when task requires it."""

    def __init__(self):
        super().__init__("python_import_hashlib", weight=20.0, category="imports")
        self.hashlib_pattern = re.compile(r"\bimport\s+hashlib\b|\bfrom\s+hashlib\s+import\b")

    async def evaluate(self, code: str, task: str, language: Language) -> Optional[RuleResult]:
        if language != Language.PYTHON:
            return None

        hashlib_keywords = ["hashlib", "sha3", "sha256", "sha512", "md5", "hash"]
        if not any(kw in task.lower() for kw in hashlib_keywords):
            return None

        has_import = self.hashlib_pattern.search(code) is not None
        if has_import:
            return RuleResult(self.name, "Import hashlib presente", True, self.weight, self.category)
        else:
            return RuleResult(
                self.name, "Import hashlib ausente", False, self.weight, self.category,
                suggestion="Adicione 'import hashlib' ao código"
            )


# =============================================================================
# Rule Registry
# =============================================================================

class RuleRegistry:
    def __init__(self):
        self.rules: List[ValidationRule] = []

    def register(self, rule: ValidationRule) -> "RuleRegistry":
        self.rules.append(rule)
        return self

    @classmethod
    def default(cls) -> "RuleRegistry":
        registry = cls()
        registry.register(PythonStructureRule())
        registry.register(HtmlStructureRule())
        registry.register(PythonImportHashlibRule())
        registry.register(KeywordPresenceRule(
            "req_sha3_512", weight=20.0, category="cryptography",
            pattern=re.compile(r"sha3.?512", re.IGNORECASE), label="SHA3-512"
        ))
        return registry


# =============================================================================
# Score Aggregator
# =============================================================================

DEFAULT_PASS_THRESHOLD = 70.0


class ScoreAggregator:
    @staticmethod
    def aggregate(results: List[RuleResult]) -> tuple:
        if not results:
            return 100.0, {}, [], []

        total_weight = sum(r.weight for r in results)
        if total_weight == 0:
            return 100.0, {}, [], []

        passed_weight = sum(r.weight for r in results if r.passed)
        score = (passed_weight / total_weight) * 100.0

        by_category: Dict[str, List[RuleResult]] = {}
        for r in results:
            by_category.setdefault(r.category, []).append(r)

        score_by_category = {}
        for cat, rules in by_category.items():
            cat_weight = sum(r.weight for r in rules)
            cat_passed = sum(r.weight for r in rules if r.passed)
            score_by_category[cat] = (cat_passed / cat_weight * 100.0) if cat_weight > 0 else 100.0

        errors = [r.description for r in results if not r.passed]
        suggestions = [r.suggestion for r in results if not r.passed and r.suggestion]

        return score, score_by_category, errors, suggestions


# =============================================================================
# Semantic Validator Agent
# =============================================================================

class SemanticValidatorAgent:
    def __init__(
        self,
        registry: Optional[RuleRegistry] = None,
        pass_threshold: float = DEFAULT_PASS_THRESHOLD
    ):
        self.registry = registry or RuleRegistry.default()
        self.pass_threshold = pass_threshold

    def validate(self, code: str, task: str = "") -> Dict[str, Any]:
        result = run_async_safe(self.validate_async, code, task)
        if hasattr(result, "to_legacy_dict"):
            return result.to_legacy_dict()
        return result

    async def validate_async(self, code: str, task: str = "") -> ValidationResult:
        start_time = time.time()

        language = await LanguageDetector.detect(code)
        rule_results = []

        for rule in self.registry.rules:
            try:
                result = await rule.evaluate(code, task, language)
                if result is not None:
                    rule_results.append(result)
            except Exception as e:
                rule_results.append(RuleResult(rule.name, str(e), False, rule.weight or 100.0, "error"))

        score, score_by_category, errors, suggestions = ScoreAggregator.aggregate(rule_results)
        valid = score >= self.pass_threshold and len(errors) == 0

        elapsed_ms = (time.time() - start_time) * 1000

        return ValidationResult(
            valid=valid,
            score=score,
            language=language,
            errors=errors,
            suggestions=suggestions,
            rule_results=rule_results,
            score_by_category=score_by_category,
            elapsed_ms=elapsed_ms,
        )