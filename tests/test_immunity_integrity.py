# tests/test_immunity_integrity.py
"""Teste de integridade do módulo immunity/."""
import pytest

from iaglobal.immunity import (
    LoopDetector, RegressionDetector, HallucinationDetector,
    MHCDetector, mhc_detector,
    ImmuneOrchestrator, immune_orchestrator,
    PathogenAnalyzer, pathogen_analyzer,
    ApoptosisEngine, apoptosis_engine,
    EpigeneticMasking, epigenetic_masking,
    OpportunityCostDetector,
)


class TestImmunityModuleIntegrity:
    """Verifica integridade do módulo immunity completo."""

    def test_all_modules_importable(self):
        """Todos os módulos devem ser importáveis."""
        assert LoopDetector is not None
        assert RegressionDetector is not None
        assert HallucinationDetector is not None
        assert MHCDetector is not None
        assert ImmuneOrchestrator is not None
        assert PathogenAnalyzer is not None
        assert ApoptosisEngine is not None
        assert EpigeneticMasking is not None
        assert OpportunityCostDetector is not None

    def test_singletons_not_none(self):
        """Singletons devem existir."""
        assert mhc_detector is not None
        assert immune_orchestrator is not None
        assert pathogen_analyzer is not None
        assert apoptosis_engine is not None
        assert epigenetic_masking is not None

    def test_immune_flow_integrity(self):
        """Fluxo imunológico deve funcionar como um todo."""
        # 1. MHC fingerprint
        fp = mhc_detector.register_skill("test_integrity", "def run(): pass")
        assert fp is not None
        
        # 2. Pathogen scan
        malicious = "import os; os.system('bad')"
        mal_result = pathogen_analyzer.analyze_code(malicious, "test")
        assert mal_result["is_pathogen"] is True
        
        # 3. Epigenetic masking
        assert epigenetic_masking.can_access("planner", "core_db") is True
        assert epigenetic_masking.can_access("hacker", "core_db") is False

    def test_genesis_hash_available(self):
        """Genesis hash deve estar disponível para máscaras."""
        from iaglobal.security.entropy_sentinel import entropy_sentinel
        
        # Verificar integridade do genesis
        result = entropy_sentinel.verify_genesis_integrity()
        assert result["valid"] is True
        assert result["real_hash"] is not None