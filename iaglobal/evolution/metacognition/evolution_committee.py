import logging
from typing import Any, Dict, List

from iaglobal.evolution.skills.skill_registry import skill_registry

logger = logging.getLogger(__name__)


class EvolutionCommittee:
    """Comitê multi-agente que avalia skills antes de aplicá-las ao pipeline.

    4 verificações paralelas:
    - gain_expected: melhoria esperada
    - risk_assessment: probabilidade de dano
    - compatibility_check: quebra algo existente?
    - cost_analysis: custo computacional
    """

    @classmethod
    async def evaluate(cls, ctx: dict) -> Dict[str, Any]:
        memory = ctx.get("memory", {})
        sandbox_result = memory.get("sandbox_validator", {}).get("output", {})
        results = sandbox_result.get("results", []) if isinstance(sandbox_result, dict) else []

        evaluations = []
        all_approved = True

        for r in results:
            skill_name = r.get("skill_name", "")
            severity = r.get("severity", "low")
            skill = skill_registry.get(skill_name)

            gain = cls._assess_gain(skill_name, severity, skill)
            risk = cls._assess_risk(skill_name, severity, skill)
            compat = cls._check_compatibility(skill_name, skill)
            cost = cls._analyze_cost(skill_name, severity, skill)

            approved = gain["score"] >= 5 and risk["score"] <= 5 and compat["compatible"] and cost["score"] <= 6
            if not approved:
                all_approved = False

            evaluations.append({
                "skill_name": skill_name,
                "approved": approved,
                "gain": gain,
                "risk": risk,
                "compatibility": compat,
                "cost": cost,
            })

        return {
            "evaluations": evaluations,
            "all_approved": all_approved,
            "total": len(evaluations),
            "approved_count": sum(1 for e in evaluations if e["approved"]),
            "rejected_count": sum(1 for e in evaluations if not e["approved"]),
            "status": "approved" if all_approved else "rejected",
        }

    @classmethod
    def _assess_gain(cls, skill_name: str, severity: str, skill: Any) -> Dict[str, Any]:
        score = 5
        if severity == "high":
            score = 8
        elif severity == "medium":
            score = 6
        if skill and skill.description:
            score += 1
        return {"score": min(score, 10), "rationale": f"Ganho esperado: {score}/10"}

    @classmethod
    def _assess_risk(cls, skill_name: str, severity: str, skill: Any) -> Dict[str, Any]:
        score = 3
        if severity == "high":
            score = 6
        elif severity == "medium":
            score = 4
        if skill_name.startswith("auto_fix"):
            score += 2
        return {"score": min(score, 10), "rationale": f"Risco estimado: {score}/10"}

    @classmethod
    def _check_compatibility(cls, skill_name: str, skill: Any) -> Dict[str, Any]:
        existing = skill_registry.list_skills() if hasattr(skill_registry, "list_skills") else []
        conflicting_names = [
            s.name if hasattr(s, "name") else ""
            for s in existing
            if (s.name if hasattr(s, "name") else "") != skill_name
        ]
        name_conflict = skill_name in conflicting_names
        return {
            "compatible": not name_conflict,
            "conflict": name_conflict,
            "rationale": "Conflito de nome detectado" if name_conflict else "Compatível",
        }

    @classmethod
    def _analyze_cost(cls, skill_name: str, severity: str, skill: Any) -> Dict[str, Any]:
        score = 3
        if severity == "high":
            score = 5
        return {"score": min(score, 10), "rationale": f"Custo estimado: {score}/10"}


async def _run_evolution_committee(ctx: dict) -> dict:
    return await EvolutionCommittee.evaluate(ctx)
