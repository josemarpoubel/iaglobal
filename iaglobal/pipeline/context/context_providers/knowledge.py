# iaglobal/pipeline/context/providers/knowledge.py
"""
KnowledgeContextProvider — provider especializado para conhecimento de domínio.

Projeta do ExecutionContext:
  - Domain knowledge (mission.domain)
  - Architecture patterns (mission.architecture)
  - Constraints (mission.constraints)
  - Entities (mission.entities)
  - Priorities (mission.priorities)

Uso:
  - planner: entende contexto de domínio
  - architect: seleciona patterns apropriados
  - coder: aplica convenções do domínio
  - reviewer: valida aderência a constraints
  - documentation: gera docs contextualizadas
"""

from .base import register_projection_provider


KnowledgeContextProvider = register_projection_provider(
    "knowledge",
    sections=(
        ("domain", "Domínio", 100, "mission.domain"),
        ("architecture", "Padrões Arquiteturais", 90, "mission.architecture"),
        ("entities", "Entidades do Domínio", 80, "mission.entities"),
        ("constraints", "Restrições", 70, "mission.constraints"),
        ("priorities", "Prioridades", 60, "mission.priorities"),
    ),
)
