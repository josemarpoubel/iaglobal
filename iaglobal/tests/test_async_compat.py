"""
Teste: verifica que graph.run() (sync) executa run functions async corretamente.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from iaglobal.graphs.node import Node
from iaglobal.graphs.execution_graph import ExecutionGraph


def _make_workdir_mock():
    wd = MagicMock()
    wd.async_write_code = AsyncMock(return_value=wd)
    wd.async_write_output = AsyncMock(return_value=wd)
    wd.async_append_log = AsyncMock(return_value=wd)
    wd.write_code = MagicMock(return_value=wd)
    wd.write_output = MagicMock(return_value=wd)
    wd.append_log = MagicMock(return_value=wd)
    return wd


def _make_mocks():
    return (
        patch("iaglobal.graphs.execution_graph.checkpoint_db"),
        patch("iaglobal.graphs.execution_graph.exec_registry"),
        patch("iaglobal.graphs.execution_graph.canonicalize", lambda x: x),
        patch("iaglobal.graphs.execution_graph.make_context", return_value={}),
        patch("iaglobal.graphs.execution_graph.compute_graph_hash", return_value=""),
        patch("iaglobal.graphs.execution_graph.skill_executor"),
        patch("iaglobal.graphs.execution_graph.make_workdir", return_value=_make_workdir_mock()),
    )


def test_sync_run_with_async_run_function():
    graph = ExecutionGraph()

    async def async_run(ctx):
        return {"output": "hello from async"}

    node = Node(name="test_async_node", run=async_run, depends_on=[])
    graph.add_node(node)

    mocks = _make_mocks()
    with mocks[0] as mock_db, mocks[1] as mock_reg, mocks[2], mocks[3], mocks[4], mocks[5] as mock_skill, mocks[6] as mock_wd:
        mock_skill.can_execute.return_value = False
        mock_reg.init_execution.return_value = None
        mock_reg.was_executed.return_value = False
        mock_reg.claim.return_value = True
        mock_db.get_checkpoint.return_value = {}
        mock_db.init_execution.return_value = None
        mock_db.get_node_retry_count.return_value = 0

        result = graph.run({"task": "test"})

    assert result["success"] is True
    raw = result.get("raw_results", {})
    node_result = raw.get("test_async_node", {})
    output = node_result.get("output", "")
    assert output == "hello from async", f"Esperado 'hello from async', got '{output}'"


@pytest.mark.asyncio
async def test_async_run_with_async_run_function():
    graph = ExecutionGraph()

    async def async_run(ctx):
        return {"output": "hello from async"}

    node = Node(name="test_async_node", run=async_run, depends_on=[])
    graph.add_node(node)

    mocks = _make_mocks()
    with mocks[0] as mock_db, mocks[1] as mock_reg, mocks[2], mocks[3], mocks[4], mocks[5] as mock_skill, mocks[6] as mock_wd:
        mock_skill.can_execute.return_value = False
        mock_reg.init_execution.return_value = None
        mock_reg.was_executed.return_value = False
        mock_reg.claim.return_value = True
        mock_db.get_checkpoint.return_value = {}
        mock_db.init_execution.return_value = None
        mock_db.get_node_retry_count.return_value = 0

        result = await graph.async_run({"task": "test"})

    assert result["success"] is True
    raw = result.get("raw_results", {})
    node_result = raw.get("test_async_node", {})
    output = node_result.get("output", "")
    assert output == "hello from async", f"Got '{output}'"


def test_sync_run_coroutine_not_leaked():
    graph = ExecutionGraph()

    async def async_run(ctx):
        return {"output": "real output"}

    def sync_run(ctx):
        return {"output": "sync output"}

    for name, fn in [("async_node", async_run), ("sync_node", sync_run)]:
        graph.add_node(Node(name=name, run=fn, depends_on=[]))

    mocks = _make_mocks()
    with mocks[0] as mock_db, mocks[1] as mock_reg, mocks[2], mocks[3], mocks[4], mocks[5] as mock_skill, mocks[6] as mock_wd:
        mock_skill.can_execute.return_value = False
        mock_reg.init_execution.return_value = None
        mock_reg.was_executed.return_value = False
        mock_reg.claim.return_value = True
        mock_db.get_checkpoint.return_value = {}
        mock_db.init_execution.return_value = None
        mock_db.get_node_retry_count.return_value = 0

        result = graph.run({"task": "test"})

    final_output = result.get("final_output", "")
    assert "<coroutine object" not in final_output, (
        f"Coroutine leaked: '{final_output[:100]}'"
    )
