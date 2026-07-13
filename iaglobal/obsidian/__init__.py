# iaglobal/obsidian/__init__.py
"""Obsidian — Sistema de memória e processamento subconsciente do iaglobal.

Módulos exports:
- SubconsciousAPI: Interface com vault Obsidian
- FugueCompartment: Processamento de tarefas em background
- DeltaSleepSync: Limpeza e compactação de memórias
- OmniMind: Sistema imunológico e apoptose
- EpigeneticRegistry: Registro de skills e configurações dinâmicas
"""

from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
from iaglobal.obsidian.fugue_compartment import FugueCompartment
from iaglobal.obsidian.delta_sleep import DeltaSleepSync
from iaglobal.obsidian.omnimind import omni_mind
from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry

__all__ = [
    "SubconsciousAPI",
    "FugueCompartment",
    "DeltaSleepSync",
    "omni_mind",
    "EpigeneticRegistry",
]
