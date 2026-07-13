# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do ResearchConsolidator — Fase 4 (Consolidação).

Cobertura:
  - Geração de markdown estruturado
  - Cálculo de fitness score
  - Persistência em JSON
  - Integração com Obsidian (mock)
  - Pipeline completo
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from iaglobal.agents.ingestion.consolidation import (
    ResearchConsolidator,
    ConsolidatedPaper,
    consolidate_paper,
    consolidate_full_pipeline,
)
from iaglobal.agents.ingestion.paper_parser import PaperMetadata
from iaglobal.agents.ingestion.experiment_runner import ExperimentResult


class TestConsolidatedPaper:
    """Testes da dataclass ConsolidatedPaper."""

    def test_consolidated_paper_creation(self):
        """ConsolidatedPaper deve criar com campos obrigatórios."""
        paper = ConsolidatedPaper(
            paper_id="2401.12345",
            title="Test Paper",
            abstract="Test abstract",
            authors=["Author1"],
            published_date="2024-01-15",
            repository="arxiv",
            topics=["ml"],
            hypotheses_count=3,
            validated_count=2,
            failed_count=1,
            fitness_score=0.67,
            obsidian_path=None,
        )
        assert paper.paper_id == "2401.12345"
        assert paper.fitness_score == 0.67
        assert paper.consolidated_at != ""

    def test_consolidated_paper_to_dict(self):
        """to_dict deve serializar corretamente."""
        paper = ConsolidatedPaper(
            paper_id="2401.67890",
            title="Another Paper",
            abstract="Abstract",
            authors=["Author1", "Author2"],
            published_date="2024-02-20",
            repository="arxiv",
            topics=["nlp"],
            hypotheses_count=5,
            validated_count=5,
            failed_count=0,
            fitness_score=1.0,
            obsidian_path="/path/to/note.md",
        )
        data = paper.to_dict()
        assert data["paper_id"] == "2401.67890"
        assert data["fitness_score"] == 1.0
        assert data["obsidian_path"] == "/path/to/note.md"


