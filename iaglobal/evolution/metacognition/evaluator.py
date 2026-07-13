import logging
from typing import Any, Dict

from iaglobal.cognition.outcome_tracker import outcome_tracker
from iaglobal.immunity.hallucination_detector import HallucinationDetector
from iaglobal.immunity.regression_detector import RegressionDetector
from iaglobal.feedback.betaine_judge import BetaineJudge

logger = logging.getLogger(__name__)


class PipelineEvaluator:
    """Avalia performance da run e produz score 0–100,
    usando dados históricos do OutcomeTracker para calibragem."""

    _regression_detector = RegressionDetector()
    _evolution_count = 0
    _last_score = 0

    @classmethod
    async def evaluate(cls, ctx: dict) -> Dict[str, Any]:
        task = ctx.get("input", {}).get("task", "")
        memory = ctx.get("memory", {})
        result = memory.get("result_agent", {}).get("output", "")
        result_len = len(str(result or ""))

        score = 50
        if result_len > 100:
            score += 10
        if result_len > 500:
            score += 10
        if result_len > 2000:
            score += 10

        validation_score_raw = memory.get("validation_score", 0)
        if isinstance(validation_score_raw, (int, float)):
            score += int(validation_score_raw * 10)

        hallucination = HallucinationDetector.analyze_node_output(
            "result_agent", result
        )
        if hallucination["hallucinating"]:
            score = max(0, score - 30)
        hallucination_count = hallucination["finding_count"]

        historical = cls._get_historical_context(task)
        if historical["avg_score"] > 0:
            score = int(score * 0.7 + historical["avg_score"] * 0.3)

        regression = cls._regression_detector.check("pipeline", score)

        judge = BetaineJudge.evaluate(str(result), task)
        betaine_overall = judge["overall"]
        score += int(betaine_overall * 20)

        previous_score = cls._last_score
        score_improved = score > previous_score if previous_score > 0 else None
        cls._last_score = score

        score = min(max(score, 0), 100)
        score = max(35, score)  # piso mínimo para nao travar evolucao na 1a execucao

        return {
            "score": score,
            "result_length": result_len,
            "task": task,
            "hallucination_score": hallucination["score"],
            "hallucination_findings": hallucination_count,
            "regression_detected": regression["regression"],
            "regression_delta": regression.get("delta", 0),
            "betaine_score": betaine_overall,
            "evolution_count": cls._evolution_count,
            "previous_score": previous_score,
            "score_improved": score_improved,
            "historical_avg_score": historical["avg_score"],
            "historical_runs": historical["total_runs"],
            "status": "evaluated",
        }

    @classmethod
    def _get_historical_context(cls, task: str) -> Dict[str, Any]:
        try:
            results = outcome_tracker.query(fingerprint=task, limit=10)
            if not results:
                return {"avg_score": 0, "total_runs": 0}
            scores = [
                r.get("success_score", 0)
                for r in results
                if r.get("success_score", -1) >= 0
            ]
            return {
                "avg_score": sum(scores) / len(scores) if scores else 0,
                "total_runs": len(results),
            }
        except Exception as e:
            logger.debug("[EVALUATOR] Histórico indisponível: %s", e)
            return {"avg_score": 0, "total_runs": 0}


async def _run_evaluator(ctx: dict) -> dict:
    return await PipelineEvaluator.evaluate(ctx)
