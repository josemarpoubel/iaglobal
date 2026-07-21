# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes do JointOptimizationLoop — ribossomo metabólico."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from iaglobal.metabolism.joint_optimization import (
    JointOptimizationLoop,
    joint_optimization_loop,
    ExecutionSnapshot,
)


@pytest.fixture
def jol():
    loop = JointOptimizationLoop()
    return loop


@pytest.mark.asyncio
async def test_ingest_basic(jol):
    await jol.ingest("coder", True, 1.5, 0.0, "ollama/qwen2.5:0.5b")
    assert len(jol._snapshots) == 1
    assert jol._snapshots[0].node == "coder"
    assert jol._snapshots[0].success is True
    assert jol._snapshots[0].latency == 1.5


@pytest.mark.asyncio
async def test_ingest_metrics_dict(jol):
    metrics = {
        "agente_utilizado": "tester",
        "success": True,
        "latency": 2.0,
        "cost": 0.001,
        "model": "groq/llama3",
    }
    await jol.ingest_metrics(metrics)
    assert len(jol._snapshots) == 1
    assert jol._snapshots[0].node == "tester"
    assert jol._snapshots[0].model == "groq/llama3"


@pytest.mark.asyncio
async def test_ingest_metrics_minimal(jol):
    await jol.ingest_metrics({"success": True, "latency": 1.0})
    assert len(jol._snapshots) == 1
    assert jol._snapshots[0].node == "unknown"
    assert jol._snapshots[0].cost == 0.0


@pytest.mark.asyncio
async def test_ingest_window_limit(jol):
    for i in range(1050):
        await jol.ingest(f"node{i}", True, 0.1, 0.0)
    assert len(jol._snapshots) == 1000


@pytest.mark.asyncio
async def test_get_node_ivm_no_data(jol):
    ivm = await jol.get_node_ivm("nonexistent")
    assert ivm == 0.5


@pytest.mark.asyncio
async def test_get_node_ivm_with_data(jol):
    for _ in range(10):
        await jol.ingest("coder", True, 1.0, 0.0)
    ivm = await jol.get_node_ivm("coder")
    assert 0.0 < ivm <= 1.0


@pytest.mark.asyncio
async def test_get_node_ivm_with_failures(jol):
    for _ in range(8):
        await jol.ingest("coder", True, 1.0, 0.0)
    for _ in range(2):
        await jol.ingest("coder", False, 5.0, 0.0)
    ivm = await jol.get_node_ivm("coder")
    assert ivm > 0.0
    assert ivm < 0.9


@pytest.mark.asyncio
async def test_get_global_ivm_empty(jol):
    ivm = await jol.get_global_ivm()
    assert ivm == 0.5


@pytest.mark.asyncio
async def test_get_global_ivm_with_data(jol):
    await jol.ingest("coder", True, 0.5)
    await jol.ingest("tester", True, 1.0)
    await jol.ingest("debugger", False, 3.0)
    ivm = await jol.get_global_ivm()
    assert 0.0 < ivm <= 1.0


@pytest.mark.asyncio
async def test_sync_bandit_weights_interval(jol):
    bandit = MagicMock()
    bandit.credit_engine = MagicMock()
    bandit.credit_engine.stats = {}
    bandit.weights = {}

    await jol.sync_bandit_weights(bandit, ["ollama/qwen2.5:0.5b"])
    assert jol._last_sync > 0


@pytest.mark.asyncio
async def test_sync_bandit_weights_smoothing(jol):
    jol._last_sync = 0
    bandit = MagicMock()
    bandit.credit_engine = MagicMock()
    key = ("critic", "ollama/qwen2.5:0.5b", "epsilon_greedy")
    bandit.credit_engine.stats = {
        key: {
            "success": 10,
            "fail": 1,
            "reward_total": 8.0,
            "reward_count": 11,
            "latency": 5.0,
        },
    }
    bandit.weights = {"ollama/qwen2.5:0.5b": 0.5}

    await jol.sync_bandit_weights(bandit, ["ollama/qwen2.5:0.5b"])
    new_weight = bandit.weights["ollama/qwen2.5:0.5b"]
    assert new_weight != 0.5
    assert 0.0 < new_weight <= 1.0


