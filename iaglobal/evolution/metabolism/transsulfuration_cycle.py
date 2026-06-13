"""TranssulfurationCycle — converte erros recorrentes em guardrails/safety skills."""

import logging
from typing import Optional

from iaglobal.evolution.metabolism.homocysteine_pool import CandidateSkill, homocysteine_pool
from iaglobal.memory.memory_error import query_relevant_errors

logger = logging.getLogger(__name__)

GUARDRAIL_FREQUENCY_THRESHOLD = 3


class TranssulfurationCycle:
    """Ciclo de Transulfuração — erros recorrentes viram proteção."""

    def __init__(self, frequency_threshold: int = GUARDRAIL_FREQUENCY_THRESHOLD):
        self.frequency_threshold = frequency_threshold

    def run(self, candidate: CandidateSkill) -> bool:
        logger.info("[TRANSSULFURATION] Avaliando '%s' para rota de proteção", candidate.skill.name)

        try:
            errors = query_relevant_errors(candidate.source_gap or candidate.skill.name, top_k=5)
            max_freq = max((e.get("count", 1) for e in errors), default=0)
        except Exception as e:
            logger.debug("[TRANSSULFURATION] Erro ao consultar: %s", e)
            max_freq = 0

        if max_freq >= self.frequency_threshold:
            success = homocysteine_pool.route_to_guardrail(candidate)
            if success:
                logger.info("[TRANSSULFURATION] '%s' → GUARDRAIL (freq=%d ≥ threshold=%d) ✓",
                           candidate.skill.name, max_freq, self.frequency_threshold)
            return success

        logger.info("[TRANSSULFURATION] '%s' frequência insuficiente (max=%d < %d) — mantendo",
                    candidate.skill.name, max_freq, self.frequency_threshold)
        return False

    def evaluate_and_route(self, candidate: CandidateSkill) -> str:
        if candidate.score >= 0.6:
            homocysteine_pool.route_to_production(candidate)
            return "production"
        elif self.run(candidate):
            return "guardrail"
        else:
            return "undecided"
