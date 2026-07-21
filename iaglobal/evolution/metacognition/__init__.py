# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
iaglobal/evolution/metacognition — Subsistema oficial de metacognição.

Responsabilidades:
    - Avaliação de execuções (PipelineEvaluator)
    - Análise de gaps (GapAnalyzer)
    - Geração de skills (SkillGenerator via backlog)
    - Validação em sandbox (SandboxValidator)
    - Comitê evolutivo (EvolutionCommittee)
    - Atualização do pipeline (PipelineUpdater)
    - Trigger de evolução (EvolutionTrigger)
    - Reflexões e insights (ReflectionEngine)
    - Backlog evolutivo (EvolutionBacklog)
    - Taxonomia de falhas (FailureTaxonomy)

Este é o ÚNICO namespace de metacognição no sistema.
"""

from iaglobal.evolution.metacognition.evolution_trigger import EvolutionTrigger
from iaglobal.evolution.metacognition.evolution_committee import EvolutionCommittee
from iaglobal.evolution.metacognition.gap_analyzer import GapAnalyzer
from iaglobal.evolution.metacognition.evaluator import PipelineEvaluator
from iaglobal.evolution.metacognition.pipeline_updater import PipelineUpdater
from iaglobal.evolution.metacognition.sandbox_validator import SandboxValidator
from iaglobal.evolution.metacognition.reflection import Reflection, ReflectionEngine
from iaglobal.evolution.metacognition.evolution_backlog import EvolutionBacklog
from iaglobal.evolution.metacognition.failure_taxonomy import (
    classify_error,
    classify_errors,
)

__all__ = [
    "EvolutionTrigger",
    "EvolutionCommittee",
    "GapAnalyzer",
    "PipelineEvaluator",
    "PipelineUpdater",
    "SandboxValidator",
    "Reflection",
    "ReflectionEngine",
    "EvolutionBacklog",
    "classify_error",
    "classify_errors",
]