class TestResearchConsolidator:
    """Testes do ResearchConsolidator."""

    def test_generate_markdown_structure(self):
        """Markdown deve ter estrutura correta."""
        consolidator = ResearchConsolidator()

        paper = PaperMetadata(
            paper_id="2401.12345",
            title="Deep Learning for NLP",
            abstract="Test abstract about deep learning.",
            authors=["John Doe"],
            published_date="2024-01-15",
            repository="arxiv",
            topics=["deep learning", "nlp"],
        )

        results = [
            ExperimentResult(
                hypothesis_id="H1",
                paper_id="2401.12345",
                success=True,
                confidence=0.85,
                execution_time_ms=100,
                stdout="Success: True",
                stderr="",
                metrics={"acc": 0.92},
                code="",
                validation_details="OK",
            ),
            ExperimentResult(
                hypothesis_id="H2",
                paper_id="2401.12345",
                success=False,
                confidence=0.3,
                execution_time_ms=50,
                stdout="Success: False",
                stderr="",
                metrics={},
                code="",
                validation_details="Failed",
            ),
        ]

        validated = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        fitness = len(validated) / len(results)

        markdown = consolidator._generate_markdown(
            paper, results, validated, failed, fitness
        )

        # Verificar estrutura
        assert "---" in markdown  # Frontmatter
        assert 'id: "2401.12345"' in markdown
        assert 'tipo: "PaperValidado"' in markdown
        assert "fitness_score: 0.50" in markdown
        assert "# Deep Learning for NLP" in markdown
        assert "## Abstract" in markdown
        assert "## Validação Experimental" in markdown
        assert "### Hipóteses Validadas ✅" in markdown
        assert "### Hipóteses Não Validadas ❌" in markdown

    def test_format_metrics(self):
        """Formatação de métricas deve funcionar."""
        consolidator = ResearchConsolidator()

        metrics = {"accuracy": 0.9234, "precision": 0.8876, "n_trials": 100}
        formatted = consolidator._format_metrics(metrics)

        assert "**accuracy**:" in formatted
        assert "0.9234" in formatted
        assert "**n_trials**:" in formatted
        assert "100" in formatted

    def test_format_aggregate_metrics(self):
        """Métricas agregadas devem funcionar."""
        consolidator = ResearchConsolidator()

        results = [
            ExperimentResult(
                hypothesis_id="H1",
                paper_id="2401.001",
                success=True,
                confidence=0.8,
                execution_time_ms=100,
                stdout="",
                stderr="",
                metrics={},
                code="",
                validation_details="",
            ),
            ExperimentResult(
                hypothesis_id="H2",
                paper_id="2401.001",
                success=True,
                confidence=0.9,
                execution_time_ms=150,
                stdout="",
                stderr="",
                metrics={},
                code="",
                validation_details="",
            ),
        ]

        formatted = consolidator._format_aggregate_metrics(results)

        assert "Tempo total" in formatted
        assert "250ms" in formatted  # 100 + 150
        assert "Confiança média" in formatted
        assert "85%" in formatted  # (0.8 + 0.9) / 2
        assert "Taxa de sucesso" in formatted
        assert "100%" in formatted  # 2/2

    def test_generate_conclusion_high_fitness(self):
        """Conclusão deve ser positiva para alto fitness."""
        consolidator = ResearchConsolidator()

        paper = PaperMetadata(
            paper_id="2401.001",
            title="Test",
            abstract="Abstract",
            authors=["A1"],
            published_date="2024",
            repository="arxiv",
            topics=[],
        )

        validated = [1, 2, 3, 4]  # 4 validados
        failed = [5]  # 1 falhado
        fitness = 0.8  # 80%

        conclusion = consolidator._generate_conclusion(
            paper, fitness, validated, failed
        )

        assert "Alta validação" in conclusion
        assert "Recomenda-se" in conclusion

    def test_generate_conclusion_low_fitness(self):
        """Conclusão deve ser crítica para baixo fitness."""
        consolidator = ResearchConsolidator()

        paper = PaperMetadata(
            paper_id="2401.001",
            title="Test",
            abstract="Abstract",
            authors=["A1"],
            published_date="2024",
            repository="arxiv",
            topics=[],
        )

        validated = [1]  # 1 validado
        failed = [2, 3, 4, 5]  # 4 falhados
        fitness = 0.2  # 20%

        conclusion = consolidator._generate_conclusion(
            paper, fitness, validated, failed
        )

        assert "Baixa validação" in conclusion
        assert "revisão crítica" in conclusion.lower()

    @pytest.mark.asyncio
    async def test_consolidate_creates_object(self):
        """consolidate deve criar ConsolidatedPaper."""
        paper = PaperMetadata(
            paper_id="2401.12345",
            title="Test Paper",
            abstract="Test abstract",
            authors=["Author1"],
            published_date="2024-01-15",
            repository="arxiv",
            topics=["ml"],
        )

        results = [
            ExperimentResult(
                hypothesis_id="H1",
                paper_id="2401.12345",
                success=True,
                confidence=0.85,
                execution_time_ms=100,
                stdout="Success",
                stderr="",
                metrics={},
                code="",
                validation_details="OK",
            ),
        ]

        consolidator = ResearchConsolidator()

        with patch.object(
            consolidator, "_write_to_obsidian", new_callable=AsyncMock
        ) as mock_obsidian:
            mock_obsidian.return_value = None  # Sem Obsidian

            with patch.object(consolidator, "_save_consolidated_json"):
                consolidated = await consolidator.consolidate(
                    paper, results, obsidian_enabled=False
                )

                assert consolidated.paper_id == "2401.12345"
                assert consolidated.hypotheses_count == 1
                assert consolidated.validated_count == 1
                assert consolidated.fitness_score == 1.0

    def test_save_consolidated_json_creates_file(self, tmp_path):
        """save_consolidated_json deve criar arquivo JSON."""
        consolidated = ConsolidatedPaper(
            paper_id="2401.12345",
            title="Test",
            abstract="Abstract",
            authors=["A1"],
            published_date="2024",
            repository="arxiv",
            topics=["ml"],
            hypotheses_count=3,
            validated_count=2,
            failed_count=1,
            fitness_score=0.67,
            obsidian_path=None,
        )

        results = [
            ExperimentResult(
                hypothesis_id="H1",
                paper_id="2401.12345",
                success=True,
                confidence=0.8,
                execution_time_ms=100,
                stdout="",
                stderr="",
                metrics={},
                code="",
                validation_details="",
            ),
        ]

        # Criar estrutura de diretórios
        papers_dir = tmp_path / "papers"
        papers_dir.mkdir(parents=True, exist_ok=True)

        with patch("iaglobal.agents.ingestion.consolidation.JSON_DIR", papers_dir):
            consolidator = ResearchConsolidator()
            consolidator._save_consolidated_json(consolidated, results)

            # Verificar arquivo criado
            expected_path = papers_dir / "2401.12345_consolidated.json"
            assert expected_path.exists(), f"Arquivo não criado em {expected_path}"

            data = json.loads(expected_path.read_text())
            assert data["paper"]["paper_id"] == "2401.12345"
            assert data["summary"]["fitness_score"] == 0.67
            assert len(data["experiment_results"]) == 1

    @pytest.mark.asyncio
    async def test_write_to_obsidian_mock(self):
        """_write_to_obsidian deve chamar SubconsciousAPI."""
        consolidator = ResearchConsolidator()

        paper = PaperMetadata(
            paper_id="2401.12345",
            title="Test",
            abstract="Abstract",
            authors=["A1"],
            published_date="2024",
            repository="arxiv",
            topics=["ml", "dl"],
        )

        content = "# Test\nContent"

        # Mock do SubconsciousAPI no módulo obsidian
        with patch("iaglobal.obsidian.subconsciousapi.SubconsciousAPI") as mock_sub:
            mock_instance = mock_sub.return_value
            mock_instance.escrever_longo_prazo = AsyncMock(
                return_value=Path("/obsidian/03_Long_Term/paper_2401_12345.md")
            )

            path = await consolidator._write_to_obsidian(content, paper)

            assert path is not None
            assert "paper_2401_12345" in path
            mock_instance.escrever_longo_prazo.assert_called_once()


