# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Telemetry contract: the lower ``CapabilityResolver.resolve`` (in
``knowledge/resolver/capability_resolver.py``) is the canonical emission
point for ``CapabilityDecisionEvent``. Downstream consumers — store,
causal engine, bandit feedback — rely on this contract.

Per architecture rule:

* KnowledgeEngine answers "what exists?"
* Resolver answers "what was chosen?"
* Telemetry lives at the decision boundary, not at the catalogue.

KNOWN ISSUES (debt):

* ``tests/test_knowledge_integration.py::TestKnowledgeEngineIntegration
  ::test_bandit_receives_validation_signal`` flakes when run after
  ``test_pipeline_e2e_integration.py::test_pipeline_engine_chama_select_model_corretamente``
  due to BanditPolicy singleton state pollution. Pre-existing — not
  caused by this telemetry contract. Future work:
  ``tests/test_event_bus_isolation.py`` should guarantee bus reset
  between tests.
"""

from __future__ import annotations

import pytest

from iaglobal.events import CapabilityDecisionEvent
from iaglobal.events.event_types import EventType
from iaglobal.knowledge.capability import Capability, CapabilityGraph
from iaglobal.knowledge.contracts import MaturityLevel
from iaglobal.knowledge.technology import TechnologyDescriptor, TechnologyGraph
from iaglobal.knowledge.validator.protocol import TechnologyValidationResult
from iaglobal.knowledge.validator.python_validator import PythonValidator
from iaglobal.pipeline.mission import MissionContract


class _MockValidator:
    ecosystem = "python"

    def __init__(self, results: dict[str, TechnologyValidationResult]) -> None:
        self._results = results

    async def validate(self, technology, required_version=None):
        return self._results.get(
            technology.name,
            TechnologyValidationResult(available=False, importable=False),
        )


@pytest.mark.anyio
async def test_resolver_emits_capability_decision_event_with_mission_id():
    """Successful resolution publishes a CapabilityDecisionEvent with the
    mission_id forwarded and the chosen technology populated."""
    from iaglobal.knowledge.resolver.capability_resolver import CapabilityResolver
    from iaglobal.models.event_bus import bus

    bus.reset()
    received: list[dict] = []

    def capture(event):
        received.append(event.data or {})

    bus.subscribe(EventType.CAPABILITY_SELECTED, capture)

    cap_g = CapabilityGraph()
    cap_g.register(Capability(id="data_analysis", keywords=frozenset({"data"})))
    tech_g = TechnologyGraph()
    tech_g.register(
        TechnologyDescriptor(
            name="pandas",
            supports=frozenset({"data_analysis"}),
            maturity=MaturityLevel.GOLD,
            offline=True,
        )
    )

    validator = _MockValidator(
        {
            "pandas": TechnologyValidationResult(
                available=True, importable=True, confidence=0.85
            ),
        }
    )
    resolver = CapabilityResolver(
        cap_graph=cap_g, tech_graph=tech_g, validator=validator
    )

    cap = cap_g.get("data_analysis")
    resolution = await resolver.resolve(
        cap, mission="data analysis", mission_id="mission-xyz"
    )

    assert resolution.has_selection
    assert len(received) == 1
    event = received[0]
    assert event["mission_id"] == "mission-xyz"
    assert event["capability"] == "data_analysis"
    assert event["selected_technology"] == "pandas"
    assert event["fallback_used"] is False
    assert event["validation_confidence"] == pytest.approx(0.85)
    assert event["candidate_count"] == 1
    assert event["filtered_count"] == 1
    assert "decision_confidence" in event
    assert event["decision_confidence"] > 0


@pytest.mark.anyio
async def test_resolver_emits_event_even_when_no_selection():
    """When no technology survives, the resolver still emits so observers
    see the empty decision (zero evidence)."""
    from iaglobal.knowledge.resolver.capability_resolver import CapabilityResolver
    from iaglobal.models.event_bus import bus

    bus.reset()
    received: list[dict] = []

    def capture(event):
        received.append(event.data or {})

    bus.subscribe(EventType.CAPABILITY_SELECTED, capture)

    cap_g = CapabilityGraph()
    cap_g.register(Capability(id="pdf_generation"))
    resolver = CapabilityResolver(
        cap_graph=cap_g,
        tech_graph=TechnologyGraph(),
        validator=_MockValidator({}),
    )

    await resolver.resolve(cap_g.get("pdf_generation"), mission_id="m-empty")

    assert len(received) == 1
    event = received[0]
    assert event["mission_id"] == "m-empty"
    assert event["selected_technology"] is None
    assert event["fallback_used"] is False
    assert event["candidate_count"] == 0


@pytest.mark.anyio
async def test_resolver_event_carries_evidence_dict():
    """The event exposes an evidence dict carrying per-tech validation
    results for downstream causal-engine reconstruction."""
    from iaglobal.knowledge.resolver.capability_resolver import CapabilityResolver
    from iaglobal.models.event_bus import bus

    bus.reset()
    received: list[dict] = []

    def capture(event):
        received.append(event.data or {})

    bus.subscribe(EventType.CAPABILITY_SELECTED, capture)

    cap_g = CapabilityGraph()
    cap_g.register(Capability(id="data_analysis"))
    tech_g = TechnologyGraph()
    tech_g.register(
        TechnologyDescriptor(
            name="pandas",
            supports=frozenset({"data_analysis"}),
            maturity=MaturityLevel.GOLD,
        )
    )
    validator = _MockValidator(
        {
            "pandas": TechnologyValidationResult(
                available=True, importable=True, confidence=0.9
            )
        }
    )
    resolver = CapabilityResolver(
        cap_graph=cap_g, tech_graph=tech_g, validator=validator
    )

    await resolver.resolve(cap_g.get("data_analysis"), mission_id="m-evidence")

    event = received[0]
    assert "evidence" in event
    assert isinstance(event["evidence"], dict)
    assert "validation_results" in event["evidence"]
    assert event["evidence"]["validation_results"][0]["name"] == "pandas"


# ── Immutability of the decision trace ────────────────────────────────────


def test_event_evidence_is_read_only_mapping():
    """The ``evidence`` mapping is wrapped in ``MappingProxyType`` —
    the frozen-dataclass slots are protected, but the *content* would
    still be mutable if ``evidence`` were a plain dict. Wrapping it
    guarantees that consumers cannot silently mutate the trace after
    emission.
    """
    from types import MappingProxyType

    e = CapabilityDecisionEvent(
        mission_id="m1",
        capability="c",
        selected_technology="t",
        validation_confidence=0.5,
        effective_score=0.5,
        bandit_score=0.0,
        reason=("ok",),
        fallback_used=False,
        candidate_count=1,
        filtered_count=1,
        evidence={"k": "v"},
    )
    assert isinstance(e.evidence, MappingProxyType)
    import pytest as _pytest

    with _pytest.raises(TypeError):
        e.evidence["injected"] = "value"  # type: ignore[index]


def test_event_decision_confidence_is_aggregate():
    """``decision_confidence`` is the spec-aligned aggregate (40%
    validation + 30% effective + 30% bandit), not a single raw signal.
    """
    e = CapabilityDecisionEvent(
        mission_id="m1",
        capability="c",
        selected_technology="t",
        validation_confidence=0.8,
        effective_score=0.6,
        bandit_score=0.3,
        reason=("ok",),
        fallback_used=False,
        candidate_count=1,
        filtered_count=1,
    )
    # 0.8*0.4 + 0.6*0.3 + 0.3*0.3 = 0.32 + 0.18 + 0.09 = 0.59
    assert e.decision_confidence == pytest.approx(0.59)
    assert e.to_dict()["decision_confidence"] == e.decision_confidence


# ── Uniqueness guard: one decision = exactly one event ────────────────────


@pytest.mark.anyio
async def test_one_event_per_resolution_engine_path():
    """Knowledge engine path: a single ``resolver.resolve`` call must
    emit exactly one ``CAPABILITY_SELECTED`` event — never zero or two.
    """
    from iaglobal.knowledge.resolver.capability_resolver import CapabilityResolver
    from iaglobal.models.event_bus import bus

    bus.reset()
    received: list[dict] = []

    def capture(event):
        received.append(event.data or {})

    bus.subscribe(EventType.CAPABILITY_SELECTED, capture)

    cap_g = CapabilityGraph()
    cap_g.register(Capability(id="data_analysis"))
    tech_g = TechnologyGraph()
    tech_g.register(
        TechnologyDescriptor(
            name="pandas",
            supports=frozenset({"data_analysis"}),
            maturity=MaturityLevel.GOLD,
        )
    )
    validator = _MockValidator(
        {
            "pandas": TechnologyValidationResult(
                available=True, importable=True, confidence=0.85
            )
        }
    )
    resolver = CapabilityResolver(
        cap_graph=cap_g, tech_graph=tech_g, validator=validator
    )

    await resolver.resolve(cap_g.get("data_analysis"), mission_id="m-once")

    assert len(received) == 1, (
        f"expected exactly one event, got {len(received)} — "
        "engine path must not double-emit"
    )


@pytest.mark.anyio
async def test_one_event_per_resolution_legacy_path():
    """Legacy fallback: ``PipelineCapabilityResolver`` must publish
    exactly one fallback event per call to ``resolve``.
    """
    from iaglobal.models.event_bus import bus
    from iaglobal.pipeline.capability_resolver import PipelineCapabilityResolver

    bus.reset()
    received: list[dict] = []

    def capture(event):
        received.append(event.data or {})

    bus.subscribe(EventType.CAPABILITY_SELECTED, capture)

    resolver = PipelineCapabilityResolver(knowledge_engine=None, legacy_fallback=True)
    contract = MissionContract(artifact="pdf", required_features=["pdf_generation"])
    await resolver.resolve(contract, mission_id="m-legacy")

    fallback = [e for e in received if e.get("fallback_used") is True]
    assert len(fallback) == 1, (
        f"expected exactly one fallback event, got {len(fallback)} — "
        "bridge must not double-emit"
    )
    assert len(received) == 1


@pytest.mark.anyio
async def test_no_double_emit_when_bridge_routes_through_engine():
    """When the bridge's engine path succeeds, the lower resolver emits
    the event; the bridge MUST NOT publish a second one. Otherwise the
    contract breaks ("one decision = one event").
    """
    from iaglobal.graphs.bandit import BanditPolicy
    from iaglobal.knowledge.engine import KnowledgeEngine
    from iaglobal.models.event_bus import bus
    from iaglobal.pipeline.capability_resolver import PipelineCapabilityResolver
    from iaglobal.knowledge.validator.python_validator import PythonValidator

    bus.reset()
    received: list[dict] = []

    def capture(event):
        received.append(event.data or {})

    bus.subscribe(EventType.CAPABILITY_SELECTED, capture)

    cap_g = CapabilityGraph()
    cap_g.register(Capability(id="data_analysis", keywords=frozenset({"data"})))
    tech_g = TechnologyGraph()
    tech_g.register(
        TechnologyDescriptor(
            name="pandas",
            supports=frozenset({"data_analysis"}),
            maturity=MaturityLevel.GOLD,
            offline=True,
        )
    )
    bandit = BanditPolicy(epsilon=0.0)
    bandit.weights["pandas"] = 1.0
    engine = KnowledgeEngine(
        cap_graph=cap_g,
        tech_graph=tech_g,
        validator=PythonValidator(),
        bandit=bandit,
    )
    resolver = PipelineCapabilityResolver(
        knowledge_engine=engine,
        legacy_fallback=True,
    )
    contract = MissionContract(
        artifact="data",
        required_features=["data_analysis"],
    )
    await resolver.resolve(contract, mission_text="data analysis")

    assert len(received) == 1, (
        f"expected exactly one event from engine+bridge, got {len(received)} — "
        "double emission would break the uniqueness contract"
    )
    assert received[0]["fallback_used"] is False
