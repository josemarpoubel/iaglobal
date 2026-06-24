from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TaskFingerprint:
    domain: str                 # web, data, ai, infra, image, video
    subdomain: str             # backend, frontend, ml, devops
    language: Optional[str]    # python, php, js, image, video...
    intent: str                # generate, debug, explain, refactor
    complexity: str            # low, medium, high
    risk: str                  # low, medium, high

    def key(self) -> str:
        """Chave compacta para fallback/compatibilidade."""
        return f"{self.domain}:{self.subdomain}:{self.intent}:{self.language or 'any'}"

    def to_vector(self) -> tuple:
        """Representação comparável simples (sem ML ainda)."""
        return (
            self.domain,
            self.subdomain,
            self.language or "any",
            self.intent,
            self.complexity,
            self.risk
        )

    def context_key(self) -> str:
        """
        Chave compacta para aprendizado contextual.
        """
        return f"{self.domain}:{self.subdomain}:{self.intent}:{self.complexity}:{self.risk}"
