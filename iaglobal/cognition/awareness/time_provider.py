# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Time Provider v3.1.5 — Deterministic Clock para replay e testes.

Provê abstração de tempo eliminando time.time() direto dos engines.
"""

from __future__ import annotations

import time
from typing import Protocol


class ClockProvider(Protocol):
    """Protocol para fonte de tempo — permite FakeClock em testes."""

    def now(self) -> float:
        """Retorna timestamp atual (Unix epoch) — para eventos, timestamps."""
        ...

    def monotonic(self) -> float:
        """Retorna tempo monotônico — para medição de latência e timeouts."""
        ...


class SystemClock:
    """Fonte de tempo real — wrapper em torno de time.time()."""

    def now(self) -> float:
        return time.time()

    def monotonic(self) -> float:
        return time.monotonic()


class FakeClock:
    """Clock determinístico — avançado manualmente em testes."""

    def __init__(self, initial: float = 0.0) -> None:
        self._epoch: float = initial
        self._mono: float = 0.0

    def now(self) -> float:
        return self._epoch

    def monotonic(self) -> float:
        return self._mono

    def advance(self, delta: float) -> None:
        if delta < 0:
            raise ValueError("FakeClock não suporta retroceder o tempo")
        self._epoch += delta
        self._mono += delta
