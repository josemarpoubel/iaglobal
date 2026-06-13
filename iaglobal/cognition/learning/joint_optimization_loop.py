from dataclasses import dataclass
from typing import Dict, Any

from iaglobal.providers.provider_metrics import metrics
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.cognition.learning.classifier_memory import ClassifierMemory


@dataclass
class LearningEvent:
    model: str
    task_type: str
    complexity: str
    risk: str

    fingerprint_raw: dict | None = None
    success: bool = True
    latency: float = 0.0
    cost: float = 0.0

class JointOptimizationLoop:
    """
    🔥 Núcleo de aprendizado do sistema.

    Unifica:
    - Task understanding
    - Model selection feedback
    - Provider performance
    """

    TASK_WEIGHTS = {
        "generate": {
            "base": 1.2,
            "complexity_multiplier": {
                "low": 0.8,
                "medium": 1.2,
                "high": 1.8,
            },
        },
        "debug": {
            "base": 1.5,
            "complexity_multiplier": {
                "low": 1.0,
                "medium": 1.3,
                "high": 2.0,
            },
        },
        "explain": {
            "base": 0.8,
            "complexity_multiplier": {
                "low": 0.6,
                "medium": 0.9,
                "high": 1.1,
            },
        },
        "refactor": {
            "base": 1.4,
            "complexity_multiplier": {
                "low": 1.0,
                "medium": 1.5,
                "high": 2.2,
            },
        },
    }

    def __init__(self):

        self.credit = CreditAssignmentEngine()

        self.classifier_memory = ClassifierMemory()

    # ============================
    # ENTRY POINT DO FEEDBACK
    # ============================

    def ingest(self, event: LearningEvent):
        """
        Recebe resultado de execução e atualiza TODO o sistema.
        """

        reward = self._compute_reward(event)

        self.bandit.update_context(
            context=event.task_type,  # depois trocar por fingerprint.context_key()
            model=event.model,
            reward=reward
        )

        # 1. Atualiza credit engine (Bandit base)
        self.credit.record_from_execution(
            model=event.model,
            success=event.success,
            latency=event.latency,
            task_type=event.task_type,
            reward=reward
        )

        # 2. Atualiza métricas globais (já existe)
        # (ProviderMetrics já gravou antes — aqui só consolidamos)
        self._update_internal_learning_state(event, reward)
        
        self._update_classifier_learning(event)

    # ============================
    # REWARD FUNCTION (CÉREBRO DO SISTEMA)
    # ============================

    def _compute_reward(self, event: LearningEvent) -> float:
        task_cfg = self.TASK_WEIGHTS.get(event.task_type, {
            "base": 1.0,
            "complexity_multiplier": {
                "low": 1.0,
                "medium": 1.0,
                "high": 1.0
            }
        })

        base = task_cfg["base"]

        complexity_factor = task_cfg["complexity_multiplier"].get(
            event.complexity, 1.0
        )

        # reward bruto
        reward = base * complexity_factor

        # sucesso/falha
        reward = reward if event.success else -reward

        # penalidades contínuas
        latency_penalty = min(event.latency / 2000, 1.0)
        cost_penalty = min(event.cost * 10, 1.0)

        reward -= (0.4 * latency_penalty)
        reward -= (0.2 * cost_penalty)

        # risco amplifica impacto
        if event.risk == "high":
            reward *= 1.2

        return reward

    # ============================
    # FUTURO: AUTO-ADAPTAÇÃO
    # ============================

    def _update_internal_learning_state(self, event, reward):
        """
        Aqui entra evolução futura:
        - ajuste de classifier
        - ajuste de bandit priors
        - ajuste de routing weights
        """
        pass

    def _update_classifier_learning(self, event: LearningEvent):
        """
        Aprende se a classificação ajudou ou prejudicou o resultado.
        """

        if not event.fingerprint_raw:
            return

        classification_quality = self._estimate_classification_quality(event)

        # aqui entra aprendizado futuro (pode ser DB ou cache)
        self._store_classifier_feedback(
            fingerprint=event.fingerprint_raw,
            reward=classification_quality
        )

    def _store_classifier_feedback(self, fingerprint: dict, reward: float):

        self.classifier_memory.record(fingerprint, reward)

    def _estimate_classification_quality(self, event: LearningEvent) -> float:
        """
        Se o resultado foi bom → classificação provavelmente correta.
        Se foi ruim → classificação provavelmente errada.
        """

        base = 1.0 if event.success else -1.0

        # penaliza decisões caras/lentas mesmo se "corretas"
        latency_penalty = min(event.latency / 2000, 1.0)
        cost_penalty = min(event.cost * 10, 1.0)

        return base - (0.3 * latency_penalty) - (0.2 * cost_penalty)        
