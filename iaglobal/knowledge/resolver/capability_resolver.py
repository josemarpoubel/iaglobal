# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from iaglobal.knowledge.capability import Capability, CapabilityGraph
from iaglobal.knowledge.constraints import (
    ConstraintExtractor,
    ConstraintSet,
    filter_technologies,
)
from iaglobal.knowledge.technology import TechnologyDescriptor, TechnologyGraph
from iaglobal.knowledge.validator.protocol import (
    TechnologyValidationResult,
    TechnologyValidator,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DecisionEvidence:
    """Why the resolver chose a particular technology.

    Carries the multi-factor justification so that downstream components
    (audit, memory, repair) can explain or contest the decision.
    """

    constraints_met: bool = True
    validation_confidence: float = 0.0
    bandit_score: float = 0.0
    effective_score: float = 0.0
    reason: tuple[str, ...] = ()

    @property
    def combined_confidence(self) -> float:
        return round(
            self.validation_confidence * 0.4
            + self.bandit_score * 0.3
            + self.effective_score * 0.3,
            4,
        )


@dataclass
class CapabilityResolution:
    """Result of resolving a capability against the environment.

    Traces the entire decision pipeline: which capability was requested,
    which candidates were found, which survived constraints and validation,
    and which was ultimately selected.
    """

    capability: str
    candidates: list[TechnologyDescriptor] = field(default_factory=list)
    filtered: list[TechnologyDescriptor] = field(default_factory=list)
    validated: list[tuple[TechnologyDescriptor, TechnologyValidationResult]] = field(
        default_factory=list
    )
    selected: Optional[TechnologyDescriptor] = None
    evidence: Optional[DecisionEvidence] = None

    @property
    def has_selection(self) -> bool:
        return self.selected is not None


class CapabilityResolver:
    """Resolve a ``Capability`` to the best ``TechnologyDescriptor``.

    Pipeline:

        1. Expand capability via ``CapabilityGraph`` (include descendants)
        2. Filter by constraints extracted from the mission prompt
        3. Validate each survivor against the environment
        4. Rank by validation confidence + effective score
        5. Select the top candidate

    Boundary Rule compliant: all I/O is read-only (validator).
    """

    def __init__(
        self,
        cap_graph: CapabilityGraph,
        tech_graph: TechnologyGraph,
        validator: TechnologyValidator,
        extractor: Optional[ConstraintExtractor] = None,
    ) -> None:
        self._cap_graph = cap_graph
        self._tech_graph = tech_graph
        self._validator = validator
        self._extractor = extractor or ConstraintExtractor()

    async def resolve(
        self,
        capability: Capability,
        mission: str = "",
        mission_id: str = "",
    ) -> CapabilityResolution:
        """Run the resolution pipeline for *capability*.

        *mission* is an optional prompt used to extract environmental
        constraints (offline, artifact, runtime, etc.).

        *mission_id* is an optional task/contract identifier that gets
        forwarded to the emitted ``CapabilityDecisionEvent`` so downstream
        consumers (EventStore, Bandit feedback, episodic memory) can
        correlate the resolution trace with the originating mission.
        """
        constraints = self._extractor.extract(mission) if mission else ConstraintSet()

        # 1. Expand capability: include itself + descendants
        cap_ids = self._expand_capability(capability)

        # 2. Gather candidates from technology graph
        candidates = self._gather_candidates(cap_ids)

        # 3. Filter by constraints
        filtered = filter_technologies(candidates, constraints)

        # 4. Validate survivors
        validated: list[tuple[TechnologyDescriptor, TechnologyValidationResult]] = []
        for tech in filtered:
            result = await self._validator.validate(tech)
            validated.append((tech, result))

        # 5. Rank and select
        valid_success = [(t, r) for t, r in validated if r.success]
        selected, evidence = (
            self._select_with_evidence(valid_success) if valid_success else (None, None)
        )

        resolution = CapabilityResolution(
            capability=capability.id,
            candidates=candidates,
            filtered=filtered,
            validated=validated,
            selected=selected,
            evidence=evidence,
        )

        # 6. Telemetry — emit the resolution trace on the event bus so
        # EventStore, CausalEngine and Bandit feedback can observe it.
        # Per project rules, no print() — silent on errors (listener-side).
        self._publish_event(mission_id, resolution)

        return resolution

    # ── internal helpers ──────────────────────────────────────────────────

    def _publish_event(self, mission_id: str, resolution: CapabilityResolution) -> None:
        """Emit a ``CapabilityDecisionEvent`` describing the chosen tech.

        Emitted on the global event bus (``bus.publish``); consumer is
        :class:`DecisionEventStore`. Imports are local to keep this resolver
        free of upstream layers at construction time.
        """
        from iaglobal.events.decision_event import CapabilityDecisionEvent
        from iaglobal.models.event_bus import bus

        ev = resolution.evidence
        event = CapabilityDecisionEvent(
            mission_id=mission_id,
            capability=resolution.capability,
            selected_technology=resolution.selected.name
            if resolution.selected
            else None,
            validation_confidence=ev.validation_confidence if ev else 0.0,
            effective_score=ev.effective_score if ev else 0.0,
            bandit_score=ev.bandit_score if ev else 0.0,
            reason=ev.reason if ev else (),
            fallback_used=False,
            candidate_count=len(resolution.candidates),
            filtered_count=len(resolution.filtered),
            evidence={
                "validation_results": [
                    {"name": t.name, "success": r.success, "confidence": r.confidence}
                    for t, r in resolution.validated
                ],
            },
        )
        bus.publish(event.event_type, data=event.to_dict(), source="CapabilityResolver")

    def _expand_capability(self, cap: Capability) -> list[str]:
        """Return the capability id + all descendant ids."""
        ids = [cap.id]
        ids.extend(d.id for d in self._cap_graph.descendants(cap.id))
        return ids

    def _gather_candidates(self, cap_ids: list[str]) -> list[TechnologyDescriptor]:
        """Collect all TechnologyDescriptors that support any of the cap_ids."""
        seen: set[str] = set()
        result: list[TechnologyDescriptor] = []
        for cid in cap_ids:
            for t in self._tech_graph.candidates_for(cid):
                if t.name not in seen:
                    seen.add(t.name)
                    result.append(t)
        return result

    @staticmethod
    def _select(
        validated: list[tuple[TechnologyDescriptor, TechnologyValidationResult]],
    ) -> Optional[TechnologyDescriptor]:
        """Pick the technology with the highest combined score."""
        tech, _ = CapabilityResolver._select_with_evidence(validated)  # type: ignore[misc]
        return tech

    @staticmethod
    def _select_with_evidence(
        validated: list[tuple[TechnologyDescriptor, TechnologyValidationResult]],
    ) -> tuple[Optional[TechnologyDescriptor], Optional[DecisionEvidence]]:
        """Pick the best technology and return it with the justification."""
        if not validated:
            return None, None

        def _combined(
            item: tuple[TechnologyDescriptor, TechnologyValidationResult],
        ) -> float:
            tech, result = item
            return tech.effective_score * result.confidence

        best_tech, best_result = max(validated, key=_combined)
        reasons: list[str] = []
        if best_result.available:
            reasons.append(f"'{best_tech.name}' found in environment")
        if best_result.importable:
            reasons.append("successfully imported")
        if best_result.version_compatible:
            reasons.append(
                f"version {best_result.version_installed} satisfies requirements"
            )
        if best_result.confidence > 0.8:
            reasons.append(f"high validation confidence ({best_result.confidence})")

        evidence = DecisionEvidence(
            constraints_met=True,
            validation_confidence=best_result.confidence,
            effective_score=best_tech.effective_score,
            reason=tuple(reasons),
        )
        return best_tech, evidence
