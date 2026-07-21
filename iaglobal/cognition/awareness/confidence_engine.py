# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
ConfidenceEngine v3.2 — Cálculo e evolução de confiança cognitiva.

Responsável por compute_confidence(), effective_confidence() e get_confidence_timeline().
Funções puras — sem efeitos colaterais, sem acesso a banco de dados.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from iaglobal.cognition.awareness.models import (
    ConfidenceTrace,
    AwarenessExecutionContext,
    compute_confidence,
    effective_confidence,
)


class ConfidenceEngine:
    """
    Motor de confiança cognitiva.

    Invariantes:
    - effective_confidence é função pura (não altera histórico)
    - confidence ∈ [0,1] em duas camadas (clamp + CHECK SQL)
    - ConfidenceTrace conserva: base + Σpositivos − Σnegativos == final
    """

    def __init__(self, repository, clock):
        self._repository = repository
        self._clock = clock

    def compute(self, ctx: AwarenessExecutionContext) -> tuple[float, ConfidenceTrace]:
        """
        Calcula confiança para um contexto de execução.

        Returns: (score, trace) — determinístico, rastreável.
        """
        return compute_confidence(ctx)

    def effective(
        self,
        base: float,
        trace: ConfidenceTrace,
        decay: float = 0.0,
    ) -> float:
        """
        Calcula confiança efetiva com decay temporal opcional.

        decay: fator de decaimento por unidade de tempo (0 = sem decaimento).
        """
        return effective_confidence(base, trace, decay)

    def get_timeline(
        self,
        repository,
        execution_id: str,
        node_id: str | None = None,
    ) -> list[dict]:
        """
        Retorna timeline de confiança consultando o repositório.
        """
        rows = repository.load_confidence_timeline(
            execution_id=execution_id, node_id=node_id
        )
        from iaglobal.cognition.awareness.models import deserialize_confidence_trace

        timeline = []
        for row in rows:
            entry = dict(row)
            if entry.get("reason"):
                entry["reason"] = deserialize_confidence_trace(entry["reason"])
            timeline.append(entry)
        return timeline
