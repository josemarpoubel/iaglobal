# tests/test_success_cycle_logger.py
"""Testes do ritual de registro de sucesso."""

"""Testes do ritual de registro de sucesso."""
import pytest
from pathlib import Path

from iaglobal.obsidian.success_cycle_logger import SuccessCycleLogger, SuccessMetrics


class TestSuccessCycleLogger:
    """Testa métricas de sucesso."""

    def test_calculate_integrity_rate(self):
        logger = SuccessCycleLogger()
        
        # Mantido síncrono (retorna float)
        rate = logger.calculate_integrity_rate(95, 100)
        assert rate == 0.95

    def test_calculate_growth_rate(self):
        logger = SuccessCycleLogger()
        
        # Mantido síncrono (retorna float)
        growth = logger.calculate_growth_rate(0.85, 0.65)
        assert abs(growth - 0.2) < 0.001

    def test_calculate_energy_efficiency(self):
        logger = SuccessCycleLogger()
        
        # Mantido síncrono (retorna float)
        efficiency = logger.calculate_energy_efficiency(100.0, 10.0)
        assert efficiency == 10.0

    @pytest.mark.asyncio
    async def test_log_success_cycle(self):
        logger = SuccessCycleLogger()
        
        metrics = SuccessMetrics(
            integrity_rate=0.95,
            growth_rate=0.2,
            alignment_score=0.9,
            energy_efficiency=10.0,
            cycle_id="test_cycle",
        )
        
        # Apenas este método é assíncrono e exige await
        path = await logger.log_success_cycle(metrics)
        assert path.name == "success_log.md"

