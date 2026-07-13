# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do ConfidenceTracker — Fase 1 do RAG Autônomo.

Cobertura:
  - should_search retorna True/False baseado em confiança
  - record_confidence atualiza cache
  - record_search_outcome ajusta confiança
  - adjust_threshold muda threshold dinamicamente
  - Persistência em JSON
"""

import pytest
from unittest.mock import patch

from iaglobal.search.confidence_tracker import (
    ConfidenceTracker,
    AgentConfidence,
    get_confidence_tracker,
    should_search,
    record_confidence,
    record_search_outcome,
    get_stats,
)


class TestAgentConfidence:
    """Testes da dataclass AgentConfidence."""

    def test_confidence_creation(self):
        """AgentConfidence deve criar com campos obrigatórios."""
        conf = AgentConfidence(
            agent_id="coder",
            task_hash="abc123",
            confidence=0.75,
            last_updated=1234567890.0,
        )
        assert conf.agent_id == "coder"
        assert conf.confidence == 0.75
        assert conf.threshold == 0.8  # default

    def test_confidence_to_dict(self):
        """to_dict deve serializar corretamente."""
        conf = AgentConfidence(
            agent_id="debugger",
            task_hash="def456",
            confidence=0.90,
            last_updated=1234567890.0,
            search_helped=True,
        )
        data = conf.to_dict()
        assert data["agent_id"] == "debugger"
        assert data["confidence"] == 0.90
        assert data["search_helped"] is True


class TestConfidenceTracker:
    """Testes do ConfidenceTracker."""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Cria tracker com arquivo de persistência em tmp."""
        with patch("iaglobal.search.confidence_tracker.JSON_DIR", tmp_path):
            t = ConfidenceTracker(default_threshold=0.8)
            yield t
            t.clear()

    def test_should_search_first_time(self, tracker):
        """should_search deve retornar True na primeira vez (sem histórico)."""
        result = tracker.should_search("coder", "task_001")
        assert result is True

    def test_should_search_low_confidence(self, tracker):
        """should_search deve retornar True se confiança < threshold."""
        tracker.record_confidence("coder", "task_001", confidence=0.5)
        result = tracker.should_search("coder", "task_001")
        assert result is True  # 0.5 < 0.8

    def test_should_search_high_confidence(self, tracker):
        """should_search deve retornar False se confiança > threshold."""
        tracker.record_confidence("coder", "task_001", confidence=0.9)
        result = tracker.should_search("coder", "task_001")
        assert result is False  # 0.9 > 0.8

    def test_should_search_custom_threshold(self, tracker):
        """should_search deve respeitar threshold customizado."""
        tracker.record_confidence("coder", "task_001", confidence=0.7)

        # Threshold padrão (0.8): deve buscar
        assert tracker.should_search("coder", "task_001") is True

        # Threshold customizado (0.6): não deve buscar
        assert tracker.should_search("coder", "task_001", threshold=0.6) is False

    def test_record_confidence_updates_cache(self, tracker):
        """record_confidence deve atualizar cache."""
        tracker.record_confidence(
            "coder", "task_001", confidence=0.85, search_helped=True
        )

        conf = tracker.get_confidence("coder", "task_001")
        assert conf == 0.85

    def test_record_search_outcome_helped(self, tracker):
        """record_search_outcome deve aumentar confiança se ajudou."""
        tracker.record_confidence("coder", "task_001", confidence=0.7)
        tracker.record_search_outcome("coder", "task_001", helped=True)

        conf = tracker.get_confidence("coder", "task_001")
        assert conf > 0.7  # Aumentou

    def test_record_search_outcome_hurt(self, tracker):
        """record_search_outcome deve diminuir confiança se atrapalhou."""
        tracker.record_confidence("coder", "task_001", confidence=0.7)
        tracker.record_search_outcome("coder", "task_001", helped=False)

        conf = tracker.get_confidence("coder", "task_001")
        assert conf < 0.7  # Diminuiu

    def test_adjust_threshold(self, tracker):
        """adjust_threshold deve ajustar threshold do agente."""
        tracker.record_confidence("coder", "task_001", confidence=0.7)
        tracker.record_confidence("coder", "task_002", confidence=0.6)

        # Ajustar threshold para +0.1
        tracker.adjust_threshold("coder", delta=0.1)

        # Verificar que threshold foi ajustado (via get_stats ou acesso interno)
        stats = tracker.get_stats("coder")
        assert stats["avg_threshold"] > 0.8

    def test_get_stats(self, tracker):
        """get_stats deve retornar estatísticas corretas."""
        tracker.record_confidence(
            "coder", "task_001", confidence=0.8, search_helped=True
        )
        tracker.record_confidence(
            "coder", "task_002", confidence=0.6, search_helped=False
        )
        tracker.record_confidence(
            "debugger", "task_003", confidence=0.9, search_helped=True
        )

        # Stats globais
        stats = tracker.get_stats()
        assert stats["total_tasks"] == 3
        assert stats["avg_confidence"] == pytest.approx(0.767, rel=0.01)

        # Stats por agente
        stats_coder = tracker.get_stats("coder")
        assert stats_coder["total_tasks"] == 2
        assert stats_coder["search_helped"] == 1
        assert stats_coder["search_hurt"] == 1

    def test_persistence_save_and_load(self, tmp_path):
        """Persistência deve salvar e carregar corretamente."""
        with patch("iaglobal.search.confidence_tracker.JSON_DIR", tmp_path):
            # Salvar
            tracker1 = ConfidenceTracker()
            tracker1.record_confidence(
                "coder", "task_001", confidence=0.85, search_helped=True
            )
            tracker1._save()

            # Carregar
            tracker2 = ConfidenceTracker()
            conf = tracker2.get_confidence("coder", "task_001")

            assert conf == 0.85

    def test_clear_agent(self, tracker):
        """clear deve limpar cache de um agente específico."""
        tracker.record_confidence("coder", "task_001", confidence=0.8)
        tracker.record_confidence("debugger", "task_002", confidence=0.9)

        tracker.clear(agent_id="coder")

        assert tracker.get_confidence("coder", "task_001") is None
        assert tracker.get_confidence("debugger", "task_002") == 0.9

    def test_clear_all(self, tracker):
        """clear sem agent_id deve limpar todo o cache."""
        tracker.record_confidence("coder", "task_001", confidence=0.8)
        tracker.record_confidence("debugger", "task_002", confidence=0.9)

        tracker.clear()

        assert tracker.get_confidence("coder", "task_001") is None
        assert tracker.get_confidence("debugger", "task_002") is None


