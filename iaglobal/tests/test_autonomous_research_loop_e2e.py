# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Teste End-to-End do Autonomous Research Loop — Pipeline Completo.

Critério de conclusão: 1 paper → 3 hipóteses → 1 experimento → persistência sem intervenção.

Este teste integra TODOS os módulos:
1. Ingestão (PaperIngestor)
2. Parser (PaperParser)
3. Síntese (HypothesisGenerator)
4. Validação (ExperimentRunner)
5. Consolidação (ResearchConsolidator)
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from iaglobal.agents.ingestion import (
    PaperIngestor,
    PaperParser,
    PaperMetadata,
    HypothesisGenerator,
    Hypothesis,
    ExperimentRunner,
    ExperimentResult,
    ResearchConsolidator,
)


class TestAutonomousResearchLoopE2E:
    """Teste end-to-end completo do pipeline."""

    @pytest.mark.asyncio
    async def test_full_autonomous_research_loop(self, tmp_path):
        """
        Pipeline completo:
        1. Paper → Ingestão
        2. PDF → Parser → Metadados
        3. Abstract → 3 Hipóteses
        4. Hipóteses → Experimentos → Resultados
        5. Resultados → Consolidação → Obsidian
        """
        # Setup de diretórios
        papers_dir = tmp_path / "papers"
        papers_dir.mkdir(parents=True, exist_ok=True)

        queue_file = tmp_path / "research_queue.json"
        queue_file.write_text(json.dumps({"queue": [], "stats": {}}))

        json_dir = tmp_path / "json"
        json_dir.mkdir(parents=True, exist_ok=True)

        # === FASE 1: INGESTÃO ===
        mock_paper_content = """
        Deep Learning for Natural Language Processing
        
        Abstract: We present a novel deep learning approach for natural language
        processing that achieves state-of-the-art results on benchmark datasets.
        Our transformer-based architecture improves accuracy by 15% over baselines.
        
        Keywords: deep learning, natural language processing, transformers
        Authors: John Doe, Jane Smith
        Published: 2024-01-15
        arXiv:2401.12345
        """

        mock_paper_path = papers_dir / "2401_12345.txt"
        mock_paper_path.write_text(mock_paper_content)

        with patch(
            "iaglobal.agents.ingestion.paper_ingestor.RESEARCH_QUEUE_FILE", queue_file
        ):
            with patch.object(
                PaperIngestor, "_download_paper", new_callable=AsyncMock
            ) as mock_download:
                mock_download.return_value = mock_paper_path

                ingestor = PaperIngestor(download_dir=papers_dir)
                local_path = await ingestor.ingest("2401.12345", "arxiv")

                assert local_path is not None
                assert local_path.exists()

                # Verificar fila
                queue_data = ingestor._load_queue()
                assert len(queue_data["queue"]) == 1
                assert queue_data["queue"][0]["status"] == "ingested"

        # === FASE 2: PARSER ===
        from iaglobal.agents.ingestion.file_ingestion_agent import FileIngestionAgent

        result = FileIngestionAgent.ingest([str(local_path)])
        assert result["file_count"] == 1
        content = result["files"][0]["content"]

        parser = PaperParser()
        metadata = await parser.parse(content, "2401.12345", "arxiv")

        assert metadata is not None
        assert "deep learning" in metadata.title.lower()
        assert len(metadata.abstract) > 50
        assert len(metadata.authors) >= 2
        assert len(metadata.topics) > 0

        # === FASE 3: SÍNTESE (HIPÓTESES) ===
        mock_hypotheses_response = {
            "hypotheses": [
                {
                    "id": "H1",
                    "description": "DL improves NLP accuracy by >10%",
                    "method": "experiment",
                    "expected_outcome": "Accuracy improvement ≥ 10%",
                    "success_criteria": "acc_dl > acc_baseline * 1.10",
                },
                {
                    "id": "H2",
                    "description": "Method generalizes across 5+ languages",
                    "method": "data_analysis",
                    "expected_outcome": "Similar performance in multiple languages",
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
        with patch.object(generator, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_hypotheses_response

            hypotheses = await generator.generate(metadata)

            assert len(hypotheses) == 3
            assert hypotheses[0].id == "H1"
            assert hypotheses[0].method == "experiment"

            # Validar schema
            validations = generator.validate_hypotheses(hypotheses)
            assert all(validations), "Todas as hipóteses devem ser válidas"

        # === FASE 4: VALIDAÇÃO (EXPERIMENTOS) ===
        runner = ExperimentRunner()
        results = []

        for hyp in hypotheses:
            with patch.object(
                runner, "_generate_code", new_callable=AsyncMock
            ) as mock_gen:
                mock_gen.return_value = "print('Success: True'); print('metric: 0.92')"

                with patch.object(
                    runner, "_execute_in_sandbox", new_callable=AsyncMock
                ) as mock_exec:
                    mock_exec.return_value = {
                        "success": True,
                        "stdout": "Success: True\nmetric: 0.92",
                        "stderr": "",
                    }

                    result = await runner.run_experiment(hyp)
                    results.append(result)

        assert len(results) == 3
        assert all(r.success for r in results), "Todos experimentos devem ter sucesso"
        assert all(r.confidence > 0.5 for r in results)

        # === FASE 5: CONSOLIDAÇÃO ===
        consolidator = ResearchConsolidator()

        with patch.object(
            consolidator, "_write_to_obsidian", new_callable=AsyncMock
        ) as mock_obsidian:
            mock_obsidian.return_value = None  # Sem Obsidian real

            with patch.object(consolidator, "_save_consolidated_json") as mock_save:
                consolidated = await consolidator.consolidate(
                    metadata, results, obsidian_enabled=False
                )

                assert consolidated.paper_id == "2401.12345"
                assert consolidated.hypotheses_count == 3
                assert consolidated.validated_count == 3
                assert consolidated.fitness_score == 1.0
                assert mock_save.called

        # === VERIFICAÇÃO FINAL ===
        # Critério de conclusão: 1 paper → 3 hipóteses → 3 experimentos → consolidação
        assert local_path.exists(), "Ingestão falhou"
        assert metadata is not None, "Parser falhou"
        assert len(hypotheses) == 3, "Síntese falhou"
        assert len(results) == 3, "Validação falhou"
        assert consolidated.fitness_score == 1.0, "Consolidação falhou"

        print("✅ Autonomous Research Loop COMPLETO:")
        print(f"   1. Ingestão: {local_path}")
        print(f"   2. Parser: {metadata.title}")
        print(f"   3. Hipóteses: {len(hypotheses)} geradas")
        print(f"   4. Validação: {len(results)}/{len(results)} sucesso")
        print(f"   5. Consolidação: fitness={consolidated.fitness_score:.0%}")


class TestAutonomousResearchLoopWithFailures:
    """Teste com hipóteses falhadas para validar resiliência."""

    @pytest.mark.asyncio
    async def test_pipeline_with_mixed_results(self, tmp_path):
        """Pipeline onde algumas hipóteses falham."""
        # Paper mock
        metadata = PaperMetadata(
            paper_id="2401.99999",
            title="Controversial Claim Paper",
            abstract="Claims that may not hold up to scrutiny.",
            authors=["Skeptic Author"],
            published_date="2024-03-20",
            repository="arxiv",
            topics=["controversial"],
        )

        # 3 hipóteses: 1 passa, 2 falham
        hypotheses = [
            Hypothesis(
                id="H1",
                description="Claim 1",
                method="experiment",
                expected_outcome="Result",
                success_criteria="x > 0.5",
            ),
            Hypothesis(
                id="H2",
                description="Claim 2",
                method="experiment",
                expected_outcome="Result",
                success_criteria="y > 0.5",
            ),
            Hypothesis(
                id="H3",
                description="Claim 3",
                method="experiment",
                expected_outcome="Result",
                success_criteria="z > 0.5",
            ),
        ]

        results = [
            ExperimentResult(
                hypothesis_id="H1",
                paper_id="2401.99999",
                success=True,
                confidence=0.85,
                execution_time_ms=100,
                stdout="Success",
                stderr="",
                metrics={},
                code="",
                validation_details="OK",
            ),
            ExperimentResult(
                hypothesis_id="H2",
                paper_id="2401.99999",
                success=False,
                confidence=0.3,
                execution_time_ms=50,
                stdout="Failed",
                stderr="",
                metrics={},
                code="",
                validation_details="Failed",
            ),
            ExperimentResult(
                hypothesis_id="H3",
                paper_id="2401.99999",
                success=False,
                confidence=0.2,
                execution_time_ms=60,
                stdout="Failed",
                stderr="",
                metrics={},
                code="",
                validation_details="Failed",
            ),
        ]

        # Consolidação
        consolidator = ResearchConsolidator()

        with patch.object(consolidator, "_save_consolidated_json"):
            consolidated = await consolidator.consolidate(
                metadata, results, obsidian_enabled=False
            )

            # Verificar resiliência
            assert consolidated.hypotheses_count == 3
            assert consolidated.validated_count == 1
            assert consolidated.failed_count == 2
            assert consolidated.fitness_score == pytest.approx(1 / 3, rel=0.01)

            # Conclusão deve ser crítica (baixo fitness)
            markdown = consolidator._generate_markdown(
                metadata,
                results,
                [r for r in results if r.success],
                [r for r in results if not r.success],
                consolidated.fitness_score,
            )

            assert "Baixa validação" in markdown or "Validação moderada" in markdown


class TestPipelineIntegration:
    """Testes de integração com o resto do iaglobal."""

    def test_all_modules_importable(self):
        """Todos os módulos devem ser importáveis."""
        from iaglobal.agents.ingestion import (
            PaperIngestor,
            PaperParser,
            HypothesisGenerator,
            ExperimentRunner,
            ResearchConsolidator,
        )

        assert PaperIngestor is not None
        assert PaperParser is not None
        assert HypothesisGenerator is not None
        assert ExperimentRunner is not None
        assert ResearchConsolidator is not None

    def test_lineage_marker_present(self):
        """Todos os arquivos devem ter LINEAGE_MARKER."""
        import re

        modules = [
            "paper_ingestor",
            "paper_parser",
            "hypothesis_generator",
            "experiment_runner",
            "consolidation",
        ]

        for module_name in modules:
            module_path = (
                Path(__file__).parent.parent
                / "iaglobal"
                / "agents"
                / "ingestion"
                / f"{module_name}.py"
            )
            content = module_path.read_text(encoding="utf-8")

            assert "# 🧬 LINEAGE_MARKER:" in content, (
                f"{module_name}.py não tem LINEAGE_MARKER"
            )
            # Verificar hash do genesis
            marker_match = re.search(r"LINEAGE_MARKER:\s*([a-f0-9]{128})", content)
            assert marker_match, f"{module_name}.py tem LINEAGE_MARKER inválido"
