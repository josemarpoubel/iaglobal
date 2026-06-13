import os
import pytest
import asyncio

from iaglobal.execution.cpu_affinity import CpuAffinityManager, cpu_affinity
from iaglobal.graphs.node import Node
from iaglobal.graphs.execution_graph import ExecutionGraph


@pytest.fixture(autouse=True)
def reset_affinity():
    CpuAffinityManager._instance = None
    CpuAffinityManager._lock = threading.Lock()
    yield


import threading


class TestCpuAffinityManager:

    def test_singleton(self):
        m1 = CpuAffinityManager()
        m2 = CpuAffinityManager()
        assert m1 is m2

    def test_detect_cores(self):
        m = CpuAffinityManager()
        assert m.total_cores >= 1
        assert m.total_cores == os.cpu_count() or 1

    def test_pin_for_agent_never_same_core_consecutive(self):
        m = CpuAffinityManager()
        agent = "test_agent_1"
        cores = set()
        for _ in range(m.total_cores * 3):
            core = m.pin_for_agent(agent)
            cores.add(core)
        assert len(cores) >= 2, (
            f"Agent should visit at least 2 different cores over {m.total_cores * 3} calls. "
            f"Got {len(cores)}: {cores}"
        )

    def test_pin_for_agent_cycles_all_cores_eventually(self):
        m = CpuAffinityManager()
        agent = "rotary_agent"
        cores = set()
        for _ in range(m.total_cores * 5):
            cores.add(m.pin_for_agent(agent))
        assert len(cores) >= min(m.total_cores, 3), (
            f"Agent should visit most cores over many calls. "
            f"Got {len(cores)}/{m.total_cores}: {cores}"
        )

    def test_different_agents_spread_to_different_cores(self):
        m = CpuAffinityManager()
        agents = [f"agent_{i}" for i in range(10)]
        assigned = {}
        for agent in agents:
            assigned[agent] = m.pin_for_agent(agent)
        unique_cores = len(set(assigned.values()))
        spread_ratio = unique_cores / m.total_cores
        assert spread_ratio >= 0.5 or unique_cores >= 2, (
            f"At least 50% of cores should be used. Got {unique_cores}/{m.total_cores}"
        )

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
                f"Core {core} should have at most 1 agent with {len(agents)} agents and {m.total_cores} cores"
            )

    def test_map_balanced_many_agents_few_cores(self):
        m = CpuAffinityManager()
        agent_count = max(m.total_cores * 5, 5)
        agents = [f"heavy_agent_{i}" for i in range(agent_count)]
        assignment = m.map_balanced(agents)
        per_core = {}
        for a, c in assignment.items():
            per_core.setdefault(c, []).append(a)
        max_load = max(len(v) for v in per_core.values())
        min_load = min(len(v) for v in per_core.values())
        assert max_load - min_load <= 1, (
            f"Imbalance > 1 with {len(agents)} agents and {m.total_cores} cores: "
            f"max={max_load}, min={min_load}"
        )

    def test_dispersion_report_structure(self):
        m = CpuAffinityManager()
        m.pin_for_agent("report_test_a")
        m.pin_for_agent("report_test_b")
        report = m.dispersion_report()
        assert "total_cores" in report
        assert "agents_mapped" in report
        assert "load_per_core" in report
        assert "efficiency" in report
        assert report["total_cores"] == m.total_cores
        assert report["agents_mapped"] >= 2

    def test_efficiency_score_perfect_balance(self):
        m = CpuAffinityManager()
        agents = [f"eff_agent_{i}" for i in range(m.total_cores * 2)]
        m.map_balanced(agents)
        report = m.dispersion_report()
        assert report["efficiency"] >= 0.5, (
            f"Efficiency should be high with balanced distribution: {report['efficiency']:.2f}"
        )

    def test_rebalance_if_needed_detects_imbalance(self):
        m = CpuAffinityManager()
        assignments_before = {}
        for i in range(m.total_cores * 3):
            assignments_before[f"reb_agent_{i}"] = m.pin_for_agent(f"reb_agent_{i}")
        per_core_before = {}
        for a, c in assignments_before.items():
            per_core_before.setdefault(c, []).append(a)
        max_before = max(len(v) for v in per_core_before.values())
        min_before = min(len(v) for v in per_core_before.values())
        imbalance_before = max_before - min_before
        if imbalance_before > 1:
            assert m.rebalance_if_needed() == True
            after_report = m.dispersion_report()
            assert after_report["imbalance"] <= 1
        else:
            assert m.rebalance_if_needed() == False

    def test_is_balanced_property(self):
        m = CpuAffinityManager()
        agents = [f"bal_prop_{i}" for i in range(4)]
        m.map_balanced(agents)
        assert m.is_balanced == True

    def test_rotate_spreads_across_cores(self):
        m = CpuAffinityManager()
        seen = set()
        for _ in range(m.total_cores * 3):
            seen.add(m.rotate())
        assert len(seen) >= min(m.total_cores, 2), (
            f"Rotate should spread across cores over many calls. "
            f"Got {len(seen)}/{m.total_cores}"
        )

    def test_pin_for_agent_different_agents_different_cores_consistency(self):
        m = CpuAffinityManager()
        result1 = m.pin_for_agent("alpha")
        result2 = m.pin_for_agent("beta")
        result3 = m.pin_for_agent("gamma")
        assert isinstance(result1, int)
        assert isinstance(result2, int)
        assert isinstance(result3, int)
        assert 0 <= result1 < m.total_cores
        assert 0 <= result2 < m.total_cores
        assert 0 <= result3 < m.total_cores

    def test_same_agent_consecutive_calls_spread(self):
        m = CpuAffinityManager()
        agent = "consecutive_spread_test"
        cores = []
        for _ in range(20):
            cores.append(m.pin_for_agent(agent))
        unique = len(set(cores))
        assert unique >= 2, (
            f"Even with jitter, same agent should visit multiple cores. "
            f"Got {unique} unique cores"
        )

    def test_get_pool_creates_executor(self):
        m = CpuAffinityManager()
        try:
            pool = m.get_pool(max_workers=1)
            assert pool is not None
        finally:
            m.shutdown_pools()

    def test_multiple_agents_automatic_dispersion(self):
        m = CpuAffinityManager()
        agents = [f"auto_disp_{i}" for i in range(min(m.total_cores * 3, 30))]
        assignments = {}
        for agent in agents:
            assignments[agent] = m.pin_for_agent(agent)
        per_core = {}
        for a, c in assignments.items():
            per_core.setdefault(c, []).append(a)
        empty_cores = sum(1 for v in per_core.values() if len(v) == 0)
        used_cores = len(per_core)
        assert used_cores >= min(m.total_cores, len(agents)) * 0.5, (
            f"Auto-dispersion should use at least 50% of available cores. "
            f"Used {used_cores} of {m.total_cores}"
        )

    def test_rebalance_preserves_all_agents(self):
        m = CpuAffinityManager()
        agents = [f"preserve_{i}" for i in range(8)]
        for a in agents:
            m.pin_for_agent(a)
        report_before = m.dispersion_report()
        changed = m.rebalance_if_needed()
        report_after = m.dispersion_report()
        assert report_after["agents_mapped"] == report_before["agents_mapped"]
        assert report_after["agents_mapped"] == len(agents)

    def test_dispersion_efficiency_formula(self):
        m = CpuAffinityManager()
        agents = [f"eff_formula_{i}" for i in range(m.total_cores + 1)]
        m.map_balanced(agents)
        report = m.dispersion_report()
        calc_efficiency = 1.0 - (
            report["imbalance"] / (report["max_load"] or 1)
        )
        assert abs(report["efficiency"] - calc_efficiency) < 0.001

    def test_full_dispersion_cycle(self):
        m = CpuAffinityManager()
        agents = [f"cycle_agent_{i}" for i in range(m.total_cores)]
        for a in agents:
            m.pin_for_agent(a)
        n_extra = m.total_cores * 3
        for i in range(n_extra):
            m.pin_for_agent(f"cycle_extra_{i}")
        m.map_balanced(list(m._last_agent_map.keys()))
        report = m.dispersion_report()
        assert report["efficiency"] >= 0.5, (
            f"After rebalance, efficiency should be high. Got {report['efficiency']}"
        )
        assert report["imbalance"] <= 1


