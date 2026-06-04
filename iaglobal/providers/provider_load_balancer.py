# 📦 iaglobal/providers/provider_load_balancer.py

from iaglobal.providers.provider_registry import PROVIDERS

from iaglobal.providers.provider_scorer import score_provider

from iaglobal.providers.task_router import detect_task_type, TASK_PROVIDER_MAP

from iaglobal.providers.provider_state import ProviderState


class ProviderLoadBalancer:

    def __init__(self):
        self.state = ProviderState()

    # =====================================================
    # ESCOLHA DO MELHOR PROVIDER
    # =====================================================

    def select(self, task_type: str = "general") -> str:

        candidates = [
            "ollama",
            "nvidia",
            "groq",
            "openrouter",
            "opencode",
        ]

        best_provider = None
        best_score = -999

        for p in candidates:

            if not self.state.is_available(p):
                continue

            score = self.state.score(p)

            # bias por tipo de tarefa (primeira versão simples)
            if task_type == "coding" and p == "openrouter":
                score += 0.2

            if task_type == "fast" and p == "groq":
                score += 0.3

            if task_type == "reasoning" and p == "nvidia":
                score += 0.2

            if task_type == "fast" and p == "opencode":
                score += 0.2

            if score > best_score:
                best_score = score
                best_provider = p

        return best_provider or "ollama"

    # =====================================================
    # FEEDBACK LOOP
    # =====================================================

    def report(self, provider: str, success: bool, latency: float):
        self.state.update(provider, success, latency)


load_balancer = ProviderLoadBalancer()