class TestSingletonAndWrappers:
    """Testes do singleton e funções wrapper."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self, monkeypatch):
        """Reseta o singleton global antes de cada teste para evitar vazamento de estado."""
        import iaglobal.search.confidence_tracker as ct

        monkeypatch.setattr(ct, "_confidence_tracker", None)

    def test_get_confidence_tracker_singleton(self):
        """get_confidence_tracker deve retornar singleton."""
        tracker1 = get_confidence_tracker()
        tracker2 = get_confidence_tracker()
        assert tracker1 is tracker2

    def test_should_search_wrapper(self):
        """should_search wrapper deve funcionar."""
        # Primeiro uso: deve buscar
        result = should_search("coder", "task_new")
        assert result is True

    def test_record_confidence_wrapper(self, tmp_path):
        """record_confidence wrapper deve funcionar."""
        with patch("iaglobal.search.confidence_tracker.JSON_DIR", tmp_path):
            record_confidence("coder", "task_001", confidence=0.75, search_helped=True)
            conf = get_confidence_tracker().get_confidence("coder", "task_001")
            assert conf == 0.75

    def test_record_search_outcome_wrapper(self, tmp_path):
        """record_search_outcome wrapper deve funcionar."""
        with patch("iaglobal.search.confidence_tracker.JSON_DIR", tmp_path):
            record_confidence("coder", "task_001", confidence=0.7)
            record_search_outcome("coder", "task_001", helped=True)

            conf = get_confidence_tracker().get_confidence("coder", "task_001")
            assert conf > 0.7

    def test_get_stats_wrapper(self, tmp_path):
        """get_stats wrapper deve funcionar."""
        with patch("iaglobal.search.confidence_tracker.JSON_DIR", tmp_path):
            record_confidence("coder", "task_001", confidence=0.8)
            stats = get_stats("coder")

            assert stats["total_tasks"] == 1
            assert stats["avg_confidence"] == 0.8


class TestIntegration:
    """Testes de integração com SearchMiddleware."""

    def test_confidence_tracker_prevents_search(self, tmp_path):
        """ConfidenceTracker deve prevenir busca se confiança alta."""

        with patch("iaglobal.search.confidence_tracker.JSON_DIR", tmp_path):
            # Registrar alta confiança
            record_confidence("coder", "task_test", confidence=0.95)

            # Mock do prompt
            prompt = "crie uma função Python que soma dois números"

            # SearchMiddleware deve skipar busca
            # (teste simplificado — na prática, SearchMiddleware.enrich() chama should_search)
            task_hash = "task_test"
            assert should_search("coder", task_hash, threshold=0.8) is False