@pytest.mark.asyncio
async def test_sync_bandit_weights_substring_match(jol):
    jol._last_sync = 0
    bandit = MagicMock()
    bandit.credit_engine = MagicMock()
    key = ("critic", "ollama/qwen2.5:0.5b", "epsilon_greedy")
    bandit.credit_engine.stats = {
        key: {
            "success": 5,
            "fail": 0,
            "reward_total": 5.0,
            "reward_count": 5,
            "latency": 2.0,
        },
    }
    bandit.weights = {"ollama/qwen2.5:0.5b": 0.0}

    await jol.sync_bandit_weights(bandit, ["ollama/qwen2.5:0.5b"])
    assert bandit.weights["ollama/qwen2.5:0.5b"] > 0.0


@pytest.mark.asyncio
async def test_apply_decay(jol):
    jol._last_decay = 0
    credit = MagicMock()
    credit.stats = {
        ("critic", "ollama/model", "default"): {
            "success": 100,
            "fail": 10,
            "latency": 50.0,
            "reward_total": 80.0,
            "reward_count": 110,
        },
    }
    await jol.apply_decay(credit)
    stats = credit.stats[("critic", "ollama/model", "default")]
    assert stats["success"] < 100
    assert stats["fail"] < 10
    assert stats["latency"] < 50.0


@pytest.mark.asyncio
async def test_evaluate_colony_no_colony(jol):
    decisions = await jol.evaluate_colony()
    assert decisions == []


@pytest.mark.asyncio
async def test_evaluate_colony_apoptose_trigger():
    jol = JointOptimizationLoop()
    colony = MagicMock()
    colony._agentes = {
        "bad_agent": MagicMock(execucoes=10, falhas=8, latencia_media=15.0),
    }
    jol._colony = colony
    decisions = await jol.evaluate_colony()
    apoptoses = [d for d in decisions if d["action"] == "apoptose"]
    assert len(apoptoses) == 1
    assert apoptoses[0]["especializacao"] == "bad_agent"


@pytest.mark.asyncio
async def test_evaluate_colony_mitose_trigger():
    jol = JointOptimizationLoop()
    colony = MagicMock()
    colony._agentes = {
        "good_agent": MagicMock(execucoes=10, falhas=0, latencia_media=0.1),
    }
    jol._colony = colony
    decisions = await jol.evaluate_colony()
    mitoses = [d for d in decisions if d["action"] == "mitose"]
    assert len(mitoses) >= 1


@pytest.mark.asyncio
async def test_get_colony_report_empty(jol):
    report = await jol.get_colony_report()
    assert report["global_ivm"] == 0.5
    assert report["total_executions"] == 0


@pytest.mark.asyncio
async def test_get_colony_report_with_data(jol):
    await jol.ingest("coder", True, 1.0)
    await jol.ingest("tester", True, 2.0)
    await jol.ingest("debugger", False, 5.0)
    report = await jol.get_colony_report()
    assert report["total_executions"] == 3
    assert report["total_success"] == 2
    assert report["total_fail"] == 1
    assert len(report["nodes"]) == 3


@pytest.mark.asyncio
async def test_bind_colony(jol):
    colony = MagicMock()
    jol.bind_colony(colony)
    assert jol._colony is colony


@pytest.mark.asyncio
async def test_ingest_updates_node_stats(jol):
    await jol.ingest("coder", True, 1.0, 0.001)
    await jol.ingest("coder", False, 5.0, 0.002)
    async with jol._lock:
        stats = jol._node_stats["coder"]
    assert stats["count"] == 2
    assert stats["success"] == 1
    assert stats["fail"] == 1
    assert stats["latency_sum"] == 6.0
    assert stats["cost_sum"] == 0.003


@pytest.mark.asyncio
async def test_sync_bandit_no_credit_engine(jol):
    jol._last_sync = 0
    bandit = MagicMock()
    bandit.credit_engine = None
    await jol.sync_bandit_weights(bandit, ["model"])
    assert jol._last_sync > 0
