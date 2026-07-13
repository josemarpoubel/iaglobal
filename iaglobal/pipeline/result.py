from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PipelineResult:
    """
    Resultado padronizado do pipeline.
    """

    success: bool

    response: Optional[str] = None

    error: Optional[str] = None

    score: float = 0.0

    metadata: Dict[str, Any] = field(default_factory=dict)

    errors: List[str] = field(default_factory=list)

    script_path: Optional[str] = None
