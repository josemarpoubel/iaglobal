# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from iaglobal.knowledge.capability import Capability, CapabilityGraph
from iaglobal.knowledge.constraints import (
    ConstraintExtractor,
    ConstraintSet,
)
from iaglobal.knowledge.resolver.capability_resolver import (
    CapabilityResolution,
    CapabilityResolver,
)
from iaglobal.knowledge.technology import TechnologyDescriptor, TechnologyGraph
from iaglobal.knowledge.validator.protocol import TechnologyValidator

logger = logging.getLogger(__name__)


@dataclass
class TechnologyDecision:
    """Final decision produced by the KnowledgeEngine.

    Carries the trace from intent to selection, ready to be consumed
    by the Planner/Bandit and ultimately by the executor.
    """

    capability: str
    technology: TechnologyDescriptor
    constraint_set: ConstraintSet
    resolution: CapabilityResolution
    bandit_arm: str
    bandit_confidence: float


class KnowledgeEngine:
    """Facade that wires the full Knowledge Intelligence pipeline.

    Flow::

        resolve(capability, mission_text)
          │
          ├── ConstraintExtractor        → constraints
          ├── CapabilityResolver         → candidates + validated
          ├── filter_technologies        → constraint filter
          ├── TechnologyValidator        → evidence
          └── BanditPolicy.select_arm()  → final selection
    """

    def __init__(
        self,
        cap_graph: CapabilityGraph,
        tech_graph: TechnologyGraph,
        validator: TechnologyValidator,
        bandit: Optional[object] = None,
        extractor: Optional[ConstraintExtractor] = None,
    ) -> None:
        self._cap_graph = cap_graph
        self._tech_graph = tech_graph
        self._validator = validator
        self._extractor = extractor or ConstraintExtractor()
        self._bandit = bandit
        self._resolver = CapabilityResolver(
            cap_graph=cap_graph,
            tech_graph=tech_graph,
            validator=validator,
            extractor=self._extractor,
        )

    async def resolve(
        self,
        capability: Capability,
        mission: str = "",
        mission_id: str = "",
    ) -> TechnologyDecision:
        """Run the full pipeline and return the selected technology.

        Args:
            capability: The capability to resolve.
            mission: Optional prompt text for constraint extraction.
            mission_id: Optional task/contract identifier forwarded to
                the emitted ``CapabilityDecisionEvent``.

        Returns:
            A ``TechnologyDecision`` with the full trace.
        """
        constraints = self._extractor.extract(mission) if mission else ConstraintSet()

        resolution = await self._resolver.resolve(
            capability, mission=mission, mission_id=mission_id
        )

        # Final selection via Bandit if available, else use resolver's selection
        if self._bandit is not None and resolution.validated:
            arms = [t.name for t, r in resolution.validated if r.success]
            if arms:
                arm = self._bandit.select_arm(arms)
                selected = next(
                    (t for t, r in resolution.validated if t.name == arm),
                    resolution.selected,
                )
                if selected is not None:
                    # Feed validation confidence as reward signal
                    for t, r in resolution.validated:
                        if t.name == arm:
                            self._bandit.update_reward(arm, r.confidence, ivm=1.0)
                            break
                    return TechnologyDecision(
                        capability=capability.id,
                        technology=selected,
                        constraint_set=constraints,
                        resolution=resolution,
                        bandit_arm=arm,
                        bandit_confidence=next(
                            (
                                r.confidence
                                for t, r in resolution.validated
                                if t.name == arm
                            ),
                            0.0,
                        ),
                    )

        if resolution.selected is None:
            raise RuntimeError(
                f"KnowledgeEngine: no candidate survived validation for '{capability.id}'"
            )

        return TechnologyDecision(
            capability=capability.id,
            technology=resolution.selected,
            constraint_set=constraints,
            resolution=resolution,
            bandit_arm=resolution.selected.name,
            bandit_confidence=next(
                (
                    r.confidence
                    for t, r in resolution.validated
                    if t.name == resolution.selected.name
                ),
                0.0,
            ),
        )
