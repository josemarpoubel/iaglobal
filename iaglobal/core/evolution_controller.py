# iaglobal/core/evolution_controller.py

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SAMe_BUDGET_TOKENS = int(os.getenv("SAMe_BUDGET_TOKENS", "10000"))
SAMe_BUDGET_CALLS = int(os.getenv("SAMe_BUDGET_CALLS", "100"))


class EvolutionController:
    """Controls evolutionary budget for token/calls limits."""

    _instance: Optional["EvolutionController"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._tokens_spent = 0
        self._calls_spent = 0
        self._budget_tokens = SAMe_BUDGET_TOKENS
        self._budget_calls = SAMe_BUDGET_CALLS

    def reset(self) -> None:
        self._tokens_spent = 0
        self._calls_spent = 0
        logger.debug("[SAMe] Budget resetado: tokens=%d, calls=%d", self._budget_tokens, self._budget_calls)

    def spend_tokens(self, amount: int) -> bool:
        if self._tokens_spent + amount > self._budget_tokens:
            logger.warning("[SAMe] Budget tokens esgotado (%d/%d)", self._tokens_spent, self._budget_tokens)
            return False
        self._tokens_spent += amount
        return True

    def spend_call(self) -> bool:
        if self._calls_spent + 1 > self._budget_calls:
            logger.warning("[SAMe] Budget calls esgotado (%d/%d)", self._calls_spent, self._budget_calls)
            return False
        self._calls_spent += 1
        return True

    def remaining_tokens(self) -> int:
        return max(0, self._budget_tokens - self._tokens_spent)

    def remaining_calls(self) -> int:
        return max(0, self._budget_calls - self._calls_spent)

    def is_exhausted(self) -> bool:
        return self.remaining_tokens() <= 0 or self.remaining_calls() <= 0


evolution_controller = EvolutionController()