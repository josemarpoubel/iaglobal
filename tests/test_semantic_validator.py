# test_semantic_validator.py

from __future__ import annotations

import pytest
import re
from unittest.mock import AsyncMock, patch

from semantic_validator import (
    DEFAULT_PASS_THRESHOLD,
    HtmlStructureRule,
    KeywordPresenceRule,
    Language,
    LanguageDetector,
    PythonImportHashlibRule,
    PythonStructureRule,
    RuleRegistry,
    RuleResult,
    ScoreAggregator,
    SemanticValidatorAgent,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def agent():
    return SemanticValidatorAgent()

@pytest.fixture
def sample_code():
    return """
import hashlib
def compute_sha3(data: bytes) -> str:
    return hashlib.sha3_512(data).hexdigest()
"""

# ─────────────────────────────────────────────────────────────────────────────
# Testes de Linguagem (Parametrizados)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code,expected_lang", [
    ("import os; print('hi')", Language.PYTHON),
    ("<!DOCTYPE html><html></html>", Language.HTML),
    ("SELECT * FROM table", Language.GENERIC),
    ("", Language.GENERIC),
])
@pytest.mark.asyncio
async def test_language_detection(code, expected_lang):
    lang = await LanguageDetector.detect(code)
    assert lang == expected_lang

# ─────────────────────────────────────────────────────────────────────────────
# Testes de Regras (Unitários)
# ─────────────────────────────────────────────────────────────────────────────

class TestRules:
    @pytest.mark.asyncio
    async def test_python_structure_rule(self):
        rule = PythonStructureRule()
        # Passa
        r = await rule.evaluate("def foo(): pass", "", Language.PYTHON)
        assert r.passed
        # Falha
        r = await rule.evaluate("x = 1", "criar função", Language.PYTHON)
        assert not r.passed

    @pytest.mark.asyncio
    async def test_keyword_presence_rule(self):
        rule = KeywordPresenceRule(
            name="req_sha3", weight=10.0, category="crypto",
            pattern=re.compile(r"sha3", re.IGNORECASE), label="SHA3"
        )
        r = await rule.evaluate("hashlib.sha3_512()", "usar sha3", Language.PYTHON)
        assert r.passed

# ─────────────────────────────────────────────────────────────────────────────
# Testes do Agente (Integração e Resiliência)
# ─────────────────────────────────────────────────────────────────────────────

class TestSemanticValidatorAgent:

    @pytest.mark.asyncio
    async def test_validate_async_success(self, agent, sample_code):
        result = await agent.validate_async(sample_code, "criar blockchain com sha3")
        assert result.valid is True
        assert result.score > 0

    @pytest.mark.asyncio
    async def test_agent_handles_engine_exception(self, agent):
        """Testa se o agente trata falhas internas do engine sem quebrar o loop."""
        with patch.object(agent.engine, 'validate', side_effect=Exception("Engine Crash")):
            result = await agent.validate_async("code", "task")
            assert result.valid is False
            assert "Engine Crash" in str(result.errors)

    @pytest.mark.asyncio
    async def test_legacy_sync_compatibility(self, agent, sample_code):
        """Garante que a fachada síncrona ainda retorne o formato esperado."""
        result = agent.validate(sample_code, "task")
        assert isinstance(result, dict)
        assert "valid" in result
        assert "score" in result

# ─────────────────────────────────────────────────────────────────────────────
# Testes de Score
# ─────────────────────────────────────────────────────────────────────────────

def test_score_aggregator_logic():
    results = [
        RuleResult(name="r1", description="", passed=True, weight=50.0, category="a"),
        RuleResult(name="r2", description="", passed=False, weight=50.0, category="b")
    ]
    score, by_cat, errors, _ = ScoreAggregator.aggregate(results)
    assert score == 50.0
    assert by_cat["a"] == 100.0
    assert by_cat["b"] == 0.0
