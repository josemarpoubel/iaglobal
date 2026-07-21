# iaglobal/pipeline/context/providers/coder.py
"""
CoderContextProvider — provider declarativo para o nó coder.

Projeta do MissionContext:
  - objective    (prioridade 100)
  - architecture (prioridade 90)
  - requirements (prioridade 80)
  - constraints  (prioridade 70)
  - technologies (prioridade 60)
"""

from .base import register_projection_provider


CoderContextProvider = register_projection_provider(
    "coder",
    sections=(
        ("objective", "Objetivo", 100, "mission.objective"),
        ("architecture", "Arquitetura", 90, "mission.architecture"),
        ("requirements", "Requisitos", 80, "mission.entities"),
        ("constraints", "Restrições", 70, "mission.constraints"),
        ("technologies", "Tecnologias", 60, "mission.language"),
    ),
)
