# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Chappie — Núcleo de Autonomia Computacional do iaglobal.

5 módulos:
  - IVMAxiom:         Índice de Viabilidade Metabolica (IVM)
  - VacuumDaemon:     Autofagia STM → LTM em background
  - ErrorEnricher:    Enriquecimento de erros com contexto
  - LineageGuardian:  Validação de DNA e defesa de linhagem
  - IvmCompliance:    Feedback IVM → OmniMind

Acesso global: _get_chappie() / _set_chappie()
"""

from iaglobal.chappie.ivm_axiom import IVMAxiom, IVMMetrics, AgentIVMRecord
from iaglobal.chappie.vacuum_daemon import VacuumDaemon
from iaglobal.chappie.error_enricher import ErrorEnricher, ErrorContext
from iaglobal.chappie.lineage_guardian import LineageGuardian, ValidationResult
from iaglobal.chappie.ivm_compliance import IvmCompliance, ivm_compliance
from iaglobal.chappie.bandit_evolution import BanditPolicyEvolution, get_bandit_evolution, init_bandit_evolution

__all__ = [
    "IVMAxiom",
    "IVMMetrics",
    "AgentIVMRecord",
    "VacuumDaemon",
    "ErrorEnricher",
    "ErrorContext",
    "LineageGuardian",
    "ValidationResult",
    "IvmCompliance",
    "ivm_compliance",
    "BanditPolicyEvolution",
    "get_bandit_evolution",
    "init_bandit_evolution",
]

# ── Global registry ─────────────────────────────────────────────
_CHAPPIE: dict = {}


def _set_chappie(**kwargs) -> None:
    """Registra as instâncias ativas do Chappie no escopo global."""
    global _CHAPPIE
    _CHAPPIE.update(kwargs)


def _get_chappie() -> dict:
    """Retorna o registry global do Chappie."""
    return _CHAPPIE
