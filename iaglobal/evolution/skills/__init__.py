# iaglobal/evolution/skills/__init__.py

"""
🎯 Skill Abstraction Layer

Skill NÃO é prompt. Skill é unidade executável + contrato + constraints + identidade.

Camadas:
- skill.py: Dataclass Skill com nome, inputs, outputs, constraints, execution_policy
- skill_registry.py: Registry global de skills versionadas
- skill_executor.py: Executor que resolve skill → node(s) no DAG
- skill_versions.py: Controle de versão e migração de skills
"""

from .skill import (
    Skill,
    SKILL_PLANNER,
    SKILL_CODER,
    SKILL_TESTER,
    SKILL_DEBUGGER,
    SKILL_ARCHITECT,
    SKILL_SEARCH,
    SKILL_SEMANTIC_VALIDATOR,
    SKILL_REVIEWER,
    SKILL_DOCUMENTATION,
    SKILL_DEPENDENCY,
    SKILL_REQUIREMENTS,
    SKILL_PRODUCT_MANAGER,
    SKILL_PROMPT_INTAKE,
    SKILL_RISK_ANALYSIS,
    SKILL_RELEASE,
    SKILL_METRICS,
    SKILL_OPTIMIZATION,
    SKILL_KNOWLEDGE,
    SKILL_ENHANCEMENT,
    SKILL_ORCHESTRATOR,
    SKILL_SECURITY_DESIGN,
    SKILL_PERFORMANCE_DESIGN,
    SKILL_SECURITY_AUDIT,
    SKILL_PERFORMANCE_AUDIT,
    SKILL_RESULT_AGENT,
)
from .skill_registry import SkillRegistry
from .skill_executor import SkillExecutor
from .skill_versions import SkillVersion, VersionManager
from .dynamic_registry import DynamicSkillRegistry, dynamic_registry
from .run_fn_factory import make_dynamic_run_fn, TEMPLATE_REGISTRY

__all__ = [
    "Skill",
    "SkillRegistry",
    "SkillExecutor",
    "SkillVersion",
    "VersionManager",
    "DynamicSkillRegistry",
    "dynamic_registry",
    "make_dynamic_run_fn",
    "TEMPLATE_REGISTRY",
    "SKILL_PLANNER",
    "SKILL_CODER",
    "SKILL_TESTER",
    "SKILL_DEBUGGER",
    "SKILL_ARCHITECT",
    "SKILL_SEARCH",
    "SKILL_SEMANTIC_VALIDATOR",
    "SKILL_REVIEWER",
    "SKILL_DOCUMENTATION",
    "SKILL_DEPENDENCY",
    "SKILL_REQUIREMENTS",
    "SKILL_PRODUCT_MANAGER",
    "SKILL_PROMPT_INTAKE",
    "SKILL_RISK_ANALYSIS",
    "SKILL_RELEASE",
    "SKILL_METRICS",
    "SKILL_OPTIMIZATION",
    "SKILL_KNOWLEDGE",
    "SKILL_ENHANCEMENT",
    "SKILL_ORCHESTRATOR",
    "SKILL_SECURITY_DESIGN",
    "SKILL_PERFORMANCE_DESIGN",
    "SKILL_SECURITY_AUDIT",
    "SKILL_PERFORMANCE_AUDIT",
    "SKILL_RESULT_AGENT",
]