class TestConsolidateFunctions:
    """Testes das funções utilitárias."""

    @pytest.mark.asyncio
    async def test_consolidate_paper_function(self):
        """consolidate_paper deve funcionar."""
        paper = PaperMetadata(
            paper_id="2401.001",
            title="Test",
            abstract="Abstract",
            authors=["A1"],
            published_date="2024",
            repository="arxiv",
            topics=[],
        )

        results = [
            ExperimentResult(
                hypothesis_id="H1",
                paper_id="2401.001",
                success=True,
                confidence=0.8,
                execution_time_ms=100,
                stdout="",
                stderr="",
                metrics={},
                code="",
                validation_details="",
            ),
        ]

        with patch(
            "iaglobal.agents.ingestion.consolidation.ResearchConsolidator.consolidate",
            new_callable=AsyncMock,
        ) as mock_consolidate:
            mock_consolidate.return_value = ConsolidatedPaper(
                paper_id="2401.001",
                title="Test",
                abstract="Abstract",
                authors=["A1"],
                published_date="2024",
                repository="arxiv",
                topics=[],
                hypotheses_count=1,
                validated_count=1,
                failed_count=0,
                fitness_score=1.0,
                obsidian_path=None,
            )

            consolidated = await consolidate_paper(
                paper, results, obsidian_enabled=False
            )

            assert consolidated.paper_id == "2401.001"
            assert consolidated.fitness_score == 1.0

    @pytest.mark.asyncio
    async def test_consolidate_full_pipeline(self):
        """consolidate_full_pipeline deve processar pipeline completo."""
        from iaglobal.agents.ingestion.hypothesis_generator import Hypothesis

        paper = PaperMetadata(
            paper_id="2401.001",
            title="Test",
            abstract="Abstract",
            authors=["A1"],
            published_date="2024",
            repository="arxiv",
            topics=["ml"],
        )

        hypotheses = [
            Hypothesis(
                id="H1",
                description="Test",
                method="experiment",
                expected_outcome="Result",
                success_criteria="x > 0.5",
            )
        ]
        results = [
            ExperimentResult(
                hypothesis_id="H1",
                paper_id="2401.001",
                success=True,
                confidence=0.8,
                execution_time_ms=100,
                stdout="",
                stderr="",
                metrics={},
                code="",
                validation_details="",
            ),
        ]

        with patch(
            "iaglobal.agents.ingestion.consolidation.consolidate_paper",
            new_callable=AsyncMock,
        ) as mock_consolidate:
            mock_consolidate.return_value = ConsolidatedPaper(
                paper_id="2401.001",
                title="Test",
                abstract="Abstract",
                authors=["A1"],
                published_date="2024",
                repository="arxiv",
                topics=["ml"],
                hypotheses_count=1,
                validated_count=1,
                failed_count=0,
                fitness_score=1.0,
                obsidian_path=None,
            )

            consolidated = await consolidate_full_pipeline(
                paper, hypotheses, results, obsidian_enabled=False
            )

            assert consolidated.paper_id == "2401.001"
            assert consolidated.hypotheses_count == 1


