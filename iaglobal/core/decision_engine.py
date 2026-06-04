# 📁 iaglobal/core/decision_engine.py

from dataclasses import dataclass
from typing import Dict, Any, List
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
    Substitui lógica if/else espalhada.
    """

    def __init__(self):
        self.agent_weights = {
            "dev_fast": 0.9,
            "dev_safe": 0.7,
            "dev_exploratory": 0.5,
        }

        self.model_cost = {
            "ollama": 0.1,
            "nvidia": 0.5,
            "openrouter": 0.4,
            "groq": 0.3,
            "opencode": 0.2,
        }

    # =====================================================
    # SCORE FINAL DE DECISÃO
    # =====================================================

    def score_option(self, agent: str, model: str, memory_score: float, task_complexity: float) -> float:
        """
        Combina múltiplos fatores em uma decisão única.
        """

        agent_score = self.agent_weights.get(agent, 0.5)
        cost_penalty = self.model_cost.get(model.split("/")[0], 0.5)

        score = (
            (agent_score * 0.4) +
            (memory_score * 0.3) +
            (task_complexity * 0.3)
        )

        return score - cost_penalty

    # =====================================================
    # DECISION MAKER
    # =====================================================

    def decide(self, agents: List[str], models: List[str], memory_score: float, complexity: float) -> Decision:
        """
        Escolhe melhor combinação agente+modelo.
        """

        best = None

        for agent in agents:
            for model in models:

                score = self.score_option(
                    agent,
                    model,
                    memory_score,
                    complexity
                )

                if best is None or score > best.score:
                    best = Decision(
                        agent=agent,
                        model=model,
                        score=score,
                        reason=f"score={score:.3f}"
                    )

        return best
