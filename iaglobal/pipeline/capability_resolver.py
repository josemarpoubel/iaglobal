# iaglobal/pipeline/capability_resolver.py
"""
Capability Resolver — mapeia missão para capacidades, skills e ferramentas.

Produz um CapabilityPlan prescritivo com steps ordenados que o PlanExecutor
interpreta sequencialmente. LLM é o último recurso, não o centro da execução.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

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
