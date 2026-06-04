# iaglobal/providers/provider_scorer.py

def score_provider(state, task_type: str, estimated_tokens: int):
    """
    Score híbrido:
    - confiabilidade
    - velocidade
    - adequação ao tipo de tarefa
    """

    base = state.success_rate()

    latency_penalty = state.avg_latency()

    cooldown_penalty = 0 if state.is_available(provider) else 0.5

    return base - latency_penalty * 0.2 - cooldown_penalty
