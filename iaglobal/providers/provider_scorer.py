# iaglobal/providers/provider_scorer.py

from iaglobal.utils.logger import logger


def score_provider(state, task_type: str, estimated_tokens: int):
    """
    Score híbrido:
    - confiabilidade
    - velocidade
    - adequação ao tipo de tarefa
    """

    base = state.success_rate()

    latency_penalty = state.avg_latency()

    cooldown_penalty = 0.0

    # state tem is_available se for ProviderStats
    if hasattr(state, "is_available") and callable(getattr(state, "is_available")):
        cooldown_penalty = 0 if state.is_available("") else 0.5

    score = base - latency_penalty * 0.2 - cooldown_penalty
    logger.info(
        "[SCORER] score_provider base=%.3f latency_penalty=%.3f cooldown_penalty=%.3f score=%.3f",
        base,
        latency_penalty,
        cooldown_penalty,
        score,
    )
    return score