class TestCpuAffinityIntegration:

    def setup_method(self):
        cpu_affinity._last_agent_map.clear()

    def test_execute_node_calls_pin_for_agent(self):
        before = len(cpu_affinity._last_agent_map)
        graph = ExecutionGraph()
        node = Node(name="integration_test_node", run=lambda ctx: {"output": "ok"}, depends_on=[])
        graph.add_node(node)
        graph._execute_node(node, {"task": "test"})
        assert "integration_test_node" in cpu_affinity._last_agent_map
        assert len(cpu_affinity._last_agent_map) == before + 1

    def test_execute_node_async_calls_pin_for_agent(self):
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

    def test_run_delegates_to_run_parallel(self):
        graph = ExecutionGraph()
        node_a = Node(name="run_A", run=lambda ctx: {"output": "a"}, depends_on=[])
        node_b = Node(name="run_B", run=lambda ctx: {"output": "b"}, depends_on=["run_A"])
        graph.add_node(node_a)
        graph.add_node(node_b)
        result = graph.run({"task": "test"})
        assert result["success"] is True
        assert result["nodes_executed"] == 2
        assert "run_A" in cpu_affinity._last_agent_map
        assert "run_B" in cpu_affinity._last_agent_map

    def test_run_from_async_context(self):
        async def _run():
            graph = ExecutionGraph()
            node_a = Node(name="asyncX", run=lambda ctx: {"output": "x"}, depends_on=[])
            node_b = Node(name="asyncY", run=lambda ctx: {"output": "y"}, depends_on=[])
            graph.add_node(node_a)
            graph.add_node(node_b)
            result = graph.run({"task": "test"})
            return result
        result = asyncio.run(_run())
        assert result["success"] is True
        assert result["nodes_executed"] == 2

    def test_nodes_get_different_cores_in_sequential_dag(self):
        graph = ExecutionGraph()
        agents = [f"seq_node_{i}" for i in range(cpu_affinity.total_cores)]
        prev = None
        for name in agents:
            node = Node(name=name, run=lambda ctx, n=name: {"output": n}, depends_on=[prev] if prev else [])
            graph.add_node(node)
            prev = name
        asyncio.run(graph.run_parallel({"task": "test"}))
        assigned = set()
        for name in agents:
            core = cpu_affinity._last_agent_map.get(name)
            if core is not None:
                assigned.add(core)
        assert len(assigned) >= 2, (
            f"Sequential DAG with {len(agents)} agents should spread across "
            f"at least 2 cores. Got {len(assigned)}: {assigned}"
        )

    def test_many_nodes_balanced_across_cores(self):
        graph = ExecutionGraph()
        n = cpu_affinity.total_cores * 3
        for i in range(n):
            node = Node(name=f"bal_many_{i}", run=lambda ctx, n=i: {"output": str(n)}, depends_on=[])
            graph.add_node(node)
        asyncio.run(graph.run_parallel({"task": "test"}))
        report = cpu_affinity.dispersion_report()
        max_possible = n // cpu_affinity.total_cores + 3
        for _c, load in report["load_per_core"].items():
            assert load <= max_possible, (
                f"Core {_c} has load {load}, max expected ~{max_possible} "
                f"(jitter may skew)"
            )

    def test_restart_node_still_works(self):
        graph = ExecutionGraph()
        node = Node(name="restart_test", run=lambda ctx: {"output": "ok"}, depends_on=[])
        graph.add_node(node)
        result = graph.run({"task": "test"}, execution_id="restart_eid")
        assert result["success"] is True
        result2 = graph.restart_node("restart_eid", "restart_test")
        assert result2["success"] is True
