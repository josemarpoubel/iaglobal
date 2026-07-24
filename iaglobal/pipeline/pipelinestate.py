from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from iaglobal.core.artifact import GeneratedArtifact


class TaskIntent(str, Enum):
    CHAT = "chat"
    CODE = "code"
    HTML = "html"
    JSON = "json"
    DOCUMENT = "document"
    ANALYSIS = "analysis"
    GENERAL = "general"


@dataclass(init=False)
class PipelineState:
    task_id: str

    prompt: str

    current_stage: str = "INIT"

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

    def __init__(
        self,
        task_id: str,
        prompt: str,
        current_stage: str = "INIT",
        generated_artifact: Optional[GeneratedArtifact] = None,
        generated_code: Optional[Any] = None,
        script_path: Optional[str] = None,
        syntax_valid: bool = False,
        security_valid: bool = False,
        execution_valid: bool = False,
        score: float = 0.0,
        retries: int = 0,
        errors: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        intent: TaskIntent = TaskIntent.GENERAL,
        execution_context: Any = None,
        execution_report: Optional[Dict[str, Any]] = None,
        chosen_model: Optional[str] = None,
    ) -> None:
        self.task_id = task_id
        self.prompt = prompt
        self.current_stage = current_stage
        if generated_artifact is not None:
            self.generated_artifact = generated_artifact
        elif generated_code is not None:
            self.generated_code = generated_code
        else:
            self.generated_artifact = None
        self.script_path = script_path
        self.syntax_valid = syntax_valid
        self.security_valid = security_valid
        self.execution_valid = execution_valid
        self.score = score
        self.retries = retries
        self.errors = errors if errors is not None else []
        self.metadata = metadata if metadata is not None else {}
        self.context = context if context is not None else {}
        self.intent = intent
        self.execution_context = execution_context
        self.execution_report = execution_report
        self.chosen_model = chosen_model

    @property
    def generated_code(self) -> Optional[str]:
        """Compat retroativa: retorna o conteúdo do artifact tipado."""
        return self.generated_artifact.content if self.generated_artifact else None

    @generated_code.setter
    def generated_code(self, value: Optional[Any]) -> None:
        """Setter de compat: envolve str em GeneratedArtifact.classificado automaticamente."""
        if value is None or value == "":
            self.generated_artifact = None
            return
        if isinstance(value, GeneratedArtifact):
            self.generated_artifact = value
            return
        self.generated_artifact = GeneratedArtifact.from_str(value, source="legacy")

    def set_artifact(self, artifact: GeneratedArtifact) -> None:
        """API explícita e idiomática para fixar o artifact tipado."""
        self.generated_artifact = artifact

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
