# tests/test_immunity_system.py
"""Testes do sistema imunológico (MHC + Quarentena + Orquestração)."""
import asyncio
import pytest
import hashlib

from iaglobal.immunity.mhc_detector import MHCDetector, SkillMHCProfile, mhc_detector
from iaglobal.immunity.immune_orchestrator import ImmuneOrchestrator, immune_orchestrator
from iaglobal.evolution.skill_quarantine import quarantine, QuarantinedSkill


class TestMHCDetector:
    """Testes do Major Histocompatibility Complex."""

    def test_register_skill_gera_fingerprint(self):
        """MHC deve gerar fingerprint sha3_512 consistente."""
        detector = MHCDetector()
        code = "def hello(): return 'world'"
        fp = detector.register_skill("test_skill", code)
        
        assert fp is not None
        assert len(fp) == 32  # primeiros 32 chars do hash
        
        # Verificar consistência
        fp2 = detector.register_skill("test_skill", code)
        assert fp == fp2

    def test_validate_execution_normal(self):
        """Execução normal deve retornar True (self)."""
        detector = MHCDetector()
        detector.register_skill("normal_skill", "def run(): pass")
        
        result = detector.validate_execution("normal_skill", {
            "cpu_seconds": 1.0,
            "file_ops": 10,
            "network_calls": 5,
            "error": False
        })
        assert result is True

    def test_validate_execution_anomalous(self):
        """Execução anômala deve retornar False e acumular score."""
        detector = MHCDetector()
        detector.register_skill("anomalous_skill", "def run(): pass")
        
        # Forçar anomaly score
        for _ in range(5):
            detector.validate_execution("anomalous_skill", {
                "cpu_seconds": 20.0,  # 4x o limite
                "file_ops": 300,    # 3x o limite
                "error": True
            })
        
        result = detector.validate_execution("anomalous_skill", {
            "cpu_seconds": 20.0,
            "file_ops": 300,
            "error": True
        })
        assert result is False  # Deve estar em quarentena


class TestImmuneOrchestrator:
    """Testes do orquestrador imunológico."""

    def test_scan_execution_detecta_nada(self):
        """Scan sem ameaças retorna threat_detected=False."""
        from iaglobal.immunity.immune_orchestrator import ImmuneOrchestrator
        orchestrator = ImmuneOrchestrator()
        
        result = orchestrator.scan_execution(
            "clean_skill",
            {"task": "normal"},
            "output normal",
            {"cpu_seconds": 1.0, "file_ops": 5}
        )
        
        assert result.threat_detected is False
        assert len(result.threats) == 0

    def test_scan_execution_detecta_behavior_anomaly(self):
        """Scan detecta comportamento anômalo."""
        from iaglobal.immunity.immune_orchestrator import ImmuneOrchestrator
        from iaglobal.immunity.mhc_detector import MHCDetector
        
        orchestrator = ImmuneOrchestrator()
        mhc = MHCDetector()
        
        # Registrar skill antes de validar
        mhc.register_skill("spike_skill", "def run(): pass")
        
        result = orchestrator.scan_execution(
            "spike_skill",
            {"task": "cpu spike"},
            "normal output",
            {"cpu_seconds": 20.0, "file_ops": 10, "error": True}
        )
        
        assert result.threat_detected is True
        assert "behavior_anomaly" in result.threats

    def test_health_check(self):
        """Health check retorna status imunológico."""
        from iaglobal.immunity.immune_orchestrator import ImmuneOrchestrator
        orchestrator = ImmuneOrchestrator()
        
        h = orchestrator.health_check()
        
        assert "active_detectors" in h
        assert h["active_detectors"] == 7  # Atualizado com SymbiontDetection


class TestParasiteDetection:
    """Testes de detecção de parasitas digitais."""

    def test_quarantine_if_parasite_unauthorized_path(self):
        """Path não autorizado ativa quarentena imediata."""
        from iaglobal.immunity.mhc_detector import MHCDetector
        
        # Reset quarantine para teste limpo
        quarantine._quarantined.clear()
        quarantine._initialized = True  # Reset não limpa initialized flag
        
        detector = MHCDetector()
        
        result = detector.quarantine_if_parasite("suspicious_skill", {
            "unauthorized_path": "/etc/passwd"
        })
        
        assert result is True
        assert quarantine.is_quarantined("suspicious_skill")

    def test_quarantine_if_parasite_memory_leak(self):
        """Memory leak ativa quarentena."""
        from iaglobal.immunity.mhc_detector import MHCDetector
        
        quarantine._quarantined.clear()
        
        detector = MHCDetector()
        
        result = detector.quarantine_if_parasite("leaky_skill", {
            "memory_leak": True
        })
        
        assert result is True
        assert quarantine.is_quarantined("leaky_skill")

    def test_fingerprint_unico_para_skill(self):
        """Fingerprint deve ser único por código."""
        detector = MHCDetector()
        
        fp1 = detector.register_skill("skill_a", "def a(): pass")
        fp2 = detector.register_skill("skill_b", "def b(): pass")
        
        assert fp1 != fp2