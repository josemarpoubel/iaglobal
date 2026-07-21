# iaglobal/pipeline/context/providers/planner.py
"""
PlannerContextProvider — provider declarativo para o nó planner.

Projeta do MissionContext:
  - objective (prioridade 100)
  - domain    (prioridade 90)
  - entities  (prioridade 70)
  - constraints (prioridade 60)

Orçamento total: ~60+15+40+50 = ~165 tokens (~660 chars).
"""

from .base import register_projection_provider


PlannerContextProvider = register_projection_provider(
    "planner",
    sections=(
        ("objective", "Objetivo", 100, "mission.objective"),
        ("domain", "Domínio", 90, "mission.domain"),
        ("entities", "Entidades", 70, "mission.entities"),
        ("constraints", "Restrições", 60, "mission.constraints"),
    ),
)
