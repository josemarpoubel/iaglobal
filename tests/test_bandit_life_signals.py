# tests/test_bandit_life_signals.py
"""
Valida a integração epigenética entre BanditPolicy e LifeSignalCollector.

Verifica que:
1. LifeSignalCollector captura sinais corretamente
2. BanditPolicy._life_signal_score() retorna valores esperados
3. BanditPolicy._calculate_scores() integra o life-signal sem dominar
"""

import asyncio
from pathlib import Path

import pytest

from iaglobal.utils.life_signal_collector import LifeSignalCollector
from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.graphs.credit import CreditAssignmentEngine


@pytest.fixture(autouse=True)
def _isolate_collector():
    """Isola o coletor para cada teste e limpa sinais antes/depois."""
    collector = LifeSignalCollector()
    collector.clear()
    yield collector
    collector.clear()


def test_life_signal_collector_records_signals():
    collector = LifeSignalCollector()
    collector.record("foo", ["ctx_a", "ctx_b"])
    collector.record("foo", ["ctx_a"])

    data = collector.get_all_signals()
    assert "foo" in data
    assert len(data["foo"]) == 2


def test_bandit_life_signal_score_neutral_without_signals():
    collector = LifeSignalCollector()
    bandit = BanditPolicy(credit=CreditAssignmentEngine())
    score = bandit._life_signal_score("ollama/qwen2.5:0.5b")
    assert score == 0.3


def test_bandit_life_signal_score_rises_with_signals():
    collector = LifeSignalCollector()
    bandit = BanditPolicy(credit=CreditAssignmentEngine())

    assert bandit._life_signal_score("ollama/qwen2.5:0.5b") == 0.3

    for _ in range(5):
        collector.record("_run_evolution_committee", ["memory"])

    score = bandit._life_signal_score("ollama/qwen2.5:0.5b")
    assert score >= 0.5
    assert score <= 1.0


def test_bandit_life_signal_score_saturates_at_one():
    collector = LifeSignalCollector()
    bandit = BanditPolicy(credit=CreditAssignmentEngine())

    for _ in range(20):
        collector.record("_run_evolution_committee", ["memory"])

    score = bandit._life_signal_score("ollama/qwen2.5:0.5b")
    assert score == 1.0


def test_calculate_scores_includes_life_signal():
    collector = LifeSignalCollector()
    bandit = BanditPolicy(credit=CreditAssignmentEngine())

    for _ in range(8):
        collector.record("_run_evolution_committee", ["memory"])

    models = ["ollama/qwen2.5:0.5b", "groq/llama-3.3-70b-versatile"]
    scored = bandit._calculate_scores("test_node", "general", models)

    assert len(scored) == 2
    scores = [s for s, _ in scored]
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_calculate_scores_is_stable_without_signals():
    collector = LifeSignalCollector()
    bandit = BanditPolicy(credit=CreditAssignmentEngine())

    models = ["ollama/qwen2.5:0.5b", "groq/llama-3.3-70b-versatile"]
    scored = bandit._calculate_scores("test_node", "general", models)

    scores = [s for s, _ in scored]
    assert len(scored) == 2
    # Sem sinais, o life_signal_score é 0.5 neutro para ambos.
    # A estabilidade aqui significa que o cálculo não levanta exceções
    # e produz floats válidos para ambos os modelos.
    assert all(isinstance(s, float) for s in scores)
