# iaglobal/core/structure.py

import os
import logging

from pathlib import Path

from iaglobal._paths import ensure_structure

logger = logging.getLogger("ia-global")

REQUIRED_DIRS = [
    "memory/data/logs",
    "memory/data/db",
    "memory/data/vectors"
]

def ensure_structure():
    """Garante que a estrutura de pastas necessária para o runtime exista."""
    # Ajuste o caminho se necessário (o 'parent' sobe para iaglobal, 'parent' para projeto-iaglobal)
    base_path = Path(__file__).resolve().parent.parent.parent
    for d in REQUIRED_DIRS:
        path = base_path / d
        path.mkdir(parents=True, exist_ok=True)

    # Executa coleta inicial de falhas do sistema em background
    _run_failure_collection_in_background()


def _run_failure_collection_in_background():
    """Dispara coleta de falhas em thread separada para não travar o bootstrap."""
    import threading

    def _collect():
        try:
            from iaglobal.agents.failure_analysis_agent import FailureAnalysisAgent
            system_data = FailureAnalysisAgent.collect_system_data()
            if system_data.get("errors", {}).get("total", 0) > 0 or system_data.get("metrics", {}).get("total_calls", 0) > 0:
                report = FailureAnalysisAgent.generate_report(system_data)
                FailureAnalysisAgent.persist_report(system_data, report)
        except Exception:
            pass

    t = threading.Thread(target=_collect, daemon=True, name="failure-collector")
    t.start()


if __name__ == "__main__":
    ensure_structure()
