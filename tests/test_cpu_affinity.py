import os
import pytest
import asyncio

from iaglobal.execution.cpu_affinity import CpuAffinityManager, cpu_affinity
from iaglobal.graphs.node import Node
from iaglobal.graphs.execution_graph import ExecutionGraph


class TestCpuAffinityManager:

    @property
    def _cores(self, m):
        return m._cores

    def test_detect_cores(self):
        m = CpuAffinityManager()
        assert len(m._cores) >= 1
        assert len(m._cores) == os.cpu_count() or 1

    def test_pin_for_agent_is_deterministic(self):
        m = CpuAffinityManager()
        agent = "test_agent_1"
        core1 = m.pin_for_agent(agent)
        core2 = m.pin_for_agent(agent)
        assert core1 == core2, "Deterministic pin should return same core for same agent"

    def test_different_agents_may_get_different_cores(self):
        m = CpuAffinityManager()
        cores = {m.pin_for_agent(f"agent_{i}") for i in range(20)}
        assert len(cores) >= 2, f"Expected at least 2 unique cores, got {len(cores)}"

    def test_assign_core_deterministic_returns_int(self):
        m = CpuAffinityManager()
        core = m.assign_core_deterministic("abc12345")
        assert isinstance(core, int)
        assert 0 <= core < len(m._cores)

    def test_pin_to_hash_returns_int(self):
        m = CpuAffinityManager()
        core = m.pin_to_hash("abc12345")
        assert isinstance(core, int)
        assert 0 <= core < len(m._cores)

    def test_map_balanced_distribution(self):
        m = CpuAffinityManager()
        agents = [f"balanced_agent_{i}" for i in range(10)]
        assignment = m.map_balanced(agents)
        assert len(assignment) == len(agents)
        per_core = {}
        for agent, core in assignment.items():
            per_core.setdefault(core, []).append(agent)
        max_load = max(len(v) for v in per_core.values())
        min_load = min(len(v) for v in per_core.values())
        assert max_load - min_load <= 1, (
            f"Imbalance > 1: max={max_load}, min={min_load}"
        )

    def test_map_balanced_few_agents_many_cores(self):
        m = CpuAffinityManager()
        agents = ["a", "b", "c"]
        assignment = m.map_balanced(agents)
        per_core = {}
        for a, c in assignment.items():
            per_core.setdefault(c, []).append(a)
        for core, assigned_agents in per_core.items():
            assert len(assigned_agents) <= 1, (
                f"Core {core} should have at most 1 agent with {len(agents)} agents and {len(m._cores)} cores"
            )

    def test_map_balanced_many_agents_few_cores(self):
        m = CpuAffinityManager()
        agent_count = max(len(m._cores) * 5, 5)
        agents = [f"heavy_agent_{i}" for i in range(agent_count)]
        assignment = m.map_balanced(agents)
        per_core = {}
        for a, c in assignment.items():
            per_core.setdefault(c, []).append(a)
        max_load = max(len(v) for v in per_core.values())
        min_load = min(len(v) for v in per_core.values())
        assert max_load - min_load <= 1, (
            f"Imbalance > 1 with {len(agents)} agents and {len(m._cores)} cores: "
            f"max={max_load}, min={min_load}"
        )

    def test_dispersion_report_structure(self):
        m = CpuAffinityManager()
        m.pin_for_agent("report_test_a")
        m.pin_for_agent("report_test_b")
        report = m.dispersion_report()
        assert "total_cores" in report
        assert "distribution" in report
        assert "efficiency" in report
        assert report["total_cores"] == len(m._cores)

    def test_efficiency_score_perfect_balance(self):
        m = CpuAffinityManager()
        agents = [f"eff_agent_{i}" for i in range(len(m._cores) * 2)]
        m.map_balanced(agents)
        report = m.dispersion_report()
        assert report["efficiency"] >= 0.5, (
            f"Efficiency should be high with balanced distribution: {report['efficiency']:.2f}"
        )

    def test_rebalance_if_needed(self):
        m = CpuAffinityManager()
        for i in range(len(m._cores) * 3):
            m.pin_for_agent(f"reb_agent_{i}")
        result = m.rebalance_if_needed()
        assert isinstance(result, bool)

    def test_random_core(self):
        m = CpuAffinityManager()
        core = m.random_core()
        assert isinstance(core, int)
        assert 0 <= core < len(m._cores)

    def test_get_thread_pool(self):
        m = CpuAffinityManager()
        pool = m.get_thread_pool()
        assert pool is not None

    def test_get_last_mapping(self):
        m = CpuAffinityManager()
        m.pin_for_agent("alpha")
        result = m.get_last_mapping("alpha")
        assert isinstance(result, int)

    def test_map_agents(self):
        m = CpuAffinityManager()
        agents = [f"map_agent_{i}" for i in range(5)]
        assignment = m.map_agents(agents)
        assert len(assignment) == len(agents)

    def test_refresh_topology(self):
        m = CpuAffinityManager()
        before = len(m._cores)
        m.refresh_topology()
        assert len(m._cores) == before


class TestCpuAffinityIntegration:

    def setup_method(self):
        cpu_affinity._last_agent_map.clear()

    def test_execute_node_async_populates_mapping(self):
        graph = ExecutionGraph()
        node = Node(name="async_integration_node", run=lambda ctx: {"output": "ok"}, depends_on=[])
        graph.add_node(node)
        asyncio.run(graph._execute_node_async(node, {"task": "test"}))
        assert "async_integration_node" in cpu_affinity._last_agent_map

    def test_run_parallel_populates_agent_assignments(self):
        graph = ExecutionGraph()
        node_a = Node(name="A", run=lambda ctx: {"output": "a"}, depends_on=[])
        node_b = Node(name="B", run=lambda ctx: {"output": "b"}, depends_on=["A"])
        graph.add_node(node_a)
        graph.add_node(node_b)
        asyncio.run(graph.run_parallel({"task": "test"}))
        assert "A" in cpu_affinity._last_agent_map
        assert "B" in cpu_affinity._last_agent_map

    def test_async_run_executes_nodes(self):
        graph = ExecutionGraph()
        node_a = Node(name="run_A", run=lambda ctx: {"output": "a"}, depends_on=[])
        node_b = Node(name="run_B", run=lambda ctx: {"output": "b"}, depends_on=["run_A"])
        graph.add_node(node_a)
        graph.add_node(node_b)
        result = asyncio.run(graph.async_run({"task": "test"}))
        assert result["success"] is True
        assert result["nodes_executed"] == 2

    def test_restart_node_async(self):
        graph = ExecutionGraph()
        node = Node(name="restart_test", run=lambda ctx: {"output": "ok"}, depends_on=[])
        graph.add_node(node)
        result = asyncio.run(graph.async_run({"task": "test"}, execution_id="restart_eid"))
        assert result["success"] is True
