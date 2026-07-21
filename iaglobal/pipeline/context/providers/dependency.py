# iaglobal/pipeline/context/providers/dependency.py
"""
DependencyContextProvider — provider declarativo para o nó dependency.

Projeta do MissionContext:
  - objective    (prioridade 100)
  - domain       (prioridade 90)
  - technologies (prioridade 80)
  - architecture (prioridade 70)
"""

from .base import register_projection_provider


DependencyContextProvider = register_projection_provider(
    "dependency",
    sections=(
        ("objective", "Objetivo", 100, "mission.objective"),
        ("domain", "Domínio", 90, "mission.domain"),
        ("technologies", "Tecnologias", 80, "mission.language"),
        ("architecture", "Arquitetura", 70, "mission.architecture"),
    ),
)
