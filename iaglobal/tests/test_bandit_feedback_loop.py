# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Etapa 7 — Bandit feedback observer tests.

Causal loop:

    CAPABILITY_RESULT (success, quality, selected_technology)
        ↓
    BanditFeedbackObserver._on_result
        ↓
    bandit.update_reward(arm, reward, ivm)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from iaglobal.events import (
    CapabilityResultEvent,
    EventId,
)
from iaglobal.events.event_types import EventType
from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.models.event_bus import bus


# ── Helpers ───────────────────────────────────────────────────────────────


def _result(**overrides) -> CapabilityResultEvent:
    p = dict(
        id=EventId("evt_r"),
        event_type=EventType.CAPABILITY_RESULT,
        mission_id="m42",
        created_at=datetime(2026, 7, 25, 12, 1, tzinfo=timezone.utc),
        decision_event_id=EventId("evt_d"),
        capability="data",
        selected_technology="pandas",
        success=True,
        artifact_kind="code",
        validation_status="passed",
        quality_score=0.85,
        repair_count=0,
        latency_ms=200.0,
    )
    p.update(overrides)
    return CapabilityResultEvent(**p)


def _publish(r: CapabilityResultEvent) -> None:
    bus.publish(r.event_type, data=r.to_dict(), source="test")


# ── Causal credit ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_bus():
    bus.reset()


def test_success_credits_bandit_with_quality_score():
    bandit = BanditPolicy(epsilon=0.0)
    from iaglobal.graphs.bandit_feedback import BanditFeedbackObserver
    BanditFeedbackObserver(bandit)

    _publish(_result(success=True, quality_score=0.92, selected_technology="weasyprint"))

    assert bandit.rewards.get("weasyprint") == [0.92]


def test_failure_credits_zero_to_bandit():
    """Failure still records reward=0.0 — the bandit tracks that the
    arm was tried but produced no value."""
    bandit = BanditPolicy(epsilon=0.0)
    from iaglobal.graphs.bandit_feedback import BanditFeedbackObserver
    BanditFeedbackObserver(bandit)

    _publish(_result(success=False, quality_score=0.9, selected_technology="pandas"))

    assert bandit.rewards.get("pandas") == [0.0]


# ── Anti-pathology guard ─────────────────────────────────────────────────


def test_low_quality_failure_does_not_inflate_reward():
    """0.1-quality failure → reward=0 (not 0.9 from the (1.0 - quality)
    formula rejected during review)."""
    bandit = BanditPolicy(epsilon=0.0)
    from iaglobal.graphs.bandit_feedback import BanditFeedbackObserver
    BanditFeedbackObserver(bandit)

    _publish(_result(success=False, quality_score=0.1, selected_technology="pandas"))

    assert bandit.rewards["pandas"] == [0.0]


# ── Idempotency (current bus) ────────────────────────────────────────────


def test_double_publish_double_credit_current_behavior():
    """The observer does NOT deduplicate; two publishes → two credits.
    This matches the current bus contract (FIFO; replay dedup is a
    future responsibility of the EventStore)."""
    bandit = BanditPolicy(epsilon=0.0)
    from iaglobal.graphs.bandit_feedback import BanditFeedbackObserver
    BanditFeedbackObserver(bandit)

    r = _result(success=True, quality_score=0.75, selected_technology="pandas")
    _publish(r)
    _publish(r)

    assert bandit.rewards["pandas"] == [0.75, 0.75]


# ── Edge: no technology (legacy fallback) ────────────────────────────────


def test_no_credit_when_selected_technology_none():
    bandit = BanditPolicy(epsilon=0.0)
    from iaglobal.graphs.bandit_feedback import BanditFeedbackObserver
    BanditFeedbackObserver(bandit)

    _publish(_result(success=True, selected_technology=None))

    assert not bandit.rewards, f"reward should not credit: {bandit.rewards}"


# ── Contracts: typed dataclass, not dict keys ────────────────────────────


def test_observer_reconstructs_dataclass_from_dict():
    from iaglobal.graphs.bandit_feedback import BanditFeedbackObserver

    class SpyBandit:
        def __init__(self):
            self.call = None

        def update_reward(self, arm, reward, ivm):
            self.call = (arm, reward, ivm)

    spy = SpyBandit()
    BanditFeedbackObserver(spy)

    _publish(_result(
        success=True, quality_score=0.88, selected_technology="sqlite3"
    ))

    assert spy.call == ("sqlite3", 0.88, 1.0)


# ── Auto-wire in singleton ────────────────────────────────────────────────


def test_get_bandit_auto_wires_observer():
    from iaglobal.graphs.bandit import _get_bandit
    b = _get_bandit()
    assert getattr(b, "_feedback_attached", False), (
        "auto-wire should set feedback_attached flag"
    )
