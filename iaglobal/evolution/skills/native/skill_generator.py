import logging
from typing import Any, Dict

from iaglobal.evolution.skills.native.skill_registry import skill_registry
from iaglobal.evolution.skills.native.skill import Skill
from iaglobal.evolution.metacognition.evolution_backlog import EvolutionBacklog
from iaglobal.metabolism.homocysteine_pool import homocysteine_pool, CandidateSkill

logger = logging.getLogger(__name__)


class MetaSkillGenerator:
    """Gera Skill template a partir de gaps identificados,
    usando política de frequency/impact/reuse gates."""

    @classmethod
    async def generate(cls, ctx: dict) -> Dict[str, Any]:
        memory = ctx.get("memory", {})
        gap_result = memory.get("gap_analyzer", {}).get("output", {})
        gaps = gap_result.get("gaps", []) if isinstance(gap_result, dict) else []
        skill_gaps = (
            gap_result.get("skill_gaps", gaps) if isinstance(gap_result, dict) else gaps
        )

        backlog = EvolutionBacklog()
        generated = []
        skipped = []

        for gap in skill_gaps:
            gap_type = gap.get("type", "unknown")
            gap_desc = gap.get("description", "")
            gap_severity = gap.get("severity", "low")

            if gap_type != "recurrent_error" and gap_type != "low_score":
                skipped.append(
                    {"description": gap_desc[:80], "reason": "tipo não elegível"}
                )
                continue

            backlog_item = backlog.add_or_update(gap)

            if not backlog.should_generate_skill(backlog_item):
                skipped.append(
                    {
                        "description": gap_desc[:80],
                        "reason": f"gates não atingidos: freq={backlog_item.get('frequency')} impact={backlog_item.get('impact')} reuse={backlog_item.get('reuse')}",
                        "backlog_item": backlog_item,
                    }
                )
                continue

            skill_name = f"auto_fix_{hash(gap_desc) % 10000:04d}"
            severity_scores = {
                "critical": 0.95,
                "high": 0.85,
                "medium": 0.70,
                "low": 0.55,
            }
            candidate_score = severity_scores.get(gap_severity, 0.55)
            skill = Skill(
                name=skill_name,
                description=f"Correção automática para: {gap_desc[:200]}",
                inputs=["task"],
                outputs=["fix_result"],
                constraints=[],
                run_fn=None,
                version="1.0.0",
                author="skill_generator",
                tags=["auto_generated", gap_severity, "metacognition"],
            )

            try:
                skill_registry.register_or_update(skill)
                candidate = CandidateSkill(
                    skill=skill,
                    score=candidate_score,
                    source_gap=gap_desc,
                )
                homocysteine_pool.add(candidate)
                generated.append(
                    {
                        "skill_name": skill_name,
                        "gap_type": gap_type,
                        "severity": gap_severity,
                        "score": candidate_score,
                    }
                )
                backlog.mark_resolved(gap_desc)
                logger.info(
                    "[SKILL-GEN] Skill '%s' registrada para gap: %s",
                    skill_name,
                    gap_desc[:80],
                )
            except Exception as e:
                logger.warning(
                    "[SKILL-GEN] Falha ao registrar skill '%s': %s", skill_name, e
                )

        return {
            "generated_skills": generated,
            "skipped_gaps": skipped,
            "count": len(generated),
            "skipped_count": len(skipped),
            "status": "generated",
        }


async def _run_skill_generator(ctx: dict) -> dict:
    return await MetaSkillGenerator.generate(ctx)
