# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do HypothesisGenerator — Fase 2 (Síntese).

Cobertura:
  - Geração de 3 hipóteses a partir de abstract
  - Validação de schema
  - Fallback quando LLM falha
  - Persistência em JSON
"""

import json
import pytest
from unittest.mock import AsyncMock, patch

from iaglobal.agents.ingestion.hypothesis_generator import (
    HypothesisGenerator,
    Hypothesis,
    validate_hypothesis_schema,
)
from iaglobal.agents.ingestion.paper_parser import PaperMetadata


class TestHypothesis:
    """Testes da dataclass Hypothesis."""

    def test_hypothesis_creation(self):
        """Hypothesis deve criar com campos obrigatórios."""
        hyp = Hypothesis(
            id="H1",
            description="Test hypothesis",
            method="experiment",
            expected_outcome="Expected result",
            success_criteria="metric > 0.9",
        )
        assert hyp.id == "H1"
        assert hyp.method == "experiment"
        assert hyp.status == "pending"

    def test_hypothesis_to_dict(self):
        """to_dict deve serializar corretamente."""
        hyp = Hypothesis(
            id="H2",
            description="Another test",
            method="data_analysis",
            expected_outcome="Result",
            success_criteria="p < 0.05",
        )
        data = hyp.to_dict()
        assert data["id"] == "H2"
        assert data["method"] == "data_analysis"
        assert data["status"] == "pending"


class TestHypothesisGenerator:
    """Testes do HypothesisGenerator."""

    def test_prompt_template_formatting(self):
        """Prompt template deve formatar corretamente."""
        paper = PaperMetadata(
            paper_id="2401.12345",
            title="Test Paper",
            abstract="Test abstract about machine learning",
            authors=["Author1", "Author2"],
            published_date="2024-01-15",
            repository="arxiv",
            topics=["machine learning", "deep learning"],
        )

        generator = HypothesisGenerator()
        prompt = generator.PROMPT_TEMPLATE.format(
            title=paper.title,
            abstract=paper.abstract,
            topics=", ".join(paper.topics),
            authors=", ".join(paper.authors),
        )

        assert "Test Paper" in prompt
        assert "Test abstract" in prompt
        assert "machine learning" in prompt
        assert "Author1" in prompt

    def test_extract_json_from_response_plain_json(self):
        """Deve extrair JSON plano da resposta."""
        generator = HypothesisGenerator()
        response = '{"hypotheses": [{"id": "H1"}]}'
        extracted = generator._extract_json_from_response(response)
        assert extracted == response

    def test_extract_json_from_response_markdown(self):
        """Deve extrair JSON de bloco markdown."""
        generator = HypothesisGenerator()
        response = """
        Aqui está o JSON:
        ```json
        {"hypotheses": [{"id": "H1", "description": "test"}]}
        ```
        """
        extracted = generator._extract_json_from_response(response)
        assert extracted is not None
        assert '"hypotheses"' in extracted

    def test_extract_json_from_response_nested(self):
        """Deve extrair JSON com chaves aninhadas."""
        generator = HypothesisGenerator()
        response = """
        Some text before
        {"hypotheses": [{"id": "H1", "data": {"nested": true}}]}
        Some text after
        """
        extracted = generator._extract_json_from_response(response)
        assert extracted is not None
        assert '"hypotheses"' in extracted

    def test_fallback_hypotheses_generation(self):
        """Fallback deve gerar 3 hipóteses válidas."""
        paper = PaperMetadata(
            paper_id="2401.12345",
            title="Test Paper",
            abstract="Test abstract",
            authors=["Author1"],
            published_date="2024-01-15",
            repository="arxiv",
            topics=["deep learning", "nlp", "transformers"],
        )

        generator = HypothesisGenerator()
        hypotheses = generator._fallback_hypotheses(paper)

        assert len(hypotheses) == 3
        assert hypotheses[0].id == "H1"
        assert hypotheses[0].method == "experiment"
        assert hypotheses[1].method == "data_analysis"
        assert hypotheses[2].method == "simulation"

        for hyp in hypotheses:
            assert len(hyp.description) > 10
            assert len(hyp.success_criteria) > 5

    @pytest.mark.asyncio
    async def test_generate_with_mock_llm(self):
        """generate deve chamar LLM e retornar 3 hipóteses."""
        paper = PaperMetadata(
            paper_id="2401.12345",
            title="Test Paper",
            abstract="Test abstract about deep learning",
            authors=["Author1"],
            published_date="2024-01-15",
            repository="arxiv",
            topics=["deep learning"],
        )

        mock_response = {
            "hypotheses": [
                {
                    "id": "H1",
                    "description": "H1 test",
                    "method": "experiment",
                    "expected_outcome": "Result1",
                    "success_criteria": "metric > 0.9",
                },
                {
                    "id": "H2",
                    "description": "H2 test",
                    "method": "data_analysis",
                    "expected_outcome": "Result2",
                    "success_criteria": "p < 0.05",
                },
                {
                    "id": "H3",
                    "description": "H3 test",
                    "method": "simulation",
                    "expected_outcome": "Result3",
                    "success_criteria": "time < 1.0",
                },
            ]
        }

        generator = HypothesisGenerator()
        with patch.object(generator, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            hypotheses = await generator.generate(paper)

            assert len(hypotheses) == 3
            assert hypotheses[0].id == "H1"
            assert hypotheses[0].method == "experiment"

    @pytest.mark.asyncio
    async def test_generate_with_llm_failure_uses_fallback(self):
        """generate deve usar fallback quando LLM falha."""
        paper = PaperMetadata(
            paper_id="2401.12345",
            title="Test Paper",
            abstract="Test abstract",
            authors=["Author1"],
            published_date="2024-01-15",
            repository="arxiv",
            topics=["topic1"],
        )

        generator = HypothesisGenerator()
        with patch.object(generator, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = None  # LLM falhou
            hypotheses = await generator.generate(paper)

            assert len(hypotheses) == 3
            assert hypotheses[0].id == "H1"
            # Verificar que são hipóteses fallback (genéricas)
            assert (
                "topic1" in hypotheses[0].description.lower()
                or "method" in hypotheses[0].description.lower()
            )

    def test_save_hypotheses_creates_json(self, tmp_path):
        """save_hypotheses deve criar arquivo JSON."""
        hypotheses = [
            Hypothesis(
                id="H1",
                description="Test",
                method="experiment",
                expected_outcome="Result",
                success_criteria="metric > 0.9",
            ),
            Hypothesis(
                id="H2",
                description="Test2",
                method="data_analysis",
                expected_outcome="Result2",
                success_criteria="p < 0.05",
            ),
        ]

        with patch(
            "iaglobal.agents.ingestion.hypothesis_generator.JSON_DIR",
            tmp_path / "papers",
        ):
            generator = HypothesisGenerator()
            output_path = generator.save_hypotheses(hypotheses, "2401.12345")

            assert output_path.exists()
            data = json.loads(output_path.read_text())
            assert data["paper_id"] == "2401.12345"
            assert len(data["hypotheses"]) == 2
            assert data["count"] == 2

    def test_validate_hypotheses_schema(self):
        """validate_hypotheses deve validar schema de cada hipótese."""
        hypotheses = [
            Hypothesis(
                id="H1",
                description="Valid hypothesis with enough text",
                method="experiment",
                expected_outcome="Result",
                success_criteria="metric > 0.9",
            ),
            Hypothesis(
                id="H2",
                description="Short",
                method="invalid_method",
                expected_outcome="Result",
                success_criteria="x",
            ),  # Inválida
            Hypothesis(
                id="H3",
                description="Another valid hypothesis here",
                method="simulation",
                expected_outcome="Result",
                success_criteria="time < 1.0",
            ),
        ]

        generator = HypothesisGenerator()
        results = generator.validate_hypotheses(hypotheses)

        assert results[0] == True  # Válida
        assert results[1] == False  # Inválida (method + description curtos)
        assert results[2] == True  # Válida


class TestValidateHypothesisSchema:
    """Testes da função validate_hypothesis_schema."""

    def test_valid_hypothesis(self):
        """Hipótese válida deve passar."""
        hyp = {
            "id": "H1",
            "description": "This is a valid hypothesis description",
            "method": "experiment",
            "expected_outcome": "Expected result",
            "success_criteria": "metric > 0.9",
        }
        assert validate_hypothesis_schema(hyp) == True

    def test_missing_required_fields(self):
        """Campos obrigatórios faltando deve falhar."""
        hyp = {
            "id": "H1",
            "description": "Test",
            # Falta method, expected_outcome, success_criteria
        }
        assert validate_hypothesis_schema(hyp) == False

    def test_invalid_method(self):
        """Método inválido deve falhar."""
        hyp = {
            "id": "H1",
            "description": "Test hypothesis",
            "method": "invalid_method",
            "expected_outcome": "Result",
            "success_criteria": "metric > 0.9",
        }
        assert validate_hypothesis_schema(hyp) == False

    def test_description_too_short(self):
        """Descrição muito curta deve falhar."""
        hyp = {
            "id": "H1",
            "description": "Short",
            "method": "experiment",
            "expected_outcome": "Result",
            "success_criteria": "metric > 0.9",
        }
        assert validate_hypothesis_schema(hyp) == False


class TestIntegration:
    """Testes de integração Ingestão → Síntese."""

    @pytest.mark.asyncio
    async def test_paper_to_hypotheses_pipeline(self, tmp_path):
        """Pipeline: Paper → Abstract → 3 Hipóteses."""
        # Mock paper
        paper = PaperMetadata(
            paper_id="2401.12345",
            title="Deep Learning for NLP",
            abstract="We present a novel deep learning approach for natural language processing that achieves state-of-the-art results on benchmark datasets.",
            authors=["John Doe", "Jane Smith"],
            published_date="2024-01-15",
            repository="arxiv",
            topics=["deep learning", "nlp", "transformers"],
        )

        # Mock LLM response
        mock_response = {
            "hypotheses": [
                {
                    "id": "H1",
                    "description": "DL improves NLP accuracy by >10%",
                    "method": "experiment",
                    "expected_outcome": "Accuracy improvement",
                    "success_criteria": "acc_dl > acc_baseline * 1.10",
                },
                {
                    "id": "H2",
                    "description": "Method generalizes across languages",
                    "method": "data_analysis",
                    "expected_outcome": "Similar performance in 5+ languages",
                    "success_criteria": "std(performance) < 0.05",
                },
                {
                    "id": "H3",
                    "description": "Transformer attention is interpretable",
                    "method": "simulation",
                    "expected_outcome": "Attention maps align with syntax",
                    "success_criteria": "correlation > 0.7",
                },
            ]
        }

        generator = HypothesisGenerator()
        with patch.object(generator, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            # Gerar hipóteses
            hypotheses = await generator.generate(paper)

            assert len(hypotheses) == 3
            assert all(h.paper_id == "2401.12345" for h in hypotheses)

            # Validar
            validation_results = generator.validate_hypotheses(hypotheses)
            assert all(validation_results)  # Todas válidas

            # Salvar
            with patch(
                "iaglobal.agents.ingestion.hypothesis_generator.JSON_DIR",
                tmp_path / "papers",
            ):
                output_path = generator.save_hypotheses(hypotheses, "2401.12345")
                assert output_path.exists()

                data = json.loads(output_path.read_text())
                assert data["count"] == 3
                assert "generated_at" in data
