# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Benchmark Intelligence — medição empírica de tecnologias no ambiente real.

Cada BenchmarkRecord armazena uma execução real medida pelo Validator.
O Technology Bandit consome esses registros para aprender preferências.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from iaglobal.knowledge.contracts import Severity, KnowledgeProvenance


@dataclass(frozen=True)
class BenchmarkRecord:
    technology: str
    capability: str
    execution_time_ms: float
    memory_mb: float
    validator_score: float
    tests_passed: int
    tests_total: int
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    python_version: str = ""
    environment: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    provenance: KnowledgeProvenance | None = None

    @property
    def success_rate(self) -> float:
        if self.tests_total == 0:
            return 0.0
        return self.tests_passed / self.tests_total

    @property
    def reward(self) -> float:
        r = self.validator_score * 0.4
        r += self.success_rate * 0.3
        latency_score = max(0.0, 1.0 - self.execution_time_ms / 10000.0)
        r += latency_score * 0.15
        memory_score = max(0.0, 1.0 - self.memory_mb / 500.0)
        r += memory_score * 0.15
        return round(r, 4)


@dataclass
class BenchmarkHistory:
    _records: dict[str, list[BenchmarkRecord]] = field(default_factory=dict)

    def record(self, r: BenchmarkRecord) -> None:
        key = f"{r.technology}/{r.capability}"
        self._records.setdefault(key, []).append(r)

    def for_technology(self, technology: str) -> list[BenchmarkRecord]:
        return [
            rec
            for key, records in self._records.items()
            for rec in records
            if key.startswith(f"{technology}/")
        ]

    def average_reward(self, technology: str, capability: str) -> float:
        key = f"{technology}/{capability}"
        records = self._records.get(key, [])
        if not records:
            return 0.0
        return sum(r.reward for r in records) / len(records)

    def best_for_capability(self, capability: str) -> Optional[BenchmarkRecord]:
        best = None
        for key, records in self._records.items():
            if not key.endswith(f"/{capability}"):
                continue
            for r in records:
                if best is None or r.reward > best.reward:
                    best = r
        return best
