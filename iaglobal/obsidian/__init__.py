"""Módulo Obsidian — Subconsciente Ativo do iaglobal.

Estrutura do Vault:
  /01_Instincts   — Diretrizes imutáveis e regras de sobrevivência
  /02_Short_Term  — Buffer volátil de logs brutos do dia
  /03_Long_Term   — Conceitos consolidados e estratégias de sucesso
  /04_Synapses    — Mapas Mentais (MOCs) gerados automaticamente
"""

from .subconsciousapi import SubconsciousAPI
from .consolidation import REMSleepEngine
from .learning_system import LearningSystem
from .error_capture import ErrorCapture
from .omnimind import OmniMind, omni_mind, Orientacao

__all__ = [
    "SubconsciousAPI",
    "REMSleepEngine",
    "LearningSystem",
    "ErrorCapture",
    "OmniMind",
    "omni_mind",
    "Orientacao",
]
