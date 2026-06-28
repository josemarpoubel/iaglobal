"""UserFeedbackCollector — coleta feedback do usuário via CLI."""

import logging
from typing import Optional

from iaglobal.feedback.reward_signal import RewardSignal, RewardSource

logger = logging.getLogger(__name__)


class UserFeedbackCollector:
    """Coleta feedback explícito do usuário sobre o resultado."""

    @classmethod
    def collect(cls, task: str, result_preview: str = "") -> Optional[RewardSignal]:
        try:
            print(f"\n{'='*50}")
            print("📋 Feedback sobre o resultado:")
            if result_preview:
                print(f"  Resultado: {result_preview[:200]}...")
            print(f"{'='*50}")
            rating = input("  Nota (1-5) [5=perfeito, Enter=pular]: ").strip()
            if not rating:
                return None

            rating_map = {"1": 0.2, "2": 0.4, "3": 0.6, "4": 0.8, "5": 1.0}
            score = rating_map.get(rating, 0.5)

            comment = input("  Comentário (opcional): ").strip()

            return RewardSignal(
                score=score,
                source=RewardSource.USER,
                metadata={"rating": rating, "comment": comment} if comment else {"rating": rating},
                task=task,
            )
        except (EOFError, KeyboardInterrupt):
            return None
        except Exception as e:
            logger.debug("[FEEDBACK] Erro ao coletar feedback: %s", e)
            return None
