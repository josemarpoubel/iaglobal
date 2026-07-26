# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Knowledge Contracts — tipos base para a camada de inteligência tecnológica.

Sem executor. Sem ORM. Sem LLM. Apenas dataclasses imutáveis que definem
o contrato entre os adaptadores de ecossistema e o KnowledgeEngine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MaturityLevel(Enum):
    EXPERIMENTAL = 0.1
    IMMATURE = 0.3
    MATURE = 0.7
    STABLE = 0.9
    GOLD = 1.0


@dataclass(frozen=True)
class ValidationResult:
    success: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class KnowledgeProvenance:
    source: str
    retrieved_at: datetime
    version: str | None = None
    confidence: float = 0.5
