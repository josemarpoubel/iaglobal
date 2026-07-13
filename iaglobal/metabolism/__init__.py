# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Metabolism Module — Ciclo metabólico do iaglobal.

Componentes:
- MethylationEngine: Transformação de dados (Metionina → SAMe → Homocisteína)
- HomocysteinePool: Detecção de toxicidade/acúmulo de erros
- MethylationCycle: Ciclo completo de metilação
- TranssulfurationCycle: Caminho alternativo de reciclagem
- OpportunityCostDetector: Análise custo-benefício de agentes
- MetabolicMetrics: Métricas de ATP/IVM
- MetabolicInvariants: Invariantes do sistema
- MetabolicAutocorrect: Auto-correção baseada em metabolismo
- ClarityDirective: Clareza de saída
"""

from iaglobal.metabolism.methylation_engine import MethylationEngine
from iaglobal.metabolism.homocysteine_pool import HomocysteinePool
from iaglobal.metabolism.methylation_cycle import MethylationCycle
from iaglobal.metabolism.transsulfuration_cycle import TranssulfurationCycle
from iaglobal.metabolism.opportunity_cost_detector import OpportunityCostDetector
from iaglobal.metabolism.metabolic_metrics import MetabolicMetrics
from iaglobal.metabolism.metabolic_invariants import MetabolicInvariants
from iaglobal.metabolism.metabolic_autocorrect import MetabolicAutocorrect
from iaglobal.metabolism.clarity_directive import ClarityDirective

__all__ = [
    "MethylationEngine",
    "HomocysteinePool",
    "MethylationCycle",
    "TranssulfurationCycle",
    "OpportunityCostDetector",
    "MetabolicMetrics",
    "MetabolicInvariants",
    "MetabolicAutocorrect",
    "ClarityDirective",
]
