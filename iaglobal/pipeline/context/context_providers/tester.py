# iaglobal/pipeline/context/providers/tester.py
"""
TesterContextProvider — provider declarativo para o nó tester.

Projeta do MissionContext:
  - objective    (prioridade 100)
  - requirements (prioridade 90)
  - constraints  (prioridade 80)
  - architecture (prioridade 70)
  - domain       (prioridade 60)
"""

from .base import register_projection_provider


TesterContextProvider = register_projection_provider(
    "tester",
    sections=(
        ("objective", "Objetivo", 100, "mission.objective"),
        ("requirements", "Requisitos", 90, "mission.entities"),
        ("constraints", "Restrições", 80, "mission.constraints"),
        ("architecture", "Arquitetura", 70, "mission.architecture"),
        ("domain", "Domínio", 60, "mission.domain"),
    ),
)
