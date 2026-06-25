# tests/test_ai_audit_compliance.py
"""Testes da auditoria de conformidade às leis universais."""
import pytest

from iaglobal.graphs.nodes.no_ai_audit_compliance import run_ai_audit_compliance


class TestAIAuditCompliance:
    """Testa auditoria de conformidade."""

    async def test_compliance_pass(self):
        """Auditoria passa com reasoning válido."""
        result = await run_ai_audit_compliance({
            "agent_name": "test_agent",
            "reasoning": "Bref analysis of the task with clear steps",
            "task": "optimize routing"
        })
        
        assert result["conforme"] is True

    async def test_compliance_fail_no_reasoning(self):
        """Auditoria falha sem reasoning."""
        result = await run_ai_audit_compliance({
            "agent_name": "test_agent",
            "reasoning": "",
            "task": "undefined"
        })
        
        assert "Lei do Pensamento" in str(result["violacoes"])