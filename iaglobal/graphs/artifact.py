from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Artifact:
    content: Any = ""
    type: str = "code"
    path: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SolutionArtifact:
    task: str = ""
    code: str = ""
    critique: str = ""
    score: float = 0.0
    tests_passed: int = 0
    tests_total: int = 0
    runtime_error: str = ""
    security_report: str = ""
    reflection: str = ""
    repaired: bool = False
    critic_degraded: bool = False
    semantic_score: float = 0.0
    semantic_errors: list = field(default_factory=list)
    critic_scores: Dict[str, float] = field(default_factory=lambda: {
        "correctness": 0.0,
        "completeness": 0.0,
        "security": 0.0,
        "spec_match": 0.0,
    })
    review_score: float = 0.0
    files: dict = field(default_factory=dict)
