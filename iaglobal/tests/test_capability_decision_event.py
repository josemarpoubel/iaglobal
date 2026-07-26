# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Tests for CapabilityDecisionEvent emission through the pipeline.

Verifies that every resolution path (engine success, engine miss + legacy,
legacy only) publishes a CapabilityDecisionEvent with the correct trace.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from iaglobal.events import CapabilityDecisionEvent
from iaglobal.events.event_id import EventId
from iaglobal.events.event_types import EventType
from iaglobal.models.event_bus import bus


def _event(
    *,
    mission_id: str = "m1",
    capability: str = "c1",
    selected_technology: str | None = "t1",
    validation_confidence: float = 0.8,
    effective_score: float = 0.9,
    bandit_score: float = 0.0,
    reason: tuple[str, ...] = ("ok",),
    fallback_used: bool = False,
    candidate_count: int = 2,
    filtered_count: int = 1,
    selected_provider: str | None = None,
    predecessor_event_id: EventId | None = None,
    evidence: dict | None = None,
    id: EventId | None = None,
    event_type: str | None = None,
    created_at: datetime | None = None,
):
    """Helper to construct a CapabilityDecisionEvent with sensible defaults."""
    return CapabilityDecisionEvent(
        id=id or EventId("evt_test"),
        event_type=event_type or EventType.CAPABILITY_SELECTED,
        mission_id=mission_id,
        created_at=created_at or datetime(2026, 7, 25, tzinfo=timezone.utc),
        capability=capability,
        selected_technology=selected_technology,
        validation_confidence=validation_confidence,
        effective_score=effective_score,
        bandit_score=bandit_score,
        reason=reason,
        fallback_used=fallback_used,
        candidate_count=candidate_count,
        filtered_count=filtered_count,
        selected_provider=selected_provider,
        predecessor_event_id=predecessor_event_id,
        evidence=evidence or {},
    )


# ── Event dataclass ──────────────────────────────────────────────────────


class TestCapabilityDecisionEvent:
    def test_event_type_constant(self):
        """The event type matches the EventType constant."""
        assert EventType.CAPABILITY_SELECTED == "capability_selected"

    def test_event_dataclass_frozen(self):
        """CapabilityDecisionEvent is immutable."""
        e = _event()
        with pytest.raises(AttributeError):
            e.selected_technology = "t2"  # type: ignore[misc]

    def test_to_dict_includes_all_fields(self):
        e = _event(
            capability="data_analysis",
            selected_technology="pandas",
            validation_confidence=0.85,
            effective_score=0.93,
            reason=("installed", "validated"),
            candidate_count=3,
            filtered_count=2,
        )
        d = e.to_dict()
        assert d["capability"] == "data_analysis"
        assert d["selected_technology"] == "pandas"
        assert d["fallback_used"] is False
        assert "created_at" in d        # DomainEvent lineage marker
        assert d["id"] == "evt_test"     # EventId.value serialization
        assert len(d["reason"]) == 2
        assert "decision_confidence" in d

    def test_event_type_field(self):
        """event_type is a field (inherited from DomainEvent) and resets
        to whatever the publisher set."""
        e = _event(capability="c", candidate_count=0, filtered_count=0)
        assert e.event_type == EventType.CAPABILITY_SELECTED


# ── Engine path: event published on success ──────────────────────────────


class TestEnginePathPublishesEvent:
    @pytest.mark.anyio
    async def test_engine_success_publishes_capability_event(self):
        """Successful engine resolution publishes a CapabilityDecisionEvent
        with the selected technology and evidence."""
        from iaglobal.graphs.bandit import BanditPolicy
        from iaglobal.knowledge.capability import Capability, CapabilityGraph
        from iaglobal.knowledge.contracts import MaturityLevel
        from iaglobal.knowledge.engine import KnowledgeEngine
        from iaglobal.knowledge.technology import TechnologyDescriptor, TechnologyGraph
        from iaglobal.knowledge.validator.python_validator import PythonValidator
        from iaglobal.pipeline.capability_resolver import PipelineCapabilityResolver
        from iaglobal.pipeline.mission import MissionContract

        bus.reset()
        received: list[dict] = []

        def capture(event):
            received.append(event.data or {})

        bus.subscribe(EventType.CAPABILITY_SELECTED, capture)

        cap_g = CapabilityGraph()
        cap_g.register(
            Capability(
                id="data_analysis",
                keywords=frozenset({"data"}),
            )
        )
        tech_g = TechnologyGraph()
        tech_g.register(
            TechnologyDescriptor(
                name="pandas",
                supports=frozenset({"data_analysis"}),
                maturity=MaturityLevel.GOLD,
                offline=True,
            )
        )
        bp = BanditPolicy(epsilon=0.0)
        bp.weights["pandas"] = 1.0
        engine = KnowledgeEngine(
            cap_graph=cap_g,
            tech_graph=tech_g,
            validator=PythonValidator(),
            bandit=bp,
        )
        resolver = PipelineCapabilityResolver(
            knowledge_engine=engine,
            legacy_fallback=False,
        )
        contract = MissionContract(
            artifact="data",
            required_features=["data_analysis"],
        )
        await resolver.resolve(contract, mission_text="data analysis")

        assert len(received) == 1
        event = received[0]
        assert event["capability"] == "data_analysis"
        assert event["selected_technology"] == "pandas"
        assert event["fallback_used"] is False
        assert event["validation_confidence"] > 0
        assert len(event["reason"]) > 0


