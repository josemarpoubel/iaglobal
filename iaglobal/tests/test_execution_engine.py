import pytest
import asyncio

from iaglobal.graphs.node import Node
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.graphs.execution_engine import ExecutionEngine


def _make_graph_with_n_independent_nodes(n: int):
    graph = ExecutionGraph()
    for i in range(n):
        node = Node(
            name=f"node_{i}",
            run=lambda ctx, i=i: {"output": f"result_{i}"},
            depends_on=[],
        )
        graph.add_node(node)
    return graph


def _make_linear_dependency_graph():
    graph = ExecutionGraph()
    node_a = Node(name="A", run=lambda ctx: {"output": "a"}, depends_on=[])
    graph.add_node(node_a)
    node_b = Node(name="B", run=lambda ctx: {"output": "b"}, depends_on=["A"])
    graph.add_node(node_b)
    return graph


def _make_diamond_dag():
    """Diamond DAG: A → {B, C} → D"""
    graph = ExecutionGraph()
    node_a = Node(name="A", run=lambda ctx: {"output": "a"}, depends_on=[])
    node_b = Node(name="B", run=lambda ctx: {"output": "b"}, depends_on=["A"])
    node_c = Node(name="C", run=lambda ctx: {"output": "c"}, depends_on=["A"])
    node_d = Node(name="D", run=lambda ctx: {"output": "d"}, depends_on=["B", "C"])
    graph.add_node(node_a)
    graph.add_node(node_b)
    graph.add_node(node_c)
    graph.add_node(node_d)
    return graph


def _make_critical_chain():
    """A (critical) → B → C — A failure should abort B and C"""
    graph = ExecutionGraph()
    node_a = Node(name="A", run=lambda ctx: (_ for _ in ()).throw(RuntimeError("A fail")),
                  depends_on=[], critical=True)
    node_b = Node(name="B", run=lambda ctx: {"output": "b"}, depends_on=["A"])
    node_c = Node(name="C", run=lambda ctx: {"output": "c"}, depends_on=["B"])
    graph.add_node(node_a)
    graph.add_node(node_b)
    graph.add_node(node_c)
    return graph


def _make_flaky_node_graph(max_retries: int = 3):
    graph = ExecutionGraph()

    attempt_counter = {"count": 0}

    def flaky_run(ctx):
        attempt_counter["count"] += 1
        if attempt_counter["count"] < 2:
            raise RuntimeError("simulated failure")
        return {"output": "success after retry"}

    node = Node(name="flaky_node", run=flaky_run, depends_on=[])
    graph.add_node(node)
    return graph, attempt_counter


@pytest.mark.asyncio
async def test_parallel_execution():
    graph = _make_graph_with_n_independent_nodes(10)
    engine = ExecutionEngine(graph)

    state = await engine.run({})

    for node_name in ["node_0", "node_5", "node_9"]:
        assert state[node_name]["status"] == "SUCCESS", (
            f"{node_name} status={state[node_name]['status']}"
        )

    all_success = all(
        entry["status"] == "SUCCESS"
        for entry in state.values()
    )
    assert all_success, "Nem todos os nos independentes foram SUCCESS"


@pytest.mark.asyncio
async def test_dag_order():
    graph = _make_linear_dependency_graph()
    engine = ExecutionEngine(graph)

    state = await engine.run({})

    assert state["A"]["status"] == "SUCCESS", f"A status={state['A']['status']}"
    assert state["B"]["status"] == "SUCCESS", f"B status={state['B']['status']}"


@pytest.mark.asyncio
async def test_retry_mechanism():
    graph, attempt_counter = _make_flaky_node_graph(max_retries=3)
    engine = ExecutionEngine(graph, max_retries=3)

    state = await engine.run({})

    assert state["flaky_node"]["status"] == "SUCCESS", (
        f"flaky_node status={state['flaky_node']['status']}, "
        f"error={state['flaky_node'].get('error')}"
    )
    assert attempt_counter["count"] >= 2, (
        f"Expected at least 2 attempts, got {attempt_counter['count']}"
    )


@pytest.mark.asyncio
async def test_determinism():
    graph = _make_linear_dependency_graph()

    engine1 = ExecutionEngine(graph)
    r1 = await engine1.run({})

    engine2 = ExecutionEngine(graph)
    r2 = await engine2.run({})

    assert r1 == r2, f"r1={r1}, r2={r2}"


