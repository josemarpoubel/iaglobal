from dataclasses import dataclass, field
from typing import Optional

from .node import Node


PENDING = "PENDING"
RUNNING = "RUNNING"
SUCCESS = "SUCCESS"
FAILED = "FAILED"


@dataclass
class Task:
    id: str
    node: Node
    status: str = PENDING
    attempt: int = 0
    max_retries: int = 3
    output: Optional[str] = None
    error: Optional[str] = None

    @property
    def is_done(self) -> bool:
        return self.status in (SUCCESS, FAILED)

    @property
    def can_retry(self) -> bool:
        return self.status == FAILED and self.attempt < self.max_retries
