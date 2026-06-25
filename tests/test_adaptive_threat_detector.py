# tests/test_adaptive_threat_detector.py
"""Testes do detector adaptativo de ameaças."""
import pytest

from iaglobal.immunity.adaptive_threat_detector import AdaptiveThreatDetector


class TestAdaptiveThreatDetector:
    """Testa aprendizado contínuo de padrões de ataque."""

    def test_learn_from_approved_skill(self):
        """Aprende padrões de skills aprovadas."""
        detector = AdaptiveThreatDetector()
        
        detector.learn_from_approved_skill("test_skill", "def run(): return 'safe'")
        
        whitelist = detector.get_benign_whitelist()
        assert len(whitelist) >= 1

    def test_scan_for_emerging_threats_detected(self):
        """Detecta padrões emergentes."""
        detector = AdaptiveThreatDetector()
        
        result = detector.scan_for_emerging_threats("code = eval(user_input)")
        
        assert result["is_threat"] is True
        assert "eval(" in result.get("indicators", [])

    def test_scan_for_emerging_threats_clean(self):
        """Não detecta ameaça em código limpo."""
        detector = AdaptiveThreatDetector()
        
        result = detector.scan_for_emerging_threats("def run(): return 'hello world'")
        
        assert result["is_threat"] is False

    def test_extract_failure_patterns(self):
        """Extrai padrões de falha."""
        detector = AdaptiveThreatDetector()
        
        # Test via learn_from_approved_skill
        detector.learn_from_approved_skill("clean_skill", "def safe(): pass")
        
        result = detector.scan_for_emerging_threats("import os; os.system('rm -rf /')")
        
        assert result["is_threat"] is True