class TestIntegration:
    """Testes de integração Validação → Consolidação."""

    @pytest.mark.asyncio
    async def test_full_validation_to_consolidation(self):
        """Pipeline: Resultados → Consolidação → JSON."""
        paper = PaperMetadata(
            paper_id="2401.12345",
            title="Deep Learning Improves NLP",
            abstract="We present a novel DL approach for NLP.",
            authors=["John Doe", "Jane Smith"],
            published_date="2024-01-15",
            repository="arxiv",
            topics=["deep learning", "nlp"],
        )

        results = [
            ExperimentResult(
                hypothesis_id="H1",
                paper_id="2401.12345",
                success=True,
                confidence=0.92,
                execution_time_ms=120,
                stdout="Success: True",
                stderr="",
                metrics={"acc": 0.92},
                code="",
                validation_details="OK",
            ),
            ExperimentResult(
                hypothesis_id="H2",
                paper_id="2401.12345",
                success=True,
                confidence=0.88,
                execution_time_ms=95,
                stdout="Success: True",
                stderr="",
                metrics={"f1": 0.88},
                code="",
                validation_details="OK",
            ),
            ExperimentResult(
                hypothesis_id="H3",
                paper_id="2401.12345",
                success=False,
                confidence=0.35,
                execution_time_ms=80,
                stdout="Success: False",
                stderr="",
                metrics={},
                code="",
                validation_details="Failed",
            ),
        ]

        consolidator = ResearchConsolidator()

        with patch.object(
            consolidator, "_write_to_obsidian", new_callable=AsyncMock
        ) as mock_obsidian:
            mock_obsidian.return_value = None

            with patch.object(consolidator, "_save_consolidated_json") as mock_save:
                consolidated = await consolidator.consolidate(
                    paper, results, obsidian_enabled=False
                )

                assert consolidated.fitness_score == pytest.approx(
                    0.67, rel=0.01
                )  # 2/3
                assert consolidated.validated_count == 2
                assert consolidated.failed_count == 1

                # Verificar que markdown foi gerado
                assert mock_save.called