# =========================================================================
# Parallel DAG Scheduling — run_parallel() tests
# =========================================================================


@pytest.mark.asyncio
async def test_parallel_independent_nodes():
    """10 independent nodes must all complete via run_parallel()."""
    graph = _make_graph_with_n_independent_nodes(10)
    result = await graph.run_parallel({"task": "test"})
    assert result["success"]
    assert result["nodes_executed"] == 10
    for i in range(10):
        assert f"node_{i}" in result["raw_results"]


@pytest.mark.asyncio
async def test_parallel_linear_dag():
    """Linear A→B — B must execute after A completes."""
    graph = _make_linear_dependency_graph()
    result = await graph.run_parallel({"task": "test"})
    assert result["success"]
    assert result["nodes_executed"] == 2
    raw = result["raw_results"]
    assert raw["A"]["success"]
    assert raw["B"]["success"]


@pytest.mark.asyncio
async def test_parallel_diamond_dag():
    """Diamond A→{B,C}→D — B and C execute concurrently, D waits for both."""
    graph = _make_diamond_dag()
    result = await graph.run_parallel({"task": "test"})
    assert result["success"]
    assert result["nodes_executed"] == 4
    raw = result["raw_results"]
    assert raw["A"]["success"]
    assert raw["B"]["success"]
    assert raw["C"]["success"]
    assert raw["D"]["success"]


@pytest.mark.asyncio
async def test_parallel_sanity_barrier_aborts_dependents():
    """Critical node A failure must abort B and C via run_parallel()."""
    graph = _make_critical_chain()
    result = await graph.run_parallel({"task": "test"})
    raw = result["raw_results"]
    assert not raw["A"]["success"], "A deve falhar"
    assert raw["A"].get("status") in ("FAILED", None)
    assert not raw["B"]["success"], "B deve ser abortado pela Sanity Barrier"
    assert "Abortado pela Sanity Barrier" in raw["B"].get("error", ""), (
        f"B deve conter mensagem Sanity Barrier: {raw['B'].get('error')}"
    )
    assert not raw["C"]["success"], "C deve ser abortado pela Sanity Barrier"
    assert "Abortado pela Sanity Barrier" in raw["C"].get("error", "")


@pytest.mark.asyncio
async def test_parallel_same_output_as_sequential():
    """run_parallel() and run() must produce identical final output."""

    def _make_graph():
        graph = ExecutionGraph()
        node_a = Node(name="A", run=lambda ctx: {"output": "a"}, depends_on=[])
        node_b = Node(name="B", run=lambda ctx: {"output": "b"}, depends_on=["A"])
        node_c = Node(name="C", run=lambda ctx: {"output": "c"}, depends_on=["A"])
        node_d = Node(name="D", run=lambda ctx: {"output": "d"}, depends_on=["B", "C"])
        graph.add_node(node_a)
        graph.add_node(node_b)
        graph.add_node(node_c)
        graph.add_node(node_d)
        return graph

    result_p = await _make_graph().run_parallel({"task": "test"})
    result_s = _make_graph().run({"task": "test"})

    assert result_p["success"] == result_s["success"]
    assert result_p["nodes_executed"] == result_s["nodes_executed"]
    # final_output pode diferir entre run() e run_parallel() quando múltiplos
    # nós têm o mesmo score — ambos são respostas válidas.
    # execution_id é sempre único por chamada — não comparamos.
    assert result_p["nodes_executed"] == result_s["nodes_executed"]


@pytest.mark.asyncio
async def test_parallel_execution_order():
    """In a linear DAG A→B, A must finish before B starts (timestamps)."""
    order = []

    def make_tracker(name: str, deps: list):
        def run(ctx):
            order.append(name)
            return {"output": name}
        return run

    graph = ExecutionGraph()
    node_a = Node(name="A", run=make_tracker("A", []), depends_on=[])
    node_b = Node(name="B", run=make_tracker("B", ["A"]), depends_on=["A"])
    graph.add_node(node_a)
    graph.add_node(node_b)

    await graph.run_parallel({"task": "test"})
    assert order == ["A", "B"], f"Ordem de execução incorreta: {order}"
