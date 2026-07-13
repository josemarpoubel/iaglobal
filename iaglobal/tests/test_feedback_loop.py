# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do FeedbackLoop — Fase 6 do RAG Autônomo.

Cobertura:
  - record_outcome() registra feedback
  - update_confidence() ajusta confiança
  - get_feedback_history() retorna histórico
  - compute_search_effectiveness() calcula eficácia
  - Stats são atualizados
"""

import pytest
import asyncio
import json
import time
from pathlib import Path

from iaglobal.search.feedback_loop import (
    FeedbackLoop,
    FeedbackRecord,
    FeedbackOutcome,
    record_outcome,
    update_confidence,
    get_feedback_stats,
    compute_search_effectiveness,
)


class TestFeedbackOutcome:
    """Testes do enum FeedbackOutcome."""

    def test_outcome_values(self):
        """FeedbackOutcome deve ter valores corretos."""
        assert FeedbackOutcome.HELPED.value == "helped"
        assert FeedbackOutcome.HARMED.value == "harmed"
        assert FeedbackOutcome.NEUTRAL.value == "neutral"
        assert FeedbackOutcome.IGNORED.value == "ignored"


class TestFeedbackRecord:
    """Testes da dataclass FeedbackRecord."""

    def test_feedback_record_creation(self):
        """FeedbackRecord deve criar com campos obrigatórios."""
        record = FeedbackRecord(
            query="test query",
            query_hash="abc123",
            agent_id="coder",
            task_hash="task456",
            outcome="helped",
            timestamp=time.time(),
        )
        assert record.query == "test query"
        assert record.outcome == "helped"
        assert record.search_results_count == 0

    def test_feedback_record_to_dict(self):
        """to_dict deve serializar corretamente."""
        record = FeedbackRecord(
            query="test",
            query_hash="hash",
            agent_id="tester",
            task_hash="task",
            outcome="harmed",
            timestamp=1234567890.0,
            search_results_count=5,
            confidence_before=0.5,
            confidence_after=0.7,
        )
        data = record.to_dict()
        assert data["query"] == "test"
        assert data["outcome"] == "harmed"
        assert data["confidence_before"] == 0.5

    def test_feedback_record_from_dict(self):
        """from_dict deve desserializar corretamente."""
        data = {
            "query": "test",
            "query_hash": "hash",
            "agent_id": "coder",
            "task_hash": "task",
            "outcome": "neutral",
            "timestamp": 1234567890.0,
            "search_results_count": 3,
            "confidence_before": None,
            "confidence_after": None,
            "latency_ms": None,
            "tokens_used": None,
        }
        record = FeedbackRecord.from_dict(data)
        assert record.query == "test"
        assert record.outcome == "neutral"


class TestFeedbackLoop:
    """Testes do FeedbackLoop."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self, tmp_path):
        """Reseta singleton, cache e arquivo de índice entre testes."""
        from iaglobal.search import feedback_loop

        # Limpar singleton e cache
        feedback_loop._feedback = None
        feedback_loop.FeedbackLoop._cache = []
        feedback_loop.FeedbackLoop._index = {}
        feedback_loop.FeedbackLoop._stats = {
            "total": 0,
            "helped": 0,
            "harmed": 0,
            "neutral": 0,
            "ignored": 0,
            "effectiveness_score": 0.0,
        }

        # Remover arquivo de índice default se existir
        default_index = Path("obsidian/04_Synapses/feedback_loop/feedback_index.json")
        if default_index.exists():
            default_index.unlink()

        yield

        # Limpar após teste
        feedback_loop._feedback = None
        feedback_loop.FeedbackLoop._cache = []
        feedback_loop.FeedbackLoop._index = {}
        feedback_loop.FeedbackLoop._stats = {
            "total": 0,
            "helped": 0,
            "harmed": 0,
            "neutral": 0,
            "ignored": 0,
            "effectiveness_score": 0.0,
        }

        # Remover arquivo de índice default novamente
        if default_index.exists():
            default_index.unlink()

    @pytest.fixture
    def temp_obsidian(self, tmp_path):
        """Cria diretório Obsidian temporário."""
        obsidian_path = tmp_path / "obsidian" / "04_Synapses" / "feedback_loop"
        obsidian_path.mkdir(parents=True, exist_ok=True)
        return obsidian_path

    @pytest.fixture
    def feedback(self, temp_obsidian):
        """Cria FeedbackLoop com path temporário."""
        return FeedbackLoop(obsidian_path=temp_obsidian)

    # ── Testes de record_outcome ────────────────────────────

    @pytest.mark.asyncio
    async def test_record_outcome_helped(self, feedback):
        """record_outcome deve registrar feedback helped."""
        result = await feedback.record_outcome(
            query="test query",
            agent_id="coder",
            task_hash="task123",
            outcome=FeedbackOutcome.HELPED,
            search_results_count=5,
            confidence_before=0.5,
            confidence_after=0.7,
        )

        assert result is True
        assert len(feedback._cache) == 1

        record = feedback._cache[0]
        assert record.query == "test query"
        assert record.outcome == "helped"
        assert record.agent_id == "coder"

    @pytest.mark.asyncio
    async def test_record_outcome_harmed(self, feedback):
        """record_outcome deve registrar feedback harmed."""
        await feedback.record_outcome(
            query="bad query",
            agent_id="debugger",
            task_hash="task456",
            outcome=FeedbackOutcome.HARMED,
        )

        record = feedback._cache[0]
        assert record.outcome == "harmed"

    @pytest.mark.asyncio
    async def test_record_outcome_updates_stats(self, feedback):
        """record_outcome deve atualizar stats."""
        await feedback.record_outcome("q1", "coder", "t1", FeedbackOutcome.HELPED)
        await feedback.record_outcome("q2", "coder", "t2", FeedbackOutcome.HELPED)
        await feedback.record_outcome("q3", "coder", "t3", FeedbackOutcome.HARMED)

        stats = feedback.get_stats()

        assert stats["total"] == 3
        assert stats["helped"] == 2
        assert stats["harmed"] == 1
        assert abs(stats["effectiveness_score"] - (2 / 3)) < 0.01

    @pytest.mark.asyncio
    async def test_record_outcome_persists_to_disk(self, feedback, temp_obsidian):
        """record_outcome deve persistir no disco."""
        await feedback.record_outcome(
            query="persistent",
            agent_id="coder",
            task_hash="task",
            outcome=FeedbackOutcome.HELPED,
        )

        assert feedback.INDEX_FILE.exists()

        with open(feedback.INDEX_FILE, "r") as f:
            data = json.load(f)

        assert "records" in data
        assert len(data["records"]) == 1
        assert data["records"][0]["query"] == "persistent"

    @pytest.mark.asyncio
    async def test_record_outcome_creates_md_file(self, feedback, temp_obsidian):
        """record_outcome deve criar arquivo .md individual."""
        await feedback.record_outcome(
            query="markdown",
            agent_id="tester",
            task_hash="task",
            outcome=FeedbackOutcome.NEUTRAL,
        )

        query_hash = feedback._query_hash("markdown")
        md_file = temp_obsidian / f"{query_hash}.md"

        assert md_file.exists()

        content = md_file.read_text()
        assert "# Feedback: markdown" in content
        assert "neutral" in content

    # ── Testes de update_confidence ─────────────────────────

    @pytest.mark.asyncio
    async def test_update_confidence_helped(self, feedback):
        """update_confidence deve aumentar confiança se helped."""
        # Primeiro registrar um feedback
        await feedback.record_outcome(
            query="test",
            agent_id="coder",
            task_hash="task123",
            outcome=FeedbackOutcome.HELPED,
            confidence_before=0.5,
            confidence_after=0.6,
        )

        # Atualizar confiança
        new_confidence = await feedback.update_confidence(
            agent_id="coder",
            task_hash="task123",
            helped=True,
            delta=0.1,
        )

        assert new_confidence is not None
        assert new_confidence >= 0.6

    @pytest.mark.asyncio
    async def test_update_confidence_harmed(self, feedback):
        """update_confidence deve diminuir confiança se harmed."""
        await feedback.record_outcome(
            query="test",
            agent_id="coder",
            task_hash="task123",
            outcome=FeedbackOutcome.HARMED,
            confidence_before=0.7,
            confidence_after=0.6,
        )

        new_confidence = await feedback.update_confidence(
            agent_id="coder",
            task_hash="task123",
            helped=False,
            delta=0.1,
        )

        assert new_confidence is not None
        assert new_confidence <= 0.6

    # ── Testes de get_feedback_history ──────────────────────

    @pytest.mark.asyncio
    async def test_get_feedback_history_basic(self, feedback):
        """get_feedback_history deve retornar histórico."""
        # Registrar 3 feedbacks
        for i in range(3):
            await feedback.record_outcome(
                query=f"query {i}",
                agent_id="coder",
                task_hash=f"task{i}",
                outcome=FeedbackOutcome.HELPED,
            )

        history = await feedback.get_feedback_history()

        assert len(history) == 3
        assert all(isinstance(r, FeedbackRecord) for r in history)

    @pytest.mark.asyncio
    async def test_get_feedback_history_limit(self, feedback):
        """get_feedback_history deve respeitar limit."""
        # Registrar 10 feedbacks
        for i in range(10):
            await feedback.record_outcome(
                query=f"query {i}",
                agent_id="coder",
                task_hash=f"task{i}",
                outcome=FeedbackOutcome.HELPED,
            )

        history = await feedback.get_feedback_history(limit=5)

        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_get_feedback_history_sorted(self, feedback):
        """get_feedback_history deve ordenar por timestamp (recente primeiro)."""
        # Registrar com delay
        for i in range(3):
            await feedback.record_outcome(
                query=f"query {i}",
                agent_id="coder",
                task_hash=f"task{i}",
                outcome=FeedbackOutcome.HELPED,
            )
            await asyncio.sleep(0.01)

        history = await feedback.get_feedback_history()

        # Verificar ordem
        assert history[0].timestamp >= history[1].timestamp >= history[2].timestamp

    # ── Testes de compute_search_effectiveness ──────────────

    @pytest.mark.asyncio
    async def test_compute_search_effectiveness_all_helped(self, feedback):
        """compute_search_effectiveness deve retornar 1.0 se todos helped."""
        for i in range(5):
            await feedback.record_outcome(
                query=f"query {i}",
                agent_id="coder",
                task_hash=f"task{i}",
                outcome=FeedbackOutcome.HELPED,
            )

        effectiveness = feedback.compute_search_effectiveness()

        assert effectiveness == 1.0

    @pytest.mark.asyncio
    async def test_compute_search_effectiveness_mixed(self, feedback):
        """compute_search_effectiveness deve calcular proporção."""
        # 3 helped, 1 harmed
        for i in range(3):
            await feedback.record_outcome(
                f"q{i}", "coder", f"t{i}", FeedbackOutcome.HELPED
            )
        await feedback.record_outcome("q4", "coder", "t4", FeedbackOutcome.HARMED)

        effectiveness = feedback.compute_search_effectiveness()

        assert abs(effectiveness - 0.75) < 0.01

    @pytest.mark.asyncio
    async def test_compute_search_effectiveness_by_agent(self, feedback):
        """compute_search_effectiveness deve filtrar por agente."""
        # Coder: 2 helped
        await feedback.record_outcome("q1", "coder", "t1", FeedbackOutcome.HELPED)
        await feedback.record_outcome("q2", "coder", "t2", FeedbackOutcome.HELPED)

        # Debugger: 1 harmed
        await feedback.record_outcome("q3", "debugger", "t3", FeedbackOutcome.HARMED)

        # Eficácia do coder
        coder_effectiveness = feedback.compute_search_effectiveness(agent_id="coder")
        assert coder_effectiveness == 1.0

        # Eficácia do debugger
        debugger_effectiveness = feedback.compute_search_effectiveness(
            agent_id="debugger"
        )
        assert debugger_effectiveness == 0.0

    # ── Testes de stats ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_stats_initial(self, feedback):
        """Stats iniciais devem ter valores padrão."""
        stats = feedback.get_stats()

        assert stats["total"] == 0
        assert stats["helped"] == 0
        assert stats["effectiveness_score"] == 0.0

    @pytest.mark.asyncio
    async def test_get_stats_updated(self, feedback):
        """Stats devem atualizar após registros."""
        await feedback.record_outcome("q1", "coder", "t1", FeedbackOutcome.HELPED)
        await feedback.record_outcome("q2", "coder", "t2", FeedbackOutcome.HARMED)

        stats = feedback.get_stats()

        assert stats["total"] == 2
        assert stats["helped"] == 1
        assert stats["harmed"] == 1
        assert abs(stats["effectiveness_score"] - 0.5) < 0.01

    def test_clear_cache(self, feedback):
        """clear_cache deve limpar cache em memória."""
        import asyncio

        asyncio.run(
            feedback.record_outcome("q1", "coder", "t1", FeedbackOutcome.HELPED)
        )

        assert len(feedback._cache) == 1

        feedback.clear_cache()

        assert len(feedback._cache) == 0


