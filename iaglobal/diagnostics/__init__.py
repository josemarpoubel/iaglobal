# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
iaglobal/diagnostics — Subsistema de diagnóstico, classificação e reparo de erros.

Arquitetura:
  Exception
      ↓
  ErrorClassifier (Chain of Responsibility)
      ↓
  ErrorDescriptor (domínio + causa)
      ↓
  RepairEngine (estratégias por capacidade)
      ↓
  RepairStrategy
      ↓
  RepairReport (com attempt, chain, telemetry)

Módulos:
  - error_category.py: Domínios e causas de erro
  - severity.py: Severidade e recuperabilidade
  - error_descriptor.py: Objeto rico de diagnóstico
  - error_classifier.py: Classificadores em cadeia
  - repair_engine.py: Orquestrador de reparos
  - repair_strategies.py: Estratégias plugáveis

Uso:
  from iaglobal.diagnostics import repair_engine

  report = repair_engine.repair(code, error, component="validator")

  if report.success:
      return report.after_code
  else:
      log(report.get_diagnostics())
"""

from iaglobal.diagnostics.error_classifier import error_classifier
from iaglobal.diagnostics.repair_engine import repair_engine
from iaglobal.diagnostics.error_descriptor import (
    ErrorDescriptor,
    ErrorCategory,
    ErrorCause,
    Severity,
)
from iaglobal.diagnostics.repair_engine import RepairReport

__all__ = [
    "error_classifier",
    "repair_engine",
    "ErrorDescriptor",
    "ErrorCategory",
    "ErrorCause",
    "Severity",
    "RepairReport",
]
