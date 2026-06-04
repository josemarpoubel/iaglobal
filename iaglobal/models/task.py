# iaglobal/models/task.py

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import uuid
import json
from typing import List, Dict, Any, Optional, Union


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    objective: str = ""
    constraints: List[str] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if not self.objective:
            self.objective = ""
        # context defaults to {} — callers use .setdefault() / .get()

    def __str__(self):
        return self.objective or ""

    def __bool__(self):
        return bool(self.objective)

    def validate(self) -> bool:
        return len(self.objective.strip()) > 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        clean_data = {
            "id": str(data.get("id", uuid.uuid4().hex[:8])),
            "objective": str(data.get("objective", "")),
            "constraints": list(data.get("constraints", [])),
            "tests": list(data.get("tests", [])),
            "metadata": dict(data.get("metadata", {})),
            "context": dict(data.get("context", {})),
            "created_at": str(data.get("created_at", datetime.now(timezone.utc).isoformat()))
        }
        return cls(**clean_data)

    @classmethod
    def from_json(cls, payload: str) -> "Task":
        return cls.from_dict(json.loads(payload))

    @classmethod
    def from_string(cls, text: str) -> "Task":
        return cls(objective=text)

    def format_prompt(self) -> str:
        if not self.validate():
            raise ValueError("Tarefa sem objetivo definido.")

        parts = [f"TAREFA: {self.objective}"]

        if self.constraints:
            parts.append("RESTRIÇÕES:")
            parts.extend(f"- {c}" for c in self.constraints)

        mem = self.context.get("memory", [])
        if isinstance(mem, str):
            mem = [mem]
        extra = self.context.get("extra", "")

        if mem or extra:
            parts.append("CONTEXTO:")
            if mem:
                parts.extend(mem)
            if extra:
                parts.append(extra)

        prompt = "\n".join(parts)

        if not self.constraints and not mem and not extra:
            prompt = self.objective

        return prompt

    def add_memory(self, text: str):
        self.context.setdefault("memory", []).append(str(text))

    def add_error(self, error_text: str):
        self.context.setdefault("errors", []).append(str(error_text))