class TestFeedbackLoopIntegration:
    """Testes de integração."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self, tmp_path):
        """Reseta singleton, cache e arquivo de índice entre testes."""
        from iaglobal.search import feedback_loop

        feedback_loop._feedback = None
        feedback_loop.FeedbackLoop._cache = []
        feedback_loop.FeedbackLoop._index = {}
        feedback_loop.FeedbackLoop._stats = {
            "total": 0,
            "helped": 0,
            "harmed": 0,
            "neutral": 0,
            "ignored": 0,
            "effectiveness_score": 0.0,
        }

        # Remover arquivo default
        default_index = Path("obsidian/04_Synapses/feedback_loop/feedback_index.json")
        if default_index.exists():
            default_index.unlink()

        yield

        feedback_loop._feedback = None
        feedback_loop.FeedbackLoop._cache = []
        feedback_loop.FeedbackLoop._index = {}
        feedback_loop.FeedbackLoop._stats = {
            "total": 0,
            "helped": 0,
            "harmed": 0,
            "neutral": 0,
            "ignored": 0,
            "effectiveness_score": 0.0,
        }

        if default_index.exists():
            default_index.unlink()

    @pytest.fixture
    def temp_obsidian(self, tmp_path):
        obsidian_path = tmp_path / "obsidian" / "04_Synapses" / "feedback_loop"
        obsidian_path.mkdir(parents=True, exist_ok=True)
        return obsidian_path

    @pytest.mark.asyncio
    async def test_record_outcome_wrapper(self, temp_obsidian):
        """record_outcome wrapper deve funcionar."""
        result = await record_outcome(
            query="wrapper query",
            agent_id="tester",
            task_hash="task123",
            outcome=FeedbackOutcome.HELPED,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_update_confidence_wrapper(self, temp_obsidian):
        """update_confidence wrapper deve funcionar."""
        # Registrar primeiro
        await record_outcome(
            query="test",
            agent_id="coder",
            task_hash="task123",
            outcome=FeedbackOutcome.HELPED,
        )

        new_confidence = await update_confidence(
            agent_id="coder",
            task_hash="task123",
            helped=True,
        )

        assert new_confidence is not None

    @pytest.mark.asyncio
    async def test_get_feedback_stats_wrapper(self):
        """get_feedback_stats wrapper deve funcionar."""
        stats = get_feedback_stats()

        assert "total" in stats
        assert "helped" in stats

    @pytest.mark.asyncio
    async def test_compute_search_effectiveness_wrapper(self, temp_obsidian):
        """compute_search_effectiveness wrapper deve funcionar."""
        await record_outcome("q1", "coder", "t1", FeedbackOutcome.HELPED)

        effectiveness = compute_search_effectiveness()

        assert 0.0 <= effectiveness <= 1.0


class TestFeedbackLoopE2E:
    """Testes end-to-end."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self, tmp_path):
        """Reseta singleton, cache e arquivo de índice entre testes."""
        from iaglobal.search import feedback_loop

        feedback_loop._feedback = None
        feedback_loop.FeedbackLoop._cache = []
        feedback_loop.FeedbackLoop._index = {}
        feedback_loop.FeedbackLoop._stats = {
            "total": 0,
            "helped": 0,
            "harmed": 0,
            "neutral": 0,
            "ignored": 0,
            "effectiveness_score": 0.0,
        }

        # Remover arquivo default
        default_index = Path("obsidian/04_Synapses/feedback_loop/feedback_index.json")
        if default_index.exists():
            default_index.unlink()

        yield

        feedback_loop._feedback = None
        feedback_loop.FeedbackLoop._cache = []
        feedback_loop.FeedbackLoop._index = {}
        feedback_loop.FeedbackLoop._stats = {
            "total": 0,
            "helped": 0,
            "harmed": 0,
            "neutral": 0,
            "ignored": 0,
            "effectiveness_score": 0.0,
        }

        if default_index.exists():
            default_index.unlink()

    @pytest.fixture
    def temp_obsidian(self, tmp_path):
        obsidian_path = tmp_path / "obsidian" / "04_Synapses" / "feedback_loop"
        obsidian_path.mkdir(parents=True, exist_ok=True)
        return obsidian_path

    @pytest.mark.asyncio
    async def test_full_feedback_lifecycle(self, temp_obsidian):
        """Ciclo completo: record → update → history → stats."""
        feedback = FeedbackLoop(obsidian_path=temp_obsidian)

        # 1. Registrar feedbacks
        await feedback.record_outcome(
            query="good search",
            agent_id="coder",
            task_hash="task1",
            outcome=FeedbackOutcome.HELPED,
            search_results_count=5,
            confidence_before=0.5,
            confidence_after=0.7,
            latency_ms=150.0,
        )

        await feedback.record_outcome(
            query="bad search",
            agent_id="coder",
            task_hash="task2",
            outcome=FeedbackOutcome.HARMED,
            search_results_count=10,
            confidence_before=0.6,
            confidence_after=0.4,
        )

        # 2. Atualizar confiança
        new_confidence = await feedback.update_confidence(
            agent_id="coder",
            task_hash="task1",
            helped=True,
            delta=0.05,
        )
        assert new_confidence is not None

        # 3. Verificar histórico
        history = await feedback.get_feedback_history()
        assert len(history) == 2
        assert history[0].outcome == "harmed"  # Mais recente
        assert history[1].outcome == "helped"

        # 4. Verificar stats
        stats = feedback.get_stats()
        assert stats["total"] == 2
        assert stats["helped"] == 1
        assert stats["harmed"] == 1
        assert abs(stats["effectiveness_score"] - 0.5) < 0.01

        # 5. Verificar eficácia
        effectiveness = feedback.compute_search_effectiveness()
        assert abs(effectiveness - 0.5) < 0.01

    @pytest.mark.asyncio
    async def test_multiple_agents_feedback(self, temp_obsidian):
        """Múltiplos agentes com feedbacks diferentes."""
        feedback = FeedbackLoop(obsidian_path=temp_obsidian)

        # Coder: sempre helped
        for i in range(5):
            await feedback.record_outcome(
                f"coder query {i}",
                "coder",
                f"task_c{i}",
                FeedbackOutcome.HELPED,
            )

        # Debugger: sempre harmed
        for i in range(3):
            await feedback.record_outcome(
                f"debugger query {i}",
                "debugger",
                f"task_d{i}",
                FeedbackOutcome.HARMED,
            )

        # Tester: misto
        await feedback.record_outcome(
            "tester q1", "tester", "task_t1", FeedbackOutcome.HELPED
        )
        await feedback.record_outcome(
            "tester q2", "tester", "task_t2", FeedbackOutcome.NEUTRAL
        )

        # Verificar eficácia por agente
        coder_eff = feedback.compute_search_effectiveness(agent_id="coder")
        assert coder_eff == 1.0

        debugger_eff = feedback.compute_search_effectiveness(agent_id="debugger")
        assert debugger_eff == 0.0

        tester_eff = feedback.compute_search_effectiveness(agent_id="tester")
        assert abs(tester_eff - 0.5) < 0.01

        # Eficácia geral
        total_eff = feedback.compute_search_effectiveness()
        # 6 helped de 10 total = 0.6
        assert abs(total_eff - 0.6) < 0.01
