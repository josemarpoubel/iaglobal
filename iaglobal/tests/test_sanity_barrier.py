import os
import sys
import unittest
from unittest.mock import patch, MagicMock

raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, raiz_projeto)

from iaglobal.graphs.node import Node
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.models.event_bus import bus, EventType


class TestNodeCriticalFlag(unittest.TestCase):
    def test_node_default_not_critical(self):
        node = Node(name="test", run=lambda ctx: {"output": "ok"})
        self.assertFalse(node.critical)

    def test_node_can_be_critical(self):
        node = Node(name="planner", run=lambda ctx: {"output": "ok"}, critical=True)
        self.assertTrue(node.critical)


class TestSanityBarrierExecutionGraph(unittest.TestCase):
    def setUp(self):
        bus.reset()
        from iaglobal.evolution.skills.skill_registry import skill_registry
        skill_registry.clear()
        from iaglobal.memory.db_manager import db as checkpoint_db

        self.checkpoint_db = checkpoint_db
        self.execution_id = "test_sanity_" + str(os.getpid())

        self.route_generate_patch = patch(
            "iaglobal.providers.provider_router.route_generate"
        )
        self.mock_route = self.route_generate_patch.start()
        self.mock_route.return_value = "mock output"

        self.graph = ExecutionGraph()

        self.critical_fail_node = Node(
            name="planner",
            run=lambda ctx: (_ for _ in ()).throw(Exception("LLM offline")),
            critical=True,
        )
        self.dependent_node = Node(
            name="tester",
            run=lambda ctx: {"output": "test ok"},
            depends_on=["planner"],
        )
        self.independent_node = Node(
            name="coder",
            run=lambda ctx: {"output": "code ok"},
            depends_on=[],
        )

        self.graph.add_node(self.critical_fail_node)
        self.graph.add_node(self.dependent_node)
        self.graph.add_node(self.independent_node)

    def tearDown(self):
        self.checkpoint_db.clear_execution(self.execution_id)
        self.route_generate_patch.stop()
        bus.reset()

    def test_critical_node_failure_aborts_dependents(self):
        def on_critical(event):
            self.critical_events.append(event)

        def on_sanity(event):
            self.sanity_events.append(event)

        self.critical_events = []
        self.sanity_events = []

        bus.subscribe(EventType.CRITICAL_NODE_FAILED, on_critical)
        bus.subscribe(EventType.SANITY_BARRIER_TRIGGERED, on_sanity)

        call_count = [0]

        def route_side_effect(model, prompt, task_type=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("LLM offline")
            return "mock output"

        self.mock_route.side_effect = route_side_effect
        result = self.graph.run({"task": "test task"}, execution_id=self.execution_id)

        raw = result.get("raw_results", {})
        planner_result = raw.get("planner", {})
        tester_result = raw.get("tester", {})
        coder_result = raw.get("coder", {})

        self.assertFalse(planner_result.get("success", True))
        self.assertEqual(
            tester_result.get("status"),
            "ABORTED",
            "Nó dependente deveria estar ABORTED",
        )
        self.assertIn("Sanity Barrier", tester_result.get("error", ""))
        self.assertTrue(coder_result.get("success", True), "Nó independente deve executar normalmente")

        self.assertEqual(len(self.critical_events), 1)
        self.assertEqual(self.critical_events[0].data["node_id"], "planner")
        self.assertEqual(len(self.sanity_events), 1)

    def test_non_critical_node_does_not_abort_dependents(self):
        bus.reset()
        non_critical_exec_id = self.execution_id + "_nc"
        graph = ExecutionGraph()

        normal_fail_node = Node(
            name="normal_agent",
            run=lambda ctx: (_ for _ in ()).throw(Exception("normal error")),
            critical=False,
        )
        dependent = Node(
            name="dependent",
            run=lambda ctx: {"output": "should still run"},
            depends_on=["normal_agent"],
        )
        graph.add_node(normal_fail_node)
        graph.add_node(dependent)

        self.mock_route.side_effect = Exception("normal error")
        result = graph.run({"task": "test"}, execution_id=non_critical_exec_id)
        try:
            self.checkpoint_db.clear_execution(non_critical_exec_id)
        except Exception:
            pass

        self.mock_route.side_effect = None
        self.mock_route.return_value = "mock output"

        raw = result.get("raw_results", {})
        normal_result = raw.get("normal_agent", {})
        dependent_result = raw.get("dependent", {})

        self.assertFalse(normal_result.get("success", True))
        self.assertNotEqual(
            dependent_result.get("status"),
            "ABORTED",
            "Nó dependente NÃO deve ser abortado quando nó não-crítico falha",
        )


class TestOrchestratorSanityBarrier(unittest.TestCase):
    def setUp(self):
        bus.reset()
        from iaglobal.core.orchestrator import Orchestrator

        self.orch = Orchestrator()

    def tearDown(self):
        if hasattr(self.orch, "evolution_runtime"):
            self.orch.evolution_runtime.stop()
        bus.reset()

    def test_on_critical_node_failed_analisa_falha(self):
        with patch.object(self.orch, "_analisar_falha_critica") as mock_analise:
            bus.publish(
                EventType.CRITICAL_NODE_FAILED,
                {
                    "execution_id": "exec_001",
                    "node_id": "planner",
                    "error": "LLM offline",
                    "retry_count": 1,
                    "aborted_dependents": ["tester", "debugger"],
                },
                source="test",
            )
            mock_analise.assert_called_once_with("planner", "LLM offline", "exec_001")

    def test_sanity_barrier_triggered_registra_erro(self):
        with patch("iaglobal.memory.memory_error.store_error") as mock_store:
            bus.publish(
                EventType.SANITY_BARRIER_TRIGGERED,
                {
                    "failed_node": "planner",
                    "error": "Plano inválido",
                    "reason": "Nó crítico 'planner' falhou",
                },
                source="test",
            )
            mock_store.assert_called_once()
            args, kwargs = mock_store.call_args
            self.assertIn("sanity_barrier", kwargs.get("prompt", ""))

    def test_analisar_falha_critica_salva_insight(self):
        with patch("iaglobal.memory.db_manager.DatabaseManager.insert_insight") as mock_insert:
            resultado = self.orch._analisar_falha_critica(
                "planner", "LLM timeout", "exec_002"
            )
            self.assertTrue(len(resultado) > 0)
            mock_insert.assert_called_once()
            args, kwargs = mock_insert.call_args
            self.assertIn("planner", kwargs.get("agent", ""))


class TestMultiAgentSanityBarrier(unittest.TestCase):
    def test_sanity_barrier_on_planner_failure(self):
        import sys
        import builtins
        from unittest.mock import MagicMock, patch

        mock_router_module = MagicMock()
        mock_router_module._router = MagicMock()
        mock_router_module._router.classify_intent.return_value = "GENERAL"

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "requests":
                mock_req = MagicMock()
                mock_req.get.return_value.status_code = 200
                mock_req.get.return_value.json.return_value = {"results": []}
                return mock_req
            if name == "iaglobal.core.router":
                return mock_router_module
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            from iaglobal.memory.db_manager import DatabaseManager
            from iaglobal.agents.multi_agent import Multi_Agent

            with patch("iaglobal.agents.multi_agent.PlannerAgent") as mock_planner_cls, \
                 patch("iaglobal.agents.multi_agent.buscar_solucao_anterior") as mock_busca, \
                 patch("iaglobal.agents.multi_agent.EventType") as mock_et, \
                 patch.object(DatabaseManager, "insert_insight") as mock_insight, \
                 patch("iaglobal.agents.multi_agent.store_error") as mock_store_error, \
                 patch("iaglobal.agents.multi_agent.bus.publish") as mock_bus_publish:

                mock_et.SANITY_BARRIER_TRIGGERED = "sanity_barrier_triggered"
                mock_busca.return_value = None

                mock_planner = MagicMock()
                mock_planner.criar_plano_execucao.return_value = None
                mock_planner_cls.return_value = mock_planner

                ma = Multi_Agent()
                resultado = ma.resolver("tarefa teste")

        self.assertIn("SANITY BARRIER", resultado)
        self.assertIn("Pipeline interrompido", resultado)


if __name__ == "__main__":
    unittest.main()
