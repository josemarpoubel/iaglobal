# 🧬 Testes da Barreira Imunológica do Telemetry/Cache (Metabolic Immune Barrier)
import pytest

from iaglobal.immunity.metabolic_immune_barrier import barrier


@pytest.fixture(autouse=True)
def _reset_barrier():
    barrier.reset()
    yield
    barrier.reset()


def test_record_increments_counts():
    barrier.record("cache_poison", detail="x", agent="a")
    assert barrier.counts()["cache_poison"] == 1
    assert barrier.is_degraded() is True


def test_non_degradation_kind_does_not_flag():
    barrier.record("cache_valid_hit")
    assert barrier.counts()["cache_valid_hit"] == 1
    assert barrier.is_degraded() is False


def test_unknown_kind_normalized_to_synthetic_success():
    barrier.record("anything_weird")
    assert barrier.counts()["synthetic_success"] == 1
    assert barrier.is_degraded() is True


def test_recent_keeps_last_entries():
    for i in range(60):
        barrier.record("cache_valid_hit", detail=str(i))
    recent = barrier.recent(limit=5)
    assert len(recent) == 5


def test_reset_clears_state():
    barrier.record("cache_poison")
    barrier.reset()
    assert barrier.is_degraded() is False
    assert sum(barrier.counts().values()) == 0
