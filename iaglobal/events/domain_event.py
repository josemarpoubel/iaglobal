# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

# iaglobal/events/domain_event.py
"""
Base class abstrata para todos os eventos de domínio do iaglobal.

ADR 0004 — Contrato de Linhagem de Eventos.

Todo evento de domínio deve herdar de ``DomainEvent``. Os invariantes:

* ``id: EventId`` — identidade opaca única por evento.
* ``event_type: str`` — discriminador semântico (categoria do fato).
* ``mission_id: str`` — agrupador contextual (``""`` para eventos
  de sistema / sem missão).
* ``created_at: datetime`` — carimbo UTC.
* ``evidence: Mapping[str, Any]`` — re-freeze para ``MappingProxyType``
  em ``__post_init__`` (imutabilidade real, não apenas slot-frozen).

A herança é rígida. Eventos legados (``dict``-shaped no barramento)
permanecem funcionando na fase de migração, mas qualquer evento
**novo** é um ``DomainEvent`` concreto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Dict, Mapping

from iaglobal.events.event_id import EventId


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DomainEvent:
    """Espinha dorsal comum — todo evento de domínio."""

    id: EventId
    event_type: str
    mission_id: str
    created_at: datetime
    evidence: Mapping[str, Any] = field(default_factory=dict, kw_only=True)

    def __post_init__(self) -> None:
        # O ``frozen=True`` do dataclass protege os *slots*. Mas o
        # ``Mapping`` interno continua mutável a menos que a gente o
        # envolva. ``__post_init__`` faz o freeze profundo em uma única
        # passagem.
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))

    def to_dict(self) -> Dict[str, Any]:
        """Serialização base — subclasses podem estender via ``super``.

        ``dict.asdict()`` é deliberadamente evitado: ele deep-copia via
        pickle e não suporta ``MappingProxyType`` (vide ADR 0004).
        """
        return {
            "id": str(self.id),
            "event_type": self.event_type,
            "mission_id": self.mission_id,
            "created_at": self.created_at.isoformat(),
            "evidence": dict(self.evidence),
        }
