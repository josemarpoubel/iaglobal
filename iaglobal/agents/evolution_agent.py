"""Evolution agentes — committee, trigger e pipeline updater."""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class EvolutionCommitteeAgent:
    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        report = context.get("evolution_report", {})
        score = report.get("score", 0)
        issues = report.get("issues", [])
        approved = score >= 60 and len(issues) == 0
        return {
            "approved": approved,
            "score": score,
            "suggestions": issues[:3],
            "committee_verdict": "approved" if approved else "rejected",
        }


class EvolutionTriggerAgent:
    def should_evolve(self, context: Dict[str, Any]) -> Dict[str, Any]:
        metrics = context.get("metrics", {})
        generations = metrics.get("generations", 0)
        avg_score = metrics.get("avg_score", 0)
        should = generations >= 3 or avg_score < 50
        return {
            "should_evolve": should,
            "reason": "generations >= 3" if generations >= 3 else "avg_score < 50" if avg_score < 50 else "none",
            "confidence": min(1.0, generations / 10) if generations >= 3 else min(0.5, (50 - avg_score) / 50),
        }


class PipelineUpdaterAgent:
    def update(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        evolution_result = context.get("evolution_result", {})
        changes = evolution_result.get("suggested_changes", [])
        if not changes:
            changes = [
                {"node": "coder", "action": "tune", "param": "temperatura", "value": 0.4},
                {"node": "critic", "action": "tune", "param": "score_threshold", "value": 65},
            ]
        return changes
