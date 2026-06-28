import logging
from typing import Any, Dict, List

from iaglobal.memory.memory_error import query_relevant_errors
from iaglobal.evolution.metacognition.failure_taxonomy import classify_errors

logger = logging.getLogger(__name__)


class MetaGapAnalyzer:
    """Identifica gaps baseados em erros frequentes e falhas de execução,
    classificando-os por categoria (prompt, config, modelo, infra, skill_ausente)."""

    @classmethod
    async def analyze(cls, ctx: dict) -> Dict[str, Any]:
        task = ctx.get("input", {}).get("task", "")
        evaluator_result = ctx.get("memory", {}).get("evaluator", {}).get("output", {})
        score = evaluator_result.get("score", 0) if isinstance(evaluator_result, dict) else 0

        gaps = []

        if score < 50:
            gaps.append({
                "type": "low_score",
                "severity": "high",
                "description": "Score geral abaixo de 50 — revisar qualidade da execução",
            })

        try:
            errors = query_relevant_errors(task, top_k=5)
            classified = classify_errors(errors)
            for err in classified:
                tax = err.get("taxonomy", {})
                gaps.append({
                    "type": "recurrent_error",
                    "severity": "medium",
                    "description": err.get("error", ""),
                    "count": err.get("count", 1),
                    "category": tax.get("category", "unknown"),
                    "taxonomy_confidence": tax.get("confidence", 0),
                })
        except Exception as e:
            logger.debug("[GAP] query_relevant_errors failed: %s", e)

        skill_gaps = [g for g in gaps if g.get("category", "skill_ausente") == "skill_ausente" or g.get("type") == "low_score"]
        other_gaps = [g for g in gaps if g not in skill_gaps]

        return {
            "gaps": gaps,
            "skill_gaps": skill_gaps,
            "other_gaps": other_gaps,
            "gap_count": len(gaps),
            "skill_gap_count": len(skill_gaps),
            "other_gap_count": len(other_gaps),
            "status": "analyzed",
        }


async def _run_gap_analyzer(ctx: dict) -> dict:
    return await MetaGapAnalyzer.analyze(ctx)
