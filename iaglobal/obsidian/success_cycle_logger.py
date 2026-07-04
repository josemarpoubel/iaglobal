# iaglobal/obsidian/success_cycle_logger.py
"""
SuccessCycleLogger — Métricas de sucesso ao final de cada ciclo macro.

Registra:
1. Taxa de Integridade (sucessos / tentativas)
2. Taxa de Crescimento (melhoria no IVM)
3. Alinhamento (agentes dentro das leis universais)
4. Eficiência Energética (energia economizada vs. trabalho realizado)
"""
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SuccessMetrics:
    """Métricas do ciclo de sucesso."""
    integrity_rate: float  # 0-1
    growth_rate: float  # delta IVM
    alignment_score: float  # agentes alinhados / total
    energy_efficiency: float  # trabalho / energia gasto
    cycle_id: str


class SuccessCycleLogger:
    """
    Logger de sucesso do ciclo evolutivo.

    Registra em obsidian/04_Synapses/success_log.md
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._history: List[SuccessMetrics] = []

    def calculate_integrity_rate(self, successes: int, attempts: int) -> float:
        """Taxa de integridade = sucessos / tentativas."""
        return min(1.0, successes / max(1, attempts))

    def calculate_growth_rate(self, current_ivm: float, previous_ivm: float = 0.0) -> float:
        """Taxa de crescimento = delta IVM."""
        return current_ivm - previous_ivm

    def calculate_energy_efficiency(self, work_units: float, energy_units: float) -> float:
        """Eficiência energética = trabalho / energia."""
        if energy_units <= 0:
            return 0.0
        return work_units / energy_units

    async def log_success_cycle(self, metrics: SuccessMetrics) -> Path:
        """
        Grava métricas no success_log.md de forma assíncrona.

        Returns:
            Caminho do arquivo gravado
        """
        self._history.append(metrics)

        log_path = Path("iaglobal/obsidian/04_Synapses/success_log.md")
        log_path.parent.mkdir(parents=True, exist_ok=True)

        entry = f"""## Ciclo {metrics.cycle_id} - {datetime.now(timezone.utc).isoformat()}

- **Taxa de Integridade:** {metrics.integrity_rate:.2%}
- **Taxa de Crescimento (IVM):** {metrics.growth_rate:+.3f}
- **Score de Alinhamento:** {metrics.alignment_score:.2%}
- **Eficiência Energética:** {metrics.energy_efficiency:.2f} unidades de trabalho/por unidade de energia

---
"""

        def _write():
            if log_path.exists():
                content = log_path.read_text() + entry
            else:
                content = f"""---
id: "success_log"
tipo: "MetricasSucessoCiclo"
timestamp: "{datetime.now(timezone.utc).isoformat()}"
---

# Registro de Sucesso do Ciclo (Law of Success)

{entry}"""
            log_path.write_text(content, encoding="utf-8")

        await asyncio.to_thread(_write)
        logger.info(f"[SUCCESS] Ciclo {metrics.cycle_id} logado - IVM={metrics.growth_rate}")
        return log_path

    def get_average_efficiency(self, last_n: int = 10) -> float:
        """Média de eficiência dos últimos ciclos."""
        if not self._history:
            return 0.0
        relevant = self._history[-last_n:]
        return sum(m.energy_efficiency for m in relevant) / len(relevant)


# Singleton
success_cycle_logger = SuccessCycleLogger()