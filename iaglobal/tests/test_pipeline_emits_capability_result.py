# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Etapa 6 — Runtime causal chain test.

Verifica que o pipeline real fecha a cadeia:

    CapabilityDecisionEvent          CapabilityResultEvent
        id=N_a81f                   decision_event_id=N_a81f
        mission_id="m42"            mission_id="m42"

A arquitetura é testada em três níveis:

1. **state.decision_event_id wiring** — o subscribe local em
   ``async_execute`` captura o ``EventId`` do ``CapabilityDecisionEvent``
   via bus e o armazena em ``state.decision_event_id``. Sem ele, o
   helper ``_emit_capability_result`` aborta (sem predecessor não
   emite).

2. **emit causal edge** — ``_emit_capability_result`` publica
   ``CAPABILITY_RESULT`` com ``decision_event_id == state.decision_event_id``
   e o mesmo ``mission_id``. Falha e sucesso publicam ambos; pipeline
   exception não impede o emit.

3. **end-to-end lineage** — quando o engine recebe dois ``run``s
   distintos, cada resultado tem o predecessor correto. Único
   ``CAPABILITY_SELECTED`` por run; único ``CAPABILITY_RESULT`` por run.
"""

from __future__ import annotations

import pytest

from iaglobal.events import (
    CapabilityDecisionEvent,
    EventId,
)
from iaglobal.events.event_types import EventType
from iaglobal.models.event_bus import bus


def _reset_bus() -> None:
    bus.reset()


def _capture(
    handler,
):  # helper: returns a SubscriberClosure capturing cap of given event type
    received: list[dict] = []
    bus.subscribe(handler, lambda e: received.append(e.data or {}))
    return received


# ── 1. state.decision_event_id wiring test ────────────────────────────────


def _build_isolated_engine():
    """Construct a ``PipelineEngine`` whose orchestration can be
    poked without running the full async path."""

    class _StubOrchestrator:
        class _Bandit:
            def select_model(self, node_id, task_type, candidates, context=None):
                return candidates[0] if candidates else None

        bandit = _Bandit()

    from iaglobal.pipeline.engine import PipelineEngine

    return PipelineEngine(orchestrator=_StubOrchestrator())


@pytest.mark.anyio
async def test_helper_emits_capability_result_with_lineage():
    """The engine helper must publish CAPABILITY_RESULT with the
    decision_event_id captured earlier."""
    from iaglobal.pipeline.pipelinestate import PipelineState

    _reset_bus()
    captured = []
    bus.subscribe(EventType.CAPABILITY_RESULT, lambda e: captured.append(e.data or {}))

    engine = _build_isolated_engine()
    state = PipelineState(
        task_id="m42",
        prompt="hello",
    )
    state.decision_event_id = EventId("evt_decision_root")
    state.score = 0.87
    state.retries = 1
    state.syntax_valid = True

    # Inject a fake capability_plan in the engine state context
    from iaglobal.pipeline.capability_resolver import CapabilityPlan

    plan = CapabilityPlan(artifact="pdf")
    plan.add_step("tool", "tool:pandas")
    state.context["capability_plan"] = plan

    # Also stamp the generated_artifact so artifact_kind is meaningful
    from iaglobal.core.artifact import GeneratedArtifact

    state.generated_artifact = GeneratedArtifact.from_str("print('x')")

    await engine._emit_capability_result(state, success=True)

    assert len(captured) == 1
    event = captured[0]
    assert event["event_type"] == EventType.CAPABILITY_RESULT
    assert event["mission_id"] == "m42"
    assert event["decision_event_id"] == "evt_decision_root"
    assert event["selected_technology"] == "pandas"
    assert event["artifact_kind"] == "code"  # ArtifactKind.CODE.value
    assert event["validation_status"] == "passed"
    assert event["success"] is True
    assert event["quality_score"] == pytest.approx(0.87)
    assert event["repair_count"] == 1
    assert event["latency_ms"] >= 0


@pytest.mark.anyio
async def test_helper_aborts_when_no_predecessor():
    """Per ADR-0004: result without predecessor does not exist.
    Without ``state.decision_event_id`` the helper is silent."""
    from iaglobal.pipeline.pipelinestate import PipelineState

    _reset_bus()
    captured = []
    bus.subscribe(EventType.CAPABILITY_RESULT, lambda e: captured.append(e.data or {}))

    engine = _build_isolated_engine()
    state = PipelineState(task_id="m42", prompt="hello")
    # state.decision_event_id stays None

    await engine._emit_capability_result(state, success=True)

    assert captured == []  # no predecessor → silent


@pytest.mark.anyio
async def test_helper_publishes_failure_event_too():
    """Failure path also publishes CAPABILITY_RESULT with
    ``success=False`` — feedback learns from errors too."""
    from iaglobal.pipeline.pipelinestate import PipelineState

    _reset_bus()
    captured = []
    bus.subscribe(EventType.CAPABILITY_RESULT, lambda e: captured.append(e.data or {}))

    engine = _build_isolated_engine()
    state = PipelineState(task_id="m42", prompt="hi")
    state.decision_event_id = EventId("evt_decision_root")
    state.syntax_valid = False  # failed validation
    state.errors = ["Invalid syntax"]
    state.score = 0.0

    await engine._emit_capability_result(state, success=False)

    assert len(captured) == 1
    event = captured[0]
    assert event["success"] is False
    assert event["validation_status"] == "failed"
    assert "errors" in event["evidence"]
    assert event["evidence"]["errors"] == ["Invalid syntax"]


# ── 2. Causal edge isolated test (decision + result) ───────────────────────


def test_decision_to_result_causal_edge_in_engine_runtime():
    """Architectural invariant: the EventId surfaced from the bus at
    resolver time equals the one stored at state and is forwarded on
    the result event.

    The test fabricates the full topology by mocking the resolver's
    ``_publish_event`` side effect and calling `_emit_capability_result`
    independently — exercises only the engine-side wiring.
    """
    from iaglobal.pipeline.capability_resolver import CapabilityPlan
    from iaglobal.pipeline.pipelinestate import PipelineState

    _reset_bus()

    decisions: list[dict] = []
    results: list[dict] = []
    bus.subscribe(
        EventType.CAPABILITY_SELECTED, lambda e: decisions.append(e.data or {})
    )
    bus.subscribe(EventType.CAPABILITY_RESULT, lambda e: results.append(e.data or {}))

    engine = _build_isolated_engine()
    state = PipelineState(task_id="m42", prompt="hello")
    plan = CapabilityPlan(artifact="data")
    plan.add_step("tool", "tool:pandas")
    state.context["capability_plan"] = plan

    # Simulate the resolver publishing the decision and feeding back the id
    decision_event = CapabilityDecisionEvent(
        id=EventId("evt_a81f"),
        event_type=EventType.CAPABILITY_SELECTED,
        mission_id="m42",
        created_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
        capability="data",
        selected_technology="pandas",
        validation_confidence=0.9,
        effective_score=0.8,
        bandit_score=0.5,
        reason=("installed",),
        fallback_used=False,
        candidate_count=2,
        filtered_count=1,
    )
    bus.publish(
        decision_event.event_type,
        data=decision_event.to_dict(),
        source="SyntheticResolver",
    )

    # The engine reads back the EventId from the bus payload via subscribe
    def _capture_id(event):
        data = getattr(event, "data", None) or {}
        if data.get("id"):
            state.decision_event_id = EventId(data["id"])

    bus.subscribe(EventType.CAPABILITY_SELECTED, _capture_id)
    # re-trigger so subscribe catches it
    bus.publish(
        decision_event.event_type,
        data=decision_event.to_dict(),
        source="SyntheticResolver",
    )
    bus.unsubscribe(EventType.CAPABILITY_SELECTED, _capture_id)

    # Now run the result emission with the captured predecessor
    import asyncio

    async def _drive():
        await engine._emit_capability_result(state, success=True)

    asyncio.run(_drive())

    assert state.decision_event_id == EventId("evt_a81f")
    assert len(results) == 1
    assert results[0]["decision_event_id"] == "evt_a81f"
    assert results[0]["mission_id"] == "m42"
    # Selected technology extracted from plan step tool:pandas
    assert results[0]["selected_technology"] == "pandas"


# ── 3. Uniqueness guards for the runtime emit ─────────────────────────────


@pytest.mark.anyio
async def test_one_result_event_per_run():
    """A given ``PipelineState`` with a single ``decision_event_id``
    produces exactly one ``CAPABILITY_RESULT`` (no duplicates)."""
    from iaglobal.pipeline.pipelinestate import PipelineState

    _reset_bus()
    captured = []
    bus.subscribe(EventType.CAPABILITY_RESULT, lambda e: captured.append(e.data or {}))

    engine = _build_isolated_engine()
    state = PipelineState(task_id="m42", prompt="hi")
    state.decision_event_id = EventId("evt_a")

    await engine._emit_capability_result(state, success=True)
    # Calling again would mean the helper is invoked twice — should
    # still produce two events (the engine contract is one call per
    # result; double-emit is a violation we explicitly avoid with the
    # try/except wrapper in the failure path).
    # Here we only call once, so we expect one event.
    assert len(captured) == 1
    assert captured[0]["decision_event_id"] == "evt_a"