# ── Legacy path: event published with fallback flag ──────────────────────


class TestLegacyPathPublishesEvent:
    @pytest.mark.anyio
    async def test_legacy_fallback_publishes_event(self):
        """When engine has no matching technology, legacy fallback
        publishes a CapabilityDecisionEvent with fallback_used=True."""
        from iaglobal.knowledge.capability import CapabilityGraph
        from iaglobal.knowledge.engine import KnowledgeEngine
        from iaglobal.knowledge.technology import TechnologyGraph
        from iaglobal.knowledge.validator.python_validator import PythonValidator
        from iaglobal.pipeline.capability_resolver import PipelineCapabilityResolver
        from iaglobal.pipeline.mission import MissionContract

        bus.reset()
        received: list[dict] = []

        def capture(event):
            received.append(event.data or {})

        bus.subscribe(EventType.CAPABILITY_SELECTED, capture)

        engine = KnowledgeEngine(
            cap_graph=CapabilityGraph(),
            tech_graph=TechnologyGraph(),
            validator=PythonValidator(),
        )
        resolver = PipelineCapabilityResolver(
            knowledge_engine=engine,
            legacy_fallback=True,
        )
        contract = MissionContract(
            artifact="pdf",
            required_features=["pdf_generation"],
        )
        await resolver.resolve(contract, mission_text="")

        assert len(received) >= 1
        legacy_event = [e for e in received if e.get("fallback_used") is True]
        assert len(legacy_event) >= 1
        assert legacy_event[0]["selected_technology"] is None
        assert legacy_event[0]["reason"] == ("legacy fallback",)


# ── Engine miss without fallback: no event ───────────────────────────────


class TestEngineMissNoFallback:
    @pytest.mark.anyio
    async def test_no_event_when_no_engine_and_no_fallback(self):
        """When there is no engine and no fallback, no event is published."""
        from iaglobal.pipeline.capability_resolver import PipelineCapabilityResolver
        from iaglobal.pipeline.mission import MissionContract

        bus.reset()
        received: list[dict] = []

        def capture(event):
            received.append(event.data or {})

        bus.subscribe(EventType.CAPABILITY_SELECTED, capture)

        resolver = PipelineCapabilityResolver(
            knowledge_engine=None,
            legacy_fallback=False,
        )
        contract = MissionContract(
            artifact="pdf",
            required_features=["pdf_generation"],
        )
        await resolver.resolve(contract, mission_text="")

        assert len(received) == 0


# ── Multiple resolutions generate independent events ─────────────────────


class TestMultipleResolutions:
    @pytest.mark.anyio
    async def test_each_resolution_creates_separate_event(self):
        """Two separate resolves produce two separate events."""
        from iaglobal.knowledge.capability import Capability, CapabilityGraph
        from iaglobal.knowledge.contracts import MaturityLevel
        from iaglobal.knowledge.engine import KnowledgeEngine
        from iaglobal.knowledge.technology import TechnologyDescriptor, TechnologyGraph
        from iaglobal.knowledge.validator.python_validator import PythonValidator
        from iaglobal.pipeline.capability_resolver import PipelineCapabilityResolver
        from iaglobal.pipeline.mission import MissionContract

        bus.reset()
        received: list[dict] = []

        def capture(event):
            received.append(event.data or {})

        bus.subscribe(EventType.CAPABILITY_SELECTED, capture)

        cap_g = CapabilityGraph()
        cap_g.register(
            Capability(
                id="data_analysis",
                keywords=frozenset({"data"}),
            )
        )
        tech_g = TechnologyGraph()
        tech_g.register(
            TechnologyDescriptor(
                name="pandas",
                supports=frozenset({"data_analysis"}),
                maturity=MaturityLevel.GOLD,
                offline=True,
            )
        )
        engine = KnowledgeEngine(
            cap_graph=cap_g,
            tech_graph=tech_g,
            validator=PythonValidator(),
        )
        resolver = PipelineCapabilityResolver(
            knowledge_engine=engine,
            legacy_fallback=False,
        )
        contract = MissionContract(
            artifact="data",
            required_features=["data_analysis"],
        )
        await resolver.resolve(contract, mission_text="data analysis")
        await resolver.resolve(contract, mission_text="data analysis")

        assert len(received) == 2
        assert received[0]["capability"] == received[1]["capability"]
        assert received[0]["created_at"] != received[1]["created_at"]
