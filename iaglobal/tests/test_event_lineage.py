# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Event Lineage Contract — ADR 0004 gate.

These tests enforce the four invariants of the lineage contract:

1. ``EventId`` is opaque — string + ``value`` only.
2. ``DomainEvent.evidence`` is genuinely immutable (frozen +
   ``MappingProxyType``), not merely ``frozen=True`` on the dataclass
   slot.
3. ``CapabilityDecisionEvent`` carries an ``EventId`` (not a public
   ``str``) so consumers cannot drift into identity-by-string.
4. Lineage is explicit via the ``predecessor_event_id`` field, with
   ``EventId``-typed reference — not by ``mission_id`` + timestamp
   inference.

Gate requirements (per ADR 0004 § "Validação automatizada"):

* exit 0 before any derived event is added.
* refreshed on every change to ``events/__init__.py`` or subclass.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from iaglobal.events import (
    CapabilityDecisionEvent,
    DomainEvent,
    EventId,
)
from iaglobal.events.event_types import EventType


# ── EventId: opaque identity ──────────────────────────────────────────────


def test_event_id_is_opaque():
    """``EventId`` is a value-only wrapper — no format dependency.

    Consumers must NOT rely on the format (UUID8 today, ULID tomorrow,
    hash causal later).
    """
    eid = EventId("abc")
    assert eid.value == "abc"
    assert str(eid) == "abc"


