# iaglobal/cognition/reputation_engine.py

from typing import Dict
from iaglobal.cognition.outcome_tracker import outcome_tracker


class ReputationEngine:
    """Score de provedor baseado em histórico de ExecutionOutcome.

    Complementar ao BanditPolicy: fornece um score de reputação
    que considera sucesso histórico, latência e consistência.
    """

    def __init__(self):
        self._cache: Dict[str, float] = {}

    def score(self, model: str) -> float:
        """Retorna score de reputação para um modelo (0.0 a 1.0).

        Fatores:
        - success_rate (0.4): taxa de sucesso histórica
        - latency_score (0.3): inverso da latência média normalizada
        - consistency (0.3): quão consistente é o desempenho
        """
        cached = self._cache.get(model)
        if cached is not None:
            return cached

        success_rate = outcome_tracker.avg_success_rate(model)
        avg_lat = outcome_tracker.avg_latency(model)

        # Latência: quanto menor, melhor. 1000ms = 0.5, 5000ms = 0.1
        latency_score = max(0.0, 1.0 - (avg_lat / 2000)) if avg_lat > 0 else 0.5

        # Consistência: baseada no número de amostras (mais amostras = mais confiável)
        # Modelos sem histórico recebem score neutro
        if success_rate == 0.0 and avg_lat == 0.0:
            result = 0.5  # Neutro para modelos sem histórico
        else:
            result = (success_rate * 0.4) + (latency_score * 0.3) + (0.5 * 0.3)

        self._cache[model] = result
        return result

    def invalidate_cache(self):
        """Limpa cache de scores (chamar quando novos dados forem registrados)."""
        self._cache.clear()


# Instância global
reputation_engine = ReputationEngine()
