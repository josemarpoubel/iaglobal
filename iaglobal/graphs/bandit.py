# iaglobal/graphs/bandit.py

import secrets
from typing import List, Tuple
from iaglobal.graphs.credit import CreditAssignmentEngine


class BanditPolicy:
    """
    🧠 Escolhe/ordena modelos baseado em histórico (ε-greedy)
    Usa secrets em vez de random para evitar viés de seed previsível
    em ambientes de produção concorrentes.
    """

    def __init__(self, credit: CreditAssignmentEngine):
        self.credit = credit

    def select_model(self, node, strategy, candidates: List[str]) -> str:
        scored = []

        for model in candidates:
            score = self.credit.score(node, model, strategy)
            scored.append((score, model))

        scored.sort(reverse=True)

        # ε-greedy: 80% explora o melhor score, 20% explora aleatório
        if secrets.randbelow(100) < 80:
            return scored[0][1]

        return secrets.choice(candidates)

    def rank_models(self, node, strategy, candidates: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """
        Retorna a lista completa de (provider, model) ordenada por score histórico.
        Útil para fallback chain: tenta o melhor primeiro, depois os demais em ordem.
        """
        scored = []
        for provider, model in candidates:
            score = self.credit.score(node, model, strategy)
            scored.append((score, provider, model))

        scored.sort(reverse=True)
        return [(p, m) for _, p, m in scored]
