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

    def remaining_tokens(self) -> int:
        return max(0, self._budget_tokens - self._tokens_spent)

    def remaining_calls(self) -> int:
        return max(0, self._budget_calls - self._calls_spent)

    def is_exhausted(self) -> bool:
        return self.remaining_tokens() <= 0 or self.remaining_calls() <= 0


evolution_controller = EvolutionController()
