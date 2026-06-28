# tests/test_opportunity_cost.py
"""Testes do OpportunityCostDetector e Apoptose Programada."""
import asyncio
import pytest

from iaglobal.evolution.metabolism.opportunity_cost_detector import OpportunityCostDetector
from iaglobal.feedback.reward_signal import RewardSignal, RewardSource


class TestOpportunityCostDetector:
    """Testes do detector de custo de oportunidade."""

    def test_record_consumption_acumula(self):
        """Consumo deve acumular corretamente."""
        detector = OpportunityCostDetector()
        detector.reset_profile("test_agent")
        
        detector.record_consumption("test_agent", cpu_seconds=2.0, memory_mb=50.0, file_ops=20)
        detector.record_consumption("test_agent", cpu_seconds=1.0, memory_mb=30.0, file_ops=15)
        
        profile = detector._profiles["test_agent"]
        assert profile.cpu_seconds_consumed == 3.0
        assert profile.memory_mb_peak == 50.0
        assert profile.file_ops == 35

    def test_reward_signal_records(self):
        """Reward signals devem ser registrados."""
        detector = OpportunityCostDetector()
        detector.reset_profile("reward_agent")
        
        detector.record_reward("reward_agent", RewardSignal(
            source=RewardSource.USER,
            score=0.9,
            metadata={"test": True}
        ))
        
        profile = detector._profiles["reward_agent"]
        assert len(profile.reward_signals) == 1

    def test_simbionte_positivo(self):
        """Agente com reward > custo é saudável."""
        detector = OpportunityCostDetector()
        detector.reset_profile("healthy_agent")
        
        detector.record_consumption("healthy_agent", cpu_seconds=1.0, memory_mb=10.0)
        detector.record_reward("healthy_agent", RewardSignal(
            source=RewardSource.USER,
            score=0.9
        ))
        
        classification = detector.classify_symbiont("healthy_agent")
        assert classification == "simbionte_positivo"

    def test_simbionte_negativo(self):
        """Agente com custo alto + reward baixo é parasita."""
        detector = OpportunityCostDetector()
        detector.reset_profile("parasite_agent")
        
        # Consuma muito mas sem reward
        detector.record_consumption(
            "parasite_agent", 
            cpu_seconds=10.0,  # > 5.0 threshold
            memory_mb=200.0,   # > 100 threshold
            file_ops=200       # > 100 threshold
        )
        
        classification = detector.classify_symbiont("parasite_agent")
        assert classification == "simbionte_negativo"

    def test_parasite_score_calc(self):
        """Parasite score deve ser calculado corretamente."""
        detector = OpportunityCostDetector()
        detector.reset_profile("score_agent")
        
        detector.record_consumption("score_agent", cpu_seconds=8.0)
        
        result = detector.calculate_opportunity_cost("score_agent")
        assert result["cost_score"] > 0
        assert result["reward_score"] == 0.0

    def test_reset_profile(self):
        """Reset deve limpar o perfil."""
        detector = OpportunityCostDetector()
        detector.reset_profile("reset_agent")
        
        detector.record_consumption("reset_agent", cpu_seconds=5.0)
        detector.reset_profile("reset_agent")
        
        assert "reset_agent" not in detector._profiles


class TestApoptosisKill:
    """Testes de apoptose programada."""

    def test_apoptosis_nao_mata_saudavel(self):
        """Apoptose não deve executar em agente saudável."""
        async def _run():
            from iaglobal.graphs.nodes.no_apoptosis_kill import run_apoptosis_kill
            result = await run_apoptosis_kill({"agent_name": "healthy"})
            assert result["status"] == "skipped"
        asyncio.run(_run())

    def test_apoptosis_prepara_snapshot(self):
        """Apoptose deve preparar snapshot de estado."""
        async def _run():
            from iaglobal.graphs.nodes.no_apoptosis_kill import run_apoptosis_kill
            from iaglobal.evolution.metabolism.opportunity_cost_detector import opportunity_cost_detector
            
            # Preparar um agente parasita
            opportunity_cost_detector.reset_profile("to_kill")
            opportunity_cost_detector.record_consumption("to_kill", cpu_seconds=10.0, memory_mb=200.0)
            
            result = await run_apoptosis_kill({"agent_name": "to_kill", "reason": "test"})
            assert result["status"] == "executed"
            assert result["quarantine_activated"] is True
        asyncio.run(_run())