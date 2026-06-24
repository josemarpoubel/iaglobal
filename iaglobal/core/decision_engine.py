# 📁 iaglobal/core/decision_engine.py

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import time


@dataclass
class Decision:
    agent: str
    model: str
    score: float
    reason: str


class DecisionEngine:
    """
    🧠 Motor cognitivo de decisão do Orchestrator.
    Usa BanditPolicy como fonte de verdade para scores de modelo.
    """

    def __init__(self, bandit: Optional[Any] = None):
        self._bandit = bandit
        self.agent_weights = {
            "dev_fast": 0.9,
            "dev_safe": 0.7,
            "dev_exploratory": 0.5,
        }

    # =====================================================
    # SCORE FINAL DE DECISÃO
    # =====================================================

    def score_option(self, agent: str, model: str, memory_score: float, task_complexity: float) -> float:
        agent_score = self.agent_weights.get(agent, 0.5)

        bandit_score = 0.5
        if self._bandit:
            try:
                credit_score = self._bandit.credit.score("decision", model, agent)
                metric = self._bandit._metrics_score(model) if hasattr(self._bandit, '_metrics_score') else 0.5
                from iaglobal.cognition.reputation_engine import reputation_engine
                reputation = reputation_engine.score(model)
                bandit_score = (credit_score * 0.5) + (metric * 0.25) + (reputation * 0.25)
            except Exception:
                bandit_score = 0.5

        score = (
            (agent_score * 0.3) +
            (memory_score * 0.2) +
            (task_complexity * 0.1) +
            (bandit_score * 0.4)
        )

        return score

