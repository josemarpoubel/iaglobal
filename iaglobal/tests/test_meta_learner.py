# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do MetaLearner — Fase 5 (Meta-aprendizado).

Cobertura:
  - Meta-análise após N papers
  - Curadoria de baixa qualidade
  - Recomendações baseadas em fitness
  - Citações cruzadas
  - Replicação automática
"""

import json
import pytest
from unittest.mock import AsyncMock, patch

from iaglobal.agents.ingestion.meta_learner import (
    MetaLearner,
    PaperRecommendation,
    MetaAnalysis,
    run_meta_learning,
)


class TestPaperRecommendation:
    """Testes da dataclass PaperRecommendation."""

    def test_recommendation_creation(self):
        """PaperRecommendation deve criar com campos obrigatórios."""
        rec = PaperRecommendation(
            paper_id="2401.12345",
            title="Test Paper",
            topics=["ml", "dl"],
            predicted_fitness=0.85,
            reason="High fitness in ML",
            similar_to=["2401.001"],
        )
        assert rec.paper_id == "2401.12345"
        assert rec.predicted_fitness == 0.85
        assert len(rec.topics) == 2

    def test_recommendation_to_dict(self):
        """to_dict deve serializar corretamente."""
        rec = PaperRecommendation(
            paper_id="2401.67890",
            title="Another Paper",
            topics=["nlp"],
            predicted_fitness=0.92,
            reason="Match",
            similar_to=[],
        )
        data = rec.to_dict()
        assert data["paper_id"] == "2401.67890"
        assert data["predicted_fitness"] == 0.92


class TestMetaAnalysis:
    """Testes da dataclass MetaAnalysis."""

    def test_meta_analysis_creation(self):
        """MetaAnalysis deve criar com campos obrigatórios."""
        analysis = MetaAnalysis(
            total_papers=10,
            total_hypotheses=30,
            validated_hypotheses=20,
            overall_fitness=0.67,
            top_topics=[("ml", 5), ("dl", 3)],
            low_fitness_papers=["2401.001"],
            high_fitness_papers=["2401.002", "2401.003"],
            replication_candidates=["2401.004"],
        )
        assert analysis.total_papers == 10
        assert analysis.overall_fitness == 0.67
        assert analysis.generated_at != ""

    def test_meta_analysis_to_dict(self):
        """to_dict deve serializar corretamente."""
        analysis = MetaAnalysis(
            total_papers=5,
            total_hypotheses=15,
            validated_hypotheses=12,
            overall_fitness=0.8,
            top_topics=[("nlp", 3)],
            low_fitness_papers=[],
            high_fitness_papers=["2401.001"],
            replication_candidates=[],
        )
        data = analysis.to_dict()
        assert data["total_papers"] == 5
        assert data["overall_fitness"] == 0.8
        assert len(data["top_topics"]) == 1


class TestMetaLearner:
    """Testes do MetaLearner."""

    @pytest.mark.asyncio
    async def test_load_consolidated_papers_empty(self, tmp_path):
        """load_consolidated_papers deve retornar lista vazia se não houver papers."""
        learner = MetaLearner()
        learner.consolidated_dir = tmp_path / "papers"
        learner.consolidated_dir.mkdir(parents=True, exist_ok=True)

        papers = await learner.load_consolidated_papers()
        assert len(papers) == 0

    @pytest.mark.asyncio
    async def test_load_consolidated_papers(self, tmp_path):
        """load_consolidated_papers deve carregar papers consolidados."""
        learner = MetaLearner()
        learner.consolidated_dir = tmp_path / "papers"
        learner.consolidated_dir.mkdir(parents=True, exist_ok=True)

        # Criar papers mock
        for i in range(3):
            paper_data = {
                "paper": {
                    "paper_id": f"2401.{i:03d}",
                    "title": f"Paper {i}",
                    "topics": ["ml"],
                },
                "summary": {
                    "total_hypotheses": 3,
                    "validated": 2,
                    "fitness_score": 0.67,
                },
            }
            paper_file = learner.consolidated_dir / f"2401_{i:03d}_consolidated.json"
            paper_file.write_text(json.dumps(paper_data, indent=2))

        papers = await learner.load_consolidated_papers()
        assert len(papers) == 3
        # Ordenar por paper_id para asserção consistente
        paper_ids = sorted([p["paper"]["paper_id"] for p in papers])
        assert paper_ids == ["2401.000", "2401.001", "2401.002"]

    @pytest.mark.asyncio
    async def test_generate_meta_analysis_insufficient_papers(self, tmp_path):
        """generate_meta_analysis deve retornar None se < min_papers."""
        learner = MetaLearner()
        learner.consolidated_dir = tmp_path / "papers"
        learner.consolidated_dir.mkdir(parents=True, exist_ok=True)

        # Criar apenas 2 papers (min_papers=5)
        for i in range(2):
            paper_data = {
                "paper": {
                    "paper_id": f"2401.{i:03d}",
                    "title": f"Paper {i}",
                    "topics": ["ml"],
                },
                "summary": {
                    "total_hypotheses": 3,
                    "validated": 2,
                    "fitness_score": 0.67,
                },
            }
            paper_file = learner.consolidated_dir / f"2401_{i:03d}_consolidated.json"
            paper_file.write_text(json.dumps(paper_data, indent=2))

        analysis = await learner.generate_meta_analysis(min_papers=5)
        assert analysis is None

    @pytest.mark.asyncio
    async def test_generate_meta_analysis_sufficient_papers(self, tmp_path):
        """generate_meta_analysis deve gerar análise com papers suficientes."""
        learner = MetaLearner()
        learner.consolidated_dir = tmp_path / "papers"
        learner.consolidated_dir.mkdir(parents=True, exist_ok=True)

        # Criar 10 papers
        for i in range(10):
            fitness = 0.8 if i < 5 else 0.4  # 5 altos, 5 baixos
            validated = int(3 * fitness)  # 2 para 0.8, 1 para 0.4
            paper_data = {
                "paper": {
                    "paper_id": f"2401.{i:03d}",
                    "title": f"Paper {i}",
                    "topics": ["ml", "dl"],
                },
                "summary": {
                    "total_hypotheses": 3,
                    "validated": validated,
                    "fitness_score": fitness,
                },
            }
            paper_file = learner.consolidated_dir / f"2401_{i:03d}_consolidated.json"
            paper_file.write_text(json.dumps(paper_data, indent=2))

        analysis = await learner.generate_meta_analysis(min_papers=5)

        assert analysis is not None
        assert analysis.total_papers == 10
        assert analysis.total_hypotheses == 30
        # 5 papers com 2 validadas + 5 papers com 1 validada = 15/30 = 0.5
        assert analysis.overall_fitness == pytest.approx(0.5, rel=0.01)
        assert len(analysis.high_fitness_papers) == 5
        assert len(analysis.low_fitness_papers) == 5

    @pytest.mark.asyncio
    async def test_curate_low_fitness_papers(self, tmp_path):
        """curate_low_fitness_papers deve marcar papers com baixo fitness."""
        learner = MetaLearner()
        learner.consolidated_dir = tmp_path / "papers"
        learner.consolidated_dir.mkdir(parents=True, exist_ok=True)

        # Criar papers com fitness variado
        for i in range(5):
            fitness = 0.3 if i < 2 else 0.8  # 2 baixos, 3 altos
            paper_data = {
                "paper": {
                    "paper_id": f"2401.{i:03d}",
                    "title": f"Paper {i}",
                    "topics": ["ml"],
                },
                "summary": {
                    "total_hypotheses": 3,
                    "validated": int(3 * fitness),
                    "fitness_score": fitness,
                },
            }
            paper_file = learner.consolidated_dir / f"2401_{i:03d}_consolidated.json"
            paper_file.write_text(json.dumps(paper_data, indent=2))

        low_quality = await learner.curate_low_fitness_papers(threshold=0.5)

        assert len(low_quality) == 2
        # Ordenar para asserção consistente
        assert sorted(low_quality) == ["2401.000", "2401.001"]

        # Verificar que JSON foi atualizado
        updated_file = learner.consolidated_dir / "2401_000_consolidated.json"
        updated_data = json.loads(updated_file.read_text())
        assert updated_data["paper"]["quality_flag"] == "low"

    @pytest.mark.asyncio
    async def test_generate_recommendations(self, tmp_path):
        """generate_recommendations deve sugerir papers de alto fitness."""
        learner = MetaLearner()
        learner.consolidated_dir = tmp_path / "papers"
        learner.consolidated_dir.mkdir(parents=True, exist_ok=True)

        # Criar papers de alto fitness
        for i in range(5):
            paper_data = {
                "paper": {
                    "paper_id": f"2401.{i:03d}",
                    "title": f"Paper {i}",
                    "topics": ["ml", "dl"],
                },
                "summary": {
                    "total_hypotheses": 3,
                    "validated": 3,
                    "fitness_score": 0.9,
                },
            }
            paper_file = learner.consolidated_dir / f"2401_{i:03d}_consolidated.json"
            paper_file.write_text(json.dumps(paper_data, indent=2))

        recommendations = await learner.generate_recommendations(limit=3)

        assert len(recommendations) == 3
        assert all(r.predicted_fitness > 0.8 for r in recommendations)
        assert all("ml" in r.topics or "dl" in r.topics for r in recommendations)

    @pytest.mark.asyncio
    async def test_trigger_replication(self, tmp_path):
        """trigger_replication deve disparar replicação para papers mistos."""
        learner = MetaLearner()
        learner.consolidated_dir = tmp_path / "papers"
        learner.consolidated_dir.mkdir(parents=True, exist_ok=True)

        # Criar paper com fitness misto (0.5 - claramente dentro da faixa 0.33-0.67)
        paper_data = {
            "paper": {
                "paper_id": "2401.500",
                "title": "Mixed Results",
                "topics": ["ml"],
            },
            "summary": {"total_hypotheses": 3, "validated": 1, "fitness_score": 0.5},
        }
        paper_file = learner.consolidated_dir / "2401_500_consolidated.json"
        paper_file.write_text(json.dumps(paper_data, indent=2))

        triggered = await learner.trigger_replication("2401.500")

        assert triggered is True

        # Verificar que JSON foi atualizado
        updated_data = json.loads(paper_file.read_text())
        assert "replication" in updated_data
        assert updated_data["replication"]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_generate_cross_citations(self, tmp_path):
        """generate_cross_citations deve criar citações entre papers relacionados."""
        learner = MetaLearner()
        learner.consolidated_dir = tmp_path / "papers"
        learner.consolidated_dir.mkdir(parents=True, exist_ok=True)

        # Criar papers com tópicos sobrepostos
        papers_data = [
            {"paper_id": "2401.001", "topics": ["ml", "dl"]},
            {"paper_id": "2401.002", "topics": ["ml", "nlp"]},
            {"paper_id": "2401.003", "topics": ["dl", "cv"]},
        ]

        for pdata in papers_data:
            paper_data = {
                "paper": {
                    "paper_id": pdata["paper_id"],
                    "title": pdata["paper_id"],
                    "topics": pdata["topics"],
                },
                "summary": {
                    "total_hypotheses": 3,
                    "validated": 2,
                    "fitness_score": 0.67,
                },
            }
            paper_file = (
                learner.consolidated_dir
                / f"{pdata['paper_id'].replace(':', '_')}_consolidated.json"
            )
            paper_file.write_text(json.dumps(paper_data, indent=2))

        citations = await learner.generate_cross_citations()

        assert len(citations) == 3
        # 2401.001 e 2401.002 compartilham "ml"
        assert "2401.002" in citations.get("2401.001", [])
        # 2401.001 e 2401.003 compartilham "dl"
        assert "2401.003" in citations.get("2401.001", [])

    @pytest.mark.asyncio
    async def test_get_summary(self, tmp_path):
        """get_summary deve retornar resumo do meta-aprendizado."""
        learner = MetaLearner()
        learner.consolidated_dir = tmp_path / "papers"
        learner.consolidated_dir.mkdir(parents=True, exist_ok=True)

        # Sem papers
        summary = await learner.get_summary()
        assert summary["status"] == "no_data"

        # Com papers
        for i in range(5):
            fitness = 0.9 if i < 3 else 0.3  # 3 altos, 2 baixos
            paper_data = {
                "paper": {
                    "paper_id": f"2401.{i:03d}",
                    "title": f"Paper {i}",
                    "topics": ["ml"],
                },
                "summary": {
                    "total_hypotheses": 3,
                    "validated": int(3 * fitness),
                    "fitness_score": fitness,
                },
            }
            paper_file = learner.consolidated_dir / f"2401_{i:03d}_consolidated.json"
            paper_file.write_text(json.dumps(paper_data, indent=2))

        summary = await learner.get_summary()

        assert summary["status"] == "active"
        assert summary["total_papers"] == 5
        assert summary["high_fitness"] == 3
        assert summary["low_fitness"] == 2
        assert summary["quality_rate"] == pytest.approx(0.6, rel=0.01)


class TestRunMetaLearning:
    """Testes da função run_meta_learning."""

    @pytest.mark.asyncio
    async def test_run_meta_learning_empty(self, tmp_path):
        """run_meta_learning deve retornar status vazio sem papers."""
        with patch(
            "iaglobal.agents.ingestion.meta_learner.MetaLearner"
        ) as mock_learner:
            mock_instance = mock_learner.return_value
            mock_instance.load_consolidated_papers = AsyncMock(return_value=[])
            mock_instance.get_summary = AsyncMock(return_value={"status": "no_data"})
            mock_instance.generate_meta_analysis = AsyncMock(return_value=None)
            mock_instance.curate_low_fitness_papers = AsyncMock(return_value=[])
            mock_instance.generate_recommendations = AsyncMock(return_value=[])
            mock_instance.generate_cross_citations = AsyncMock(return_value={})

            results = await run_meta_learning(min_papers=5)

            assert results["summary"]["status"] == "no_data"
            assert results["meta_analysis"] is None
            assert results["low_quality_papers"] == []
            assert results["recommendations"] == []
            assert results["citations"] == {}

    @pytest.mark.asyncio
    async def test_run_meta_learning_full(self, tmp_path):
        """run_meta_learning deve executar todas as etapas."""
        from iaglobal.agents.ingestion.meta_learner import (
            MetaAnalysis,
            PaperRecommendation,
        )

        with patch(
            "iaglobal.agents.ingestion.meta_learner.MetaLearner"
        ) as mock_learner:
            mock_instance = mock_learner.return_value
            mock_instance.load_consolidated_papers = AsyncMock(
                return_value=[
                    {
                        "paper": {"paper_id": "2401.001", "topics": ["ml"]},
                        "summary": {"fitness_score": 0.9},
                    },
                ]
            )
            mock_instance.generate_meta_analysis = AsyncMock(
                return_value=MetaAnalysis(
                    total_papers=10,
                    total_hypotheses=30,
                    validated_hypotheses=25,
                    overall_fitness=0.83,
                    top_topics=[("ml", 5)],
                    low_fitness_papers=[],
                    high_fitness_papers=["2401.001"],
                    replication_candidates=[],
                )
            )
            mock_instance.curate_low_fitness_papers = AsyncMock(return_value=[])
            mock_instance.generate_recommendations = AsyncMock(
                return_value=[
                    PaperRecommendation(
                        "2401.001", "Test", ["ml"], 0.9, "High fitness", []
                    ),
                ]
            )
            mock_instance.generate_cross_citations = AsyncMock(
                return_value={"2401.001": []}
            )
            mock_instance.get_summary = AsyncMock(
                return_value={"status": "active", "total_papers": 10}
            )

            results = await run_meta_learning(min_papers=5)

            assert results["meta_analysis"] is not None
            assert len(results["recommendations"]) == 1
            assert results["summary"]["status"] == "active"
