"""Self-critique mechanism for code and output evaluation."""

from typing import Dict, List, Any


class SelfCritique:
    """Evaluates its own outputs and generates critiques."""

    def __init__(self):
        self.critique_history = []

    def evaluate(self, output: str) -> Dict[str, Any]:
        """Evaluate output quality and return scored critique.

        Args:
            output: Text output to evaluate.

        Returns:
            Dict with score (0-1) and analysis fields.
        """
        lines = output.strip().splitlines() if output else []
        score = min(1.0, len(lines) / 20) if lines else 0.0
        critique = {
            "output": output,
            "score": score,
            "line_count": len(lines),
            "strengths": ["non-empty"] if output else [],
            "weaknesses": [],
        }
        if not output or len(output.strip()) < 10:
            critique["weaknesses"].append("too_short")
            score = max(0.0, score - 0.3)
        critique["score"] = round(score, 2)
        self.critique_history.append(critique)
        return critique

    def critique(self, output: Any, criteria: List[str]) -> Dict:
        """Generate a critique of output based on criteria."""
        critique = {
            "output": output,
            "criteria_evaluated": criteria,
            "strengths": [],
            "weaknesses": [],
            "score": 0.0,
        }
        self.critique_history.append(critique)
        return critique
