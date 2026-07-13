from __future__ import annotations


class MaxRetriesReached(Exception):
    """Raised when all retry attempts have been exhausted without success."""

    def __init__(self, retries: int, state_summary: str = "") -> None:
        self.retries = retries
        self.state_summary = state_summary
        super().__init__(
            f"Max retries ({retries}) exceeded. "
            f"Details: {state_summary or 'unknown state'}"
        )


class BackpressureSignal(Exception):
    """Raised when the system needs to signal upstream backpressure."""

    def __init__(self, reason: str = "capacity exceeded") -> None:
        self.reason = reason
        super().__init__(reason)


class LawViolation(Exception):
    """Raised when an agent violates one of the 11 Universal Laws (Holliwell).

    Triggered by no_law_of_thought_enforcer and other law-enforcement nodes.
    The OmniMind's apply_lei_da_obediencia handles the apoptotic response.
    """

    def __init__(self, message: str = "", law: str = "Lei do Pensamento") -> None:
        self.law = law
        super().__init__(message or f"Violacao da {law}")