def test_event_id_rejects_non_string():
    """Strings are the only accepted value type — int, None, dict fail."""
    with pytest.raises(TypeError):
        EventId(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        EventId(None)  # type: ignore[arg-type]


def test_event_id_rejects_empty_string():
    """Empty string would defeat uniqueness — guarded at construction."""
    with pytest.raises(ValueError):
        EventId("")


def test_two_event_ids_with_same_value_are_equal():
    """Equality is by ``value`` (frozen dataclass equality)."""
    assert EventId("evt_42") == EventId("evt_42")
    assert EventId("evt_a") != EventId("evt_b")


# ── DomainEvent: frozen + evidence immutability ───────────────────────────


def _domain_event_with_evidence(**overrides) -> DomainEvent:
    payload = dict(
        id=EventId("evt_dom"),
        event_type="test_event",
        mission_id="m-dom",
        created_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
        evidence={"k": "v"},
    )
    payload.update(overrides)
    return DomainEvent(**payload)


def test_domain_event_is_frozen():
    """Slot assignment must raise ``FrozenInstanceError`` (subclass of
    ``AttributeError``)."""
    e = _domain_event_with_evidence()
    with pytest.raises(AttributeError):
        e.mission_id = "tampered"  # type: ignore[misc]


def test_domain_event_evidence_is_immutable():
    """``evidence`` slot receives ``MappingProxyType`` deep-freeze.

    ``frozen=True`` on the dataclass only protects the slot, not inner
    content. ``__post_init__`` is what wraps the dict into a
    ``MappingProxyType`` so consumers cannot silently mutate.
    """
    e = _domain_event_with_evidence(evidence={"k": "v"})
    assert isinstance(e.evidence, MappingProxyType)
    with pytest.raises(TypeError):
        e.evidence["injected"] = "value"  # type: ignore[index]


def test_domain_event_evidence_defaults_to_empty_mapping():
    """Empty ``evidence`` is still a ``MappingProxyType`` — not None
    and not a plain dict."""
    e = _domain_event_with_evidence(evidence={})
    assert isinstance(e.evidence, MappingProxyType)
    assert dict(e.evidence) == {}


def test_domain_event_to_dict_round_trip():
    """``to_dict()`` returns a JSON-friendly dict with ISO timestamp."""
    e = _domain_event_with_evidence(evidence={"a": 1, "b": [1, 2]})
    d = e.to_dict()
    assert d["id"] == "evt_dom"  # EventId.value as str
    assert d["event_type"] == "test_event"
    assert d["mission_id"] == "m-dom"
    assert d["created_at"].startswith("2026-07-25T")
    assert d["evidence"] == {"a": 1, "b": [1, 2]}


# ── CapabilityDecisionEvent: lineage carrier ───────────────────────────────


def _decision_event(**overrides) -> CapabilityDecisionEvent:
    payload = dict(
        id=EventId("evt_decision"),
        event_type=EventType.CAPABILITY_SELECTED,
        mission_id="m-dec",
        created_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
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


def test_capability_decision_event_has_event_identity():
    """The event carries a typed ``EventId`` — never an unwrapped string.

    This prevents the legacy mix-up where one emitter forgets to wrap
    with ``EventId(...)`` and downstream codechecks ``isinstance(id,
    EventId)``.
    """
    e = _decision_event(id=EventId("evt_typed"))
    assert isinstance(e.id, EventId)
    assert e.id.value == "evt_typed"


def test_capability_decision_event_inherits_from_domain_event():
    """Inheritance is the contract backbone — concrete events extend."""

    assert issubclass(CapabilityDecisionEvent, DomainEvent)


def test_capability_decision_event_inherits_evidence_freeze():
    """Subclasses don't need to repeat freeze — parent's
    ``__post_init__`` runs (via ``super().__post_init__``).
    """
    e = _decision_event(evidence={"raw": "ok"})
    assert isinstance(e.evidence, MappingProxyType)
    with pytest.raises(TypeError):
        e.evidence["x"] = "fail"  # type: ignore[index]


def test_capability_decision_event_to_dict_inherits_parent_fields():
    """``to_dict()`` includes parent fields (``id`` as ``str``,
    ``event_type``, ``mission_id``, ``created_at``, ``evidence``) plus
    subclass body."""
    e = _decision_event(evidence={"k": "v"})
    d = e.to_dict()
    assert d["id"] == "evt_decision"
    assert d["event_type"] == EventType.CAPABILITY_SELECTED
    assert d["mission_id"] == "m-dec"
    assert d["created_at"].startswith("2026-07-25T")
    assert d["evidence"] == {"k": "v"}
    # subclass body
    assert d["capability"] == "pdf_generation"
    assert d["selected_technology"] == "reportlab"
    assert d["decision_confidence"] > 0


def test_capability_decision_event_predecessor_references_event_id():
    """A successor event names its predecessor by ``EventId`` — never by
    string inference. This is the explicit lineage rule from ADR 0004.
    """
    decision_id = EventId("evt_decision")
    e = _decision_event(id=decision_id, predecessor_event_id=EventId("evt_prev"))

    assert e.predecessor_event_id == EventId("evt_prev")
    # The Optional default is None when no predecessor (first event in chain).
    assert e.predecessor_event_id is not None

    no_pred = _decision_event(predecessor_event_id=None)
    assert no_pred.predecessor_event_id is None


def test_predecessor_reference_uses_event_id_type_only():
    """Pure contract: a result-event's ``decision_event_id`` field
    equals ``EventId(...)`` of the decision-event that produced it.

    This is the lineage test the user explicitly required.
    """
    # Decision event — establishes lineage root.
    decision = _decision_event(
        id=EventId("evt_a81f"),
        mission_id="m-lineage",
        capability="pdf_generation",
        selected_technology="reportlab",
    )

    # The 'result' carrier here is a hypothetical CapabilityResultEvent,
    # but for schema-level lineage we simulate it with a sibling
    # CapabilityDecisionEvent that explicitly inherits the predecessor
    # id. The contract is structural: any successor carries the
    # predecessor's EventId.
    successor_id = EventId("evt_b402")
    successor = _decision_event(
        id=successor_id,
        mission_id=decision.mission_id,
        capability=decision.capability,
        selected_technology=decision.selected_technology,
        predecessor_event_id=decision.id,
    )

    # Lineage by EventId, not by mission_id+timestamp.
    assert isinstance(successor.predecessor_event_id, EventId)
    assert successor.predecessor_event_id == decision.id
    assert successor.id != decision.id  # distinct occurrence


# ── Frozen chain: cannot rewrite chain after construction ────────────────


def test_decision_id_immutable_after_construction():
    """Once the event exists, its ``id`` slot cannot be reassigned."""
    e = _decision_event(id=EventId("evt_locked"))
    with pytest.raises(AttributeError):
        e.id = EventId("evt_replaced")  # type: ignore[misc]


def test_evidence_immutable_via_post_init():
    """The ``__post_init__`` deep-freeze applies even when evidence is
    passed as a later-bound value (the wrap happens once, at
    construction)."""
    e = _decision_event(evidence={"raw": "dict"})
    assert isinstance(e.evidence, MappingProxyType)
    original = dict(e.evidence)
    with pytest.raises(TypeError):
        e.evidence["new"] = "value"  # type: ignore[index]
    # untouched
    assert dict(e.evidence) == original
