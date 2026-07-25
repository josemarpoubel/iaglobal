from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from iaglobal.core.artifact import ArtifactKind, GeneratedArtifact


class TaskIntent(str, Enum):
    CHAT = "chat"
    CODE = "code"
    HTML = "html"
    JSON = "json"
    DOCUMENT = "document"
    ANALYSIS = "analysis"
    GENERAL = "general"


@dataclass
class PipelineState:
    task_id: str

    prompt: str

    current_stage: str = "INIT"

    _generated_code: Optional[str] = None

    generated_artifact: Optional[GeneratedArtifact] = None

    script_path: Optional[str] = None

    syntax_valid: bool = False

    security_valid: bool = False

    execution_valid: bool = False

    score: float = 0.0

    retries: int = 0

    errors: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    context: Dict[str, Any] = field(default_factory=dict)

    intent: TaskIntent = TaskIntent.GENERAL

    execution_context: Any = None

    execution_report: Optional[Dict[str, Any]] = None

    chosen_model: Optional[str] = None

    @property
    def generated_code(self) -> Optional[str]:
        if self.generated_artifact is not None:
            return self.generated_artifact.content
        return self._generated_code

    @generated_code.setter
    def generated_code(self, value: Optional[str]):
        if value is not None:
            self.generated_artifact = GeneratedArtifact.from_str(value)
            self._generated_code = value
        else:
            self.generated_artifact = None
            self._generated_code = None
