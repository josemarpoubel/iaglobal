from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class AgentContext:
    task: str = ""
    plan: dict = field(default_factory=dict)
    knowledge: str = ""
    code_candidates: dict = field(default_factory=dict)
    critiques: dict = field(default_factory=dict)
    rankings: list = field(default_factory=list)
    best_code: str = ""
    best_score: float = 0.0
    test_results: dict = field(default_factory=dict)
    debug_attempts: int = 0
    reflections: list = field(default_factory=list)
    success: bool = False
