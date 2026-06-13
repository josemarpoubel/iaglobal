"""MethylationCycle — valida skill candidata e promove a production se score > threshold."""

import logging
from typing import Optional

from iaglobal.evolution.metabolism.homocysteine_pool import CandidateSkill, homocysteine_pool
from iaglobal.feedback.benchmark_runner import BenchmarkRunner

logger = logging.getLogger(__name__)

PRODUCTION_THRESHOLD = 0.6


class MethylationCycle:
    """Ciclo de Metilação — testa, valida e promove skills candidatas a production."""

    def __init__(self, threshold: float = PRODUCTION_THRESHOLD):
        self.threshold = threshold

    def run(self, candidate: CandidateSkill) -> bool:
        logger.info("[METHYLATION] Avaliando '%s' (score=%.2f, threshold=%.2f)",
                    candidate.skill.name, candidate.score, self.threshold)

        if candidate.score >= self.threshold:
            success = homocysteine_pool.route_to_production(candidate)
            if success:
                logger.info("[METHYLATION] '%s' PROMOVIDA a production ✓", candidate.skill.name)
            return success

        logger.info("[METHYLATION] '%s' abaixo do threshold (%.2f < %.2f) — mantendo como candidata",
                    candidate.skill.name, candidate.score, self.threshold)
        return False

    def run_with_benchmark(self, candidate: CandidateSkill, code: str) -> bool:
        signal = BenchmarkRunner.run(code, task=candidate.skill.name)
        candidate.score = signal.score
        return self.run(candidate)
