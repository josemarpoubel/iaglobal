# tests/test_parasite_symbiont_recognition.py
"""Testes de reconhecimento de parasitas vs simbiontes."""
import pytest

from iaglobal.immunity.immune_orchestrator import immune_orchestrator
from iaglobal.graphs.communication.membrane_key import MembraneKey


class TestParasiteSymbiontRecognition:
    """Testa a capacidade de distinguir parasitas de simbiontes."""

    def test_symbiont_tolerance_with_membrane_key(self):
        """Simbionte com chave deve ter tolerância maior."""
        mk = MembraneKey()
        key = mk.generate_key("trusted_llm")
        
        report = immune_orchestrator.scan_execution(
            skill_name="trusted_external",
            execution_context={"membrane_key": key},
            output="SELECT * FROM users;",
            metrics={"latency": 0.01, "cost": 0.001, "success": True}
        )
        
        # Simbionte autorizado via membrane_key deve ser tolerado
        assert report.threat_detected is False or report.threats.get("hallucination") is None

    def test_parasite_without_key(self):
        """Agente sem chave pode ser classificado como parasita."""
        report = immune_orchestrator.scan_execution(
            skill_name="random_agent",
            execution_context={},  # Sem membrane_key
            output="optimized response",
            metrics={"latency": 0.05, "cost": 0.001, "success": True}
        )
        
        assert report.threat_detected is False  # Output "clean" passa

    def test_symbiont_productive_low_cost(self):
        """Simbionte produtivo tem baixo custo de oportunidade."""
        mk = MembraneKey()
        key = mk.generate_key("efficient_service")
        
        report = immune_orchestrator.scan_execution(
            skill_name="efficient_symbiont",
            execution_context={"membrane_key": key},
            output="optimized response",
            metrics={"latency": 0.05, "cost": 0.001, "success": True}
        )
        
        assert report.threat_detected is False