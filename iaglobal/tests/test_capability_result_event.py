# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
CapabilityResultEvent — Etapa 5 do ADR-0004.

Foco do teste é a **cadeia causal explícita**:

    CapabilityDecisionEvent
            |
            |  decision.id  ───────────────────┐
            |                                  | predecessor_event_id
            v                                  v
    CapabilityResultEvent    ─────────►  causal edge

O contrato arquitetural:

* ``decision_event_id`` é obrigatório (não-Optional). Resultado sem
  decisão não existe.
* ``decision_event_id: EventId`` é tipado — strings cruas ou inferência
  por ``mission_id + created_at`` não passam.
* A serialização preserva o tipo forte na wire (via ``str(id)``).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from iaglobal.events import (
    CapabilityDecisionEvent,
    CapabilityResultEvent,
    DomainEvent,
    EventId,
)
from iaglobal.events.event_types import EventType


# ── Helpers ───────────────────────────────────────────────────────────────


def _decision_event(**overrides) -> CapabilityDecisionEvent:
    payload = dict(
        id=EventId("evt_dec_root"),
        event_type=EventType.CAPABILITY_SELECTED,
        mission_id="m42",
        created_at=datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc),
        capability="pdf_generation",
        selected_technology="reportlab",
        validation_confidence=0.85,
        effective_score=0.9,
        bandit_score=0.3,
        reason=("installed",),
        fallback_used=False,
        candidate_count=3,
        filtered_count=2,
    )
    payload.update(overrides)
    return CapabilityDecisionEvent(**payload)


def _result_event(
    *, decision_event_id: EventId | None = None, **overrides
) -> CapabilityResultEvent:
    if decision_event_id is None:
        decision_event_id = EventId("evt_dec_default")
    payload = dict(
        id=EventId("evt_res"),
        event_type=EventType.CAPABILITY_RESULT,
        mission_id="m42",
        created_at=datetime(2026, 7, 25, 12, 1, tzinfo=timezone.utc),
        decision_event_id=decision_event_id,
        capability="pdf_generation",
        selected_technology="reportlab",
        success=True,
        artifact_kind="CODE",
        validation_status="passed",
        quality_score=0.92,
        repair_count=0,
        latency_ms=1543.0,
    )
    payload.update(overrides)
    return CapabilityResultEvent(**payload)


# ── Schema & inheritance ───────────────────────────────────────────────────


def test_result_event_inherits_from_domain_event():
    """Inheritance backbone — same as for any domain event."""
    e = _result_event()
    assert issubclass(CapabilityResultEvent, DomainEvent)
    assert isinstance(e, DomainEvent)


def test_result_event_has_all_required_fields():
    """Frozen dataclass requires every inherited + own attribute."""
    e = _result_event()
    # Inherited from DomainEvent
    assert isinstance(e.id, EventId)
    assert isinstance(e.event_type, str)
    assert isinstance(e.mission_id, str)
    assert isinstance(e.created_at, datetime)
    assert isinstance(e.evidence, MappingProxyType)
    # Own attributes
    assert isinstance(e.decision_event_id, EventId)
    assert isinstance(e.capability, str)
    assert isinstance(e.success, bool)
    assert isinstance(e.quality_score, float)


def test_decision_event_id_is_required():
    """``decision_event_id`` must be provided — a result with no
    decision violates the ADR-0004 lineage invariant.
    """
    with pytest.raises(TypeError):
        CapabilityResultEvent(
            id=EventId("evt_no_dec"),
            event_type=EventType.CAPABILITY_RESULT,
            mission_id="m42",
            created_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
            capability="pdf",
            selected_technology="reportlab",
            success=True,
            artifact_kind="CODE",
            validation_status="passed",
            quality_score=0.9,
            repair_count=0,
            latency_ms=100.0,
        )  # type: ignore[call-arg]


# ── Frozen + evidence immutability ────────────────────────────────────────


def test_result_event_is_frozen():
    e = _result_event()
    with pytest.raises(AttributeError):
        e.success = False  # type: ignore[misc]


def test_result_event_evidence_is_immutable():
    """Inherited from DomainEvent — propagates to subclass."""
    e = _result_event(decision_event_id=EventId("evt_x"), evidence={"raw": "ok"})
    assert isinstance(e.evidence, MappingProxyType)
    with pytest.raises(TypeError):
        e.evidence["inject"] = "fail"  # type: ignore[index]


# ── Causal chain (the architectural test) ──────────────────────────────────


def test_decision_to_result_causal_chain():
    """The architectural invariant:
        ``result.decision_event_id == decision.id``

    Without this, the lineage collapses to mission_id+timestamp
    inference (correlation, not causation).
    """
    decision = _decision_event(id=EventId("evt_a81f"))
    result = _result_event(decision_event_id=decision.id)

    # Type-strong identity:
    assert isinstance(result.decision_event_id, EventId)
    # Equality by value:
    assert result.decision_event_id == decision.id
    # Distinct identities (decision.id ≠ result.id):
    assert decision.id != result.id


def test_decision_and_result_preserve_mission_correlation():
    """Both events share ``mission_id`` so that mission-aggregate queries
    still work in parallel with explicit lineage.
    """
    decision = _decision_event(mission_id="m-XYZ")
    result = _result_event(
        decision_event_id=decision.id,
        mission_id="m-XYZ",
    )
    assert decision.mission_id == result.mission_id == "m-XYZ"


def test_result_carries_unique_id_distinct_from_decision():
    """A result is its own factual occurrence — never shares its id
    with the decision that produced it.
    """
    decision = _decision_event(id=EventId("evt_a"))
    result = _result_event(
        decision_event_id=decision.id,
        id=EventId("evt_b"),
    )
    assert result.id != decision.id
    assert result.decision_event_id == decision.id


def test_created_at_after_decision_created_at():
    """Sanity: causal edge implies temporal order (UTC). If a result's
    ``created_at`` predates its decision's, the lineage has hanged.
    """
    decision_time = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
    result_time = decision_time + timedelta(seconds=30)
    decision = _decision_event(created_at=decision_time)
    result = _result_event(
        decision_event_id=decision.id,
        created_at=result_time,
    )
    assert result.created_at > decision.created_at


# ── Serialization ────────────────────────────────────────────────────────


def test_to_dict_inherits_parent_fields_and_adds_body():
    """``to_dict()`` includes inherited + subclass body, with the
    decision reference as plain string (wire format)."""
    e = _result_event(
        decision_event_id=EventId("evt_a81f"),
        evidence={"notes": "compiled cleanly"},
    )
    d = e.to_dict()
    # Inherited parent fields
    assert d["id"] == "evt_res"
    assert d["event_type"] == EventType.CAPABILITY_RESULT
    assert d["mission_id"] == "m42"
    assert d["created_at"].startswith("2026-07-25T")
    assert d["evidence"] == {"notes": "compiled cleanly"}
    # Subclass body
    assert d["decision_event_id"] == "evt_a81f"
    assert d["capability"] == "pdf_generation"
    assert d["selected_technology"] == "reportlab"
    assert d["success"] is True
    assert d["artifact_kind"] == "CODE"
    assert d["validation_status"] == "passed"
    assert d["quality_score"] == 0.92
    assert d["repair_count"] == 0
    assert d["latency_ms"] == 1543.0


def test_to_dict_promotes_decision_event_id_to_string():
    """Wire format uses ``str(EventId)`` for the lineage reference —
    ``EventId.value`` is the canonical string form. Consumers must
    not depend on internal EventId structure.
    """
    e = _result_event(decision_event_id=EventId("evt_a81f"))
    d = e.to_dict()
    assert d["decision_event_id"] == "evt_a81f"
    assert isinstance(d["decision_event_id"], str)
