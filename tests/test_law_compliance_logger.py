# tests/test_law_compliance_logger.py
"""Testes do logger de conformidade das leis universais."""
import pytest

from iaglobal.obsidian.law_compliance_logger import LawComplianceLogger


class TestLawComplianceLogger:
    """Testa registro de conformidade às leis."""

    def test_log_law_application(self):
        logger = LawComplianceLogger()
        
        logger.log_law_application("Lei da Ordem", "test_context", "test_agent")
        
        assert "Lei da Ordem" in logger._counts
        assert logger._counts["Lei da Ordem"] >= 1

    def test_get_top_laws(self):
        logger = LawComplianceLogger()
        
        logger.log_law_application("Lei A", "ctx", "agent")
        logger.log_law_application("Lei A", "ctx", "agent")
        logger.log_law_application("Lei B", "ctx", "agent")
        
        top = logger.get_top_laws(2)
        
        assert len(top) == 2
        assert top[0][0] == "Lei A"

    def test_context_log_structure(self):
        logger = LawComplianceLogger()
        
        logger.log_law_application("Lei C", "ctx", "agent")
        
        assert len(logger._context_log) >= 1
        assert "law" in logger._context_log[-1]