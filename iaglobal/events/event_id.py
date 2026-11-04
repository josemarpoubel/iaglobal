# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

# iaglobal/events/event_id.py
"""
Identidade opaca de evento.

ADR 0004 — Contrato de Linhagem de Eventos.

``EventId`` é o elo entre eventos: o consumidor trata ``value`` como
string comparável e **nunca** depende do formato. Hoje usa UUID8;
amanhã pode migrar para ULID, hash causal, UUIDv7, ou id externo —
sem quebrar consumidores, porque a referência passa a ser por
``EventId`` em vez de string crua.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventId:
    """Identidade opaca de um evento no iaglobal.

    Construtor exige ``EventId(value)`` explícito — strings cruas não
    são aceitas silenciosamente. Esse rigor evita mistura acidental
    entre ``EventId`` e ``str`` durante migração de eventos legados
    (vide ADR 0004 § "Compatibilidade retroativa").
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError(
                "EventId.value must be a string; "
                "wrap raw identifiers explicitly with EventId(...)"
            )
        if not self.value:
            raise ValueError("EventId.value must be a non-empty string")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"EventId({self.value!r})"
