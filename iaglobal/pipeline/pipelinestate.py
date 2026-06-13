from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PipelineState:
    """
    Estado central do pipeline.
    """

    task_id: str
    prompt: str

    current_stage: str = "INIT"

    generated_code: Optional[str] = None

    script_path: Optional[str] = None

    syntax_valid: bool = False
    security_valid: bool = False
    execution_valid: bool = False

    score: float = 0.0

    retries: int = 0

    errors: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    context: Dict[str, Any] = field(default_factory=dict)
