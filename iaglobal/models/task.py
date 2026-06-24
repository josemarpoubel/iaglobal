# iaglobal/models/task.py

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import uuid
from typing import Dict, Any


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    objective: str = ""
    constraints: list = field(default_factory=list)
    tests: list = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __str__(self):
        return self.objective or ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
