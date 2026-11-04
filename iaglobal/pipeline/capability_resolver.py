# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

# iaglobal/pipeline/capability_resolver.py
"""
Capability Resolver — mapeia missão para capacidades, skills e ferramentas.

DoisResolvedores:

* :class:`CapabilityResolver` — heurístico legado (``_SKILL_MAP`` /
  ``_TOOL_MAP``). Conservado para fallback e comparação de telemetria.
* :class:`PipelineCapabilityResolver` — bridge que tenta o
  ``KnowledgeEngine`` (evidence-aware) primeiro e cai no legado quando o
  engine não resolve. Emite ``CapabilityDecisionEvent`` em ambos os
  caminhos.

A telemetria é a fonte da verdade: cada decisão é publicada no
barramento de eventos antes do plano ser devolvido, para que
``EventStore``, ``CausalEngine`` e o feedback loop do Bandit possam
reconstruir cada escolha.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

from iaglobal.pipeline.mission import MissionContract


StepKind = Literal["template", "skill", "tool", "knowledge", "search", "llm"]


@dataclass
class PlanStep:
    kind: StepKind
    name: str
    params: Dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"PlanStep({self.kind}, {self.name})"


@dataclass
class CapabilityPlan:
    artifact: str = "unknown"
    steps: List[PlanStep] = field(default_factory=list)
    rejection_reason: str = ""

    def add_step(self, kind: StepKind, name: str, **params: object) -> None:
        self.steps.append(PlanStep(kind=kind, name=name, params=params))

    def is_empty(self) -> bool:
        return not self.steps

    def __repr__(self) -> str:
        steps_str = ", ".join(repr(s) for s in self.steps)
        return f"CapabilityPlan(artifact={self.artifact}, steps=[{steps_str}])"


class CapabilityResolver:
    """Resolve uma missão em um plano de capacidades prescritivo (steps ordenados)."""

    _SKILL_MAP = {
        "frontend": {"html", "css", "javascript", "typescript", "react", "vue"},
        "backend": {"python", "flask", "fastapi", "django", "node", "go"},
        "pdf": {"fpdf", "fpdf2", "reportlab", "jspdf", "pdfkit"},
        "database": {"sqlite", "postgres", "sqlalchemy"},
        "ui": {"tkinter", "pyqt", "html", "css"},
    }

    _TOOL_MAP = {
        "template:webapp": {"web_application", "frontend"},
        "tool:pdf": {"pdf_generation"},
        "skill:frontend": {"frontend", "ui"},
    }

    def resolve(self, contract: MissionContract) -> CapabilityPlan:
        if not contract:
            return CapabilityPlan(artifact="unknown")

        plan = CapabilityPlan(artifact=contract.artifact)

        if contract.artifact != "unknown":
            # Passo 1: templates — base estrutural do artefato
            if contract.requires_ui:
                plan.add_step("template", "web_app_base")
                plan.add_step("skill", "frontend")

            if contract.requires_persistence:
                plan.add_step("skill", "database")

            if contract.requires_api:
                plan.add_step("skill", "backend")

            # Passo 2: tools — recursos específicos detectados nas features
            if "pdf_generation" in contract.required_features:
                plan.add_step("tool", "tool:pdf")
                plan.add_step("skill", "pdf")

            if "dark_theme" in contract.required_features:
                plan.add_step("template", "dark_theme_patch")

            if "form_input" in contract.required_features:
                plan.add_step("template", "form_handler_base")

            if "infinite_scroll" in contract.required_features:
                plan.add_step("template", "infinite_scroll_patch")

        # Passo 3: conhecimento — consultas determinísticas
        plan.add_step("knowledge", "domain_guidelines")

        # Passo 4: busca — contexto da web se disponível
        plan.add_step("search", "web_context")

        # Passo 5: LLM — preenchimento do que não foi resolvido acima
        for llm_task in self._derive_llm_tasks(contract):
            plan.add_step("llm", llm_task)

        return plan

    def _derive_llm_tasks(self, contract: MissionContract) -> List[str]:
        tasks = []
        if contract.requires_ui:
            tasks.append("compose_ui")
        if "pdf_generation" in contract.required_features:
            tasks.append("integrate_pdf")
        if contract.requires_persistence:
            tasks.append("setup_persistence")
        if contract.requires_api:
            tasks.append("build_api")
        if not tasks:
            tasks.append("generate_code")
        return tasks


# ── Feature / Artifact → capability id (bridge catalogue) ─────────────────


_FEATURE_TO_CAPABILITY: Dict[str, str] = {
    "pdf_generation": "pdf_generation",
    "dark_theme": "ui_theming",
    "form_input": "form_handling",
    "infinite_scroll": "infinite_scroll",
    "data_analysis": "data_analysis",
    "image_processing": "image_processing",
}


_ARTIFACT_TO_CAPABILITY: Dict[str, str] = {
    "pdf": "pdf_generation",
    "api": "rest_api",
    "web": "web_application",
    "cli": "cli_application",
    "spreadsheet": "spreadsheet",
    "html": "web_application",
}


class PipelineCapabilityResolver:
    """Bridge between ``MissionContract`` and ``KnowledgeEngine``.

    Two-phase resolution:

    1. **Knowledge Engine** — evidence-aware pipeline (constraints,
       validation, bandit). The inner :class:`CapabilityResolver` emits
       a ``CapabilityDecisionEvent`` on its own.
    2. **Legacy fallback** — ``_SKILL_MAP`` / ``_TOOL_MAP`` heuristics
       when the engine returns no selection. Emits a fallback
       ``CapabilityDecisionEvent`` here (no underlying resolver to do
       it).

    Telemetry is always published on
    :data:`EventType.CAPABILITY_SELECTED` so consumers can correlate
    ``mission → decision → outcome``.
    """

    def __init__(
        self,
        knowledge_engine: Optional["object"] = None,
        legacy_fallback: bool = True,
    ) -> None:
        self._engine = knowledge_engine
        self._legacy = CapabilityResolver() if legacy_fallback else None

    async def resolve(
        self,
        contract: MissionContract,
        mission_text: str = "",
        mission_id: str = "",
    ) -> CapabilityPlan:
        """Resolve *contract* into a ``CapabilityPlan``.

        Tries the knowledge engine first; falls back to legacy on miss.
        Emits a ``CapabilityDecisionEvent`` describing the chosen path.
        """
        plan = CapabilityPlan(artifact=contract.artifact)

        # Phase 1 — Knowledge Engine (resolver emits via inner CapabilityResolver)
        if self._engine is not None:
            ke_plan = await self._resolve_with_engine(
                contract, mission_text, mission_id
            )
            if ke_plan is not None and not ke_plan.is_empty():
                return ke_plan

        # Phase 2 — Legacy fallback (no underlying resolver → emit here)
        if self._legacy is not None:
            legacy_plan = self._legacy.resolve(contract)
            self._publish_legacy_event(mission_id, contract)
            return legacy_plan

        return plan

    async def _resolve_with_engine(
        self,
        contract: MissionContract,
        mission_text: str,
        mission_id: str,
    ) -> Optional[CapabilityPlan]:
        """Map ``KnowledgeEngine`` output into a ``CapabilityPlan``."""

        cap = self._mission_to_capability(contract)
        if cap is None:
            return None

        try:
            decision = await self._engine.resolve(  # type: ignore[union-attr]
                cap, mission=mission_text, mission_id=mission_id
            )
        except RuntimeError:
            return None

        if not decision.resolution.has_selection:
            return None

        plan = CapabilityPlan(artifact=contract.artifact)
        plan.add_step(
            "tool",
            f"tool:{decision.technology.name}",
            evidence=str(decision.resolution.evidence)
            if decision.resolution.evidence
            else "",
        )

        legacy = CapabilityResolver()
        for llm_task in legacy._derive_llm_tasks(contract):
            plan.add_step("llm", llm_task)

        return plan

    # ── Decision telemetry ─────────────────────────────────────────────────

    def _publish_legacy_event(
        self,
        mission_id: str,
        contract: MissionContract,
    ) -> None:
        """Publish a ``CapabilityDecisionEvent`` for a legacy fallback path."""
        from datetime import datetime, timezone
        from uuid import uuid4

        from iaglobal.events.decision_event import CapabilityDecisionEvent
        from iaglobal.events.event_id import EventId
        from iaglobal.events.event_types import EventType
        from iaglobal.models.event_bus import bus

        event = CapabilityDecisionEvent(
            id=EventId(value=str(uuid4())[:8]),
            event_type=EventType.CAPABILITY_SELECTED,
            mission_id=mission_id,
            created_at=datetime.now(timezone.utc),
            capability=contract.artifact,
            selected_technology=None,
            validation_confidence=0.0,
            effective_score=0.0,
            bandit_score=0.0,
            reason=("legacy fallback",),
            fallback_used=True,
            candidate_count=0,
            filtered_count=0,
            evidence={"path": "legacy"},
        )
        bus.publish(
            event.event_type, data=event.to_dict(), source="PipelineCapabilityResolver"
        )

    @staticmethod
    def _mission_to_capability(
        contract: MissionContract,
    ) -> Optional["object"]:  # Capability
        """Map ``MissionContract`` features to a ``Capability`` id.

        Inspects ``required_features`` first; falls back to ``artifact``
        mapping. Returns ``None`` when no candidate capability can be
        inferred.
        """
        from iaglobal.knowledge.capability import Capability

        for feature in contract.required_features:
            cap_id = _FEATURE_TO_CAPABILITY.get(feature)
            if cap_id:
                return Capability(
                    id=cap_id,
                    keywords=frozenset({feature, contract.artifact}),
                )

        cap_id = _ARTIFACT_TO_CAPABILITY.get(contract.artifact)
        if cap_id:
            return Capability(
                id=cap_id,
                keywords=frozenset({contract.artifact}),
            )

        return None
