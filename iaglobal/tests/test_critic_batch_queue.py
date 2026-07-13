# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Tests for CriticBatchQueue — avaliação com contexto cruzado."""

import pytest

from iaglobal.core.critic_batch_queue import CriticBatchQueue


class TestCriticBatchQueue:
    """Valida extração de contexto, prompt cruzado, parse e fallback."""

    def test_extract_evaluation_summary_with_issues(self):
        eval_dict = {
            "score": 75.0,
            "approved": True,
            "issues": ["minor style", "use f-strings"],
        }
        summary = CriticBatchQueue._extract_evaluation_summary(eval_dict, "Revisor")
        assert "score=75" in summary
        assert "aprovado=True" in summary
        assert "minor style" in summary

    def test_extract_evaluation_summary_empty(self):
        summary = CriticBatchQueue._extract_evaluation_summary({}, "QA")
        assert summary == ""

    def test_extract_evaluation_summary_none(self):
        summary = CriticBatchQueue._extract_evaluation_summary(None, "QA")
        assert summary == ""

    def test_montar_prompt_cruzado_includes_context(self):
        prompt = CriticBatchQueue._montar_prompt_cruzado(
            task="fazer api",
            output="def api(): pass",
            reviewer="Revisor: score=80 aprovado=True",
            qa="QA: score=60 aprovado=True",
        )
        assert "[Revisor]" in prompt
        assert "[QA]" in prompt
        assert "Revisor: score=80" in prompt
        assert "QA: score=60" in prompt
        assert "fazer api" in prompt
        assert "def api(): pass" in prompt
        assert "validacao cruzada" in prompt.lower()

    def test_montar_prompt_cruzado_no_context(self):
        prompt = CriticBatchQueue._montar_prompt_cruzado(
            task="x",
            output="y",
            reviewer="",
            qa="",
        )
        assert "Nenhuma avaliacao previa" in prompt
        assert "[Reviewer]" not in prompt
        assert "[QA]" not in prompt

    def test_parse_resposta_valid_json(self):
        raw = '{"approved": true, "score": 85, "issues": ["minor"], "fix_suggestions": [], "summary": "ok"}'
        result = CriticBatchQueue._parse_resposta(raw)
        assert result["approved"] is True
        assert result["score"] == 85.0
        assert result["issues"] == ["minor"]

    def test_parse_resposta_rejected(self):
        raw = '{"approved": false, "score": 30, "issues": ["error"], "fix_suggestions": ["fix"], "summary": "bad"}'
        result = CriticBatchQueue._parse_resposta(raw)
        assert result["approved"] is False
        assert result["score"] == 30.0
        assert result["fix_suggestions"] == ["fix"]

    def test_parse_resposta_malformed_returns_fallback(self):
        result = CriticBatchQueue._parse_resposta("not json at all")
        assert result["approved"] is False
        assert result["score"] == 0.0
        assert "indispon" in result["issues"][0]

    def test_parse_resposta_empty_returns_fallback(self):
        result = CriticBatchQueue._parse_resposta("")
        assert result["approved"] is False

    def test_fallback_returns_expected_structure(self):
        fallback = CriticBatchQueue._fallback()
        assert "approved" in fallback
        assert "score" in fallback
        assert "issues" in fallback
        assert "fix_suggestions" in fallback
        assert "summary" in fallback
        assert fallback["approved"] is False

    def test_parse_resposta_clamps_score_range(self):
        raw = '{"approved": true, "score": 150, "issues": [], "fix_suggestions": [], "summary": ""}'
        result = CriticBatchQueue._parse_resposta(raw)
        assert result["score"] <= 100

    def test_parse_resposta_adds_issue_for_low_score(self):
        raw = '{"approved": false, "score": 20, "issues": [], "fix_suggestions": [], "summary": ""}'
        result = CriticBatchQueue._parse_resposta(raw)
        assert len(result["issues"]) >= 1

    @pytest.mark.asyncio
    async def test_get_instance_returns_singleton(self):
        q1 = await CriticBatchQueue.get_instance()
        q2 = await CriticBatchQueue.get_instance()
        assert q1 is q2
