# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Evolution agentes — committee, trigger e pipeline updater.

⚠️ DEPRECATED — substituído pelo módulo iaglobal/evolution/metacognition/.
Manter apenas para compatibilidade reversa.
"""

import warnings
from typing import Any, Dict, List

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.agents.evolution_agent")

warnings.warn(
    "iaglobal.agents.evolution_agent está obsoleto. "
    "Use iaglobal.evolution.metacognition no lugar.",
    DeprecationWarning,
    stacklevel=2,
)


class EvolutionCommitteeAgent(AgentBase):
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


class EvolutionTriggerAgent(AgentBase):
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


class PipelineUpdaterAgent(AgentBase):
    def update(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        evolution_result = context.get("evolution_result", {})
        changes = evolution_result.get("suggested_changes", [])
        if not changes:
            changes = [
                {"node": "coder", "action": "tune", "param": "temperatura", "value": 0.4},
                {"node": "critic", "action": "tune", "param": "score_threshold", "value": 65},
            ]
        return changes
