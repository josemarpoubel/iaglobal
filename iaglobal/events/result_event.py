# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

# iaglobal/events/result_event.py
"""
``CapabilityResultEvent`` — Etapa 5 do ADR-0004.

Fecha a cadeia causal iniciada por ``CapabilityDecisionEvent``:

    CAPABILITY_SELECTED → CAPABILITY_RESULT
    (id=N_a81f)             (id=N_b402)
                                decision_event_id=N_a81f

Antes deste commit a ligação era **inferida** por ``mission_id`` +
``created_at``: correlação. Agora é **declarada** pelo campo
``decision_event_id: EventId`` — referência explícita ao predecessor.

Invariantes que este dataclass preserva (vide :class:`DomainEvent`):

* ``id`` opaco, único por evento;
* ``event_type`` discrimina ``"capability_result"``;
* ``mission_id`` agrupador contextual;
* ``created_at`` UTC;
* ``evidence`` re-freeze em ``__post_init__``;
* Subclass não precisa repetir o freeze — chama ``super().__post_init__``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from iaglobal.events.domain_event import DomainEvent
from iaglobal.events.event_id import EventId


@dataclass(frozen=True)
class CapabilityResultEvent(DomainEvent):
    """``CAPABILITY_RESULT`` — emitida após a execução do capability escolhido.

    A referência ao predecessor é obrigatória (``decision_event_id``),
    porque todo resultado decorre de uma decisão. Sem predecessor, o
    evento não existe — esta é a regra do ADR-0004.

    Convenção de ``event_type``: o publicador passa
    :data:`EventType.CAPABILITY_RESULT` no construtor — o dataclass
    não fixa default para forçar lembretes de preenchimento em code
    review.
    """

    decision_event_id: EventId
    capability: str
    selected_technology: Optional[str]
    success: bool
    artifact_kind: str
    validation_status: str
    quality_score: float
    repair_count: int
    latency_ms: float
    provider: Optional[str] = None

    def __post_init__(self) -> None:
        # Herda freeze de ``evidence`` via parent.
        super().__post_init__()

    def to_dict(self) -> Dict[str, Any]:
        # ``event_type``, ``id`` (como str), ``created_at``, ``evidence``
        # vêm do parent.
        data = super().to_dict()
        # A serialização do predecessor é sempre ``str`` — o contrato
        # público de referência é string-like; o tipo forte está no
        # payload Python, não na wire format.
        data["decision_event_id"] = str(self.decision_event_id)
        data.update(
            {
                "capability": self.capability,
                "selected_technology": self.selected_technology,
                "success": self.success,
                "artifact_kind": self.artifact_kind,
                "validation_status": self.validation_status,
                "quality_score": self.quality_score,
                "repair_count": self.repair_count,
                "latency_ms": self.latency_ms,
                "provider": self.provider,
            }
        )
        return data
