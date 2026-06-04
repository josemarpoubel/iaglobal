"""
Testes do Pipeline V3 — DAG completo.

Verifica:
- PIPELINE_SKILLS tem a ordem topológica correta (22 nós V3)
- build_graph_from_skills cria todos os nós
- skills registradas
- importação correta dos novos módulos
"""

import pytest

from iaglobal.graphs.builder import PIPELINE_SKILLS


class TestPipelineV3Definition:

    def test_pipeline_v3_has_correct_nodes(self):
        names = [name for name, _ in PIPELINE_SKILLS]
        expected = [
            "prompt_intake",
            "enhancement",
            "orchestrator_agent",
            "pm",
            "requirements",
            "architect",
            "search",
            "knowledge",
            "dependency",
            "risk_analysis",
            "security_design",
            "performance_design",
            "planner",
            "coder",
            "reviewer",
            "semantic_validator",
            "security_audit",
            "performance_audit",
            "tester",
            "debugger",
            "documentation",
            "release",
            "metrics",
            "optimization",
            "result_agent",
        ]
        assert names == expected, f"Esperado {len(expected)} nós, got {len(names)}: {names}"

    def test_pipeline_v3_no_v2_leftovers(self):
        names = {name for name, _ in PIPELINE_SKILLS}
        v2_only = {"interpreter", "web_classifier", "style_validator", "critic",
                    "ast_validator", "rank_final", "final_gatekeeper", "artifact_writer",
                    "reflexion"}
        leftovers = v2_only & names
        assert not leftovers, f"Nós V2 ainda presentes: {leftovers}"

    def test_pipeline_v3_has_all_v3_nodes(self):
        names = {name for name, _ in PIPELINE_SKILLS}
        v3_nodes = {"prompt_intake", "enhancement", "orchestrator_agent",
                     "pm", "requirements", "architect", "search", "knowledge",
                     "dependency", "risk_analysis", "security_design", "performance_design",
                     "planner", "coder", "reviewer", "semantic_validator",
                     "security_audit", "performance_audit", "tester", "debugger",
                     "documentation", "release", "metrics", "optimization", "result_agent"}
        missing = v3_nodes - names
        assert not missing, f"Nós V3 faltando: {missing}"

    def test_pipeline_v3_dependencies_are_valid(self):
        all_names = {name for name, _ in PIPELINE_SKILLS}
        aliases = set()
        for name, opts in PIPELINE_SKILLS:
            alias = opts.get("name")
            if alias:
                aliases.add(alias)
        all_known = all_names | aliases
        for name, opts in PIPELINE_SKILLS:
            for dep in opts.get("depends_on", []):
                assert dep in all_known, f"'{name}' depende de '{dep}' que não existe (conhecidos: {all_known})"

    def test_pipeline_v3_has_no_cycles(self):
        visited = set()
        path = set()

        def visit(node):
            if node in path:
                raise AssertionError(f"Ciclo detectado envolvendo: {node}")
            if node in visited:
                return
            path.add(node)
            for name, opts in PIPELINE_SKILLS:
                if name == node:
                    for dep in opts.get("depends_on", []):
                        visit(dep)
            path.remove(node)
            visited.add(node)

        for name, _ in PIPELINE_SKILLS:
            visit(name)


class TestPipelineV3Imports:

    def test_import_enhancement_agent(self):
        from iaglobal.agents.enhancement_agent import EnhancementAgent
        assert EnhancementAgent is not None

    def test_import_security_design_agent(self):
        from iaglobal.agents.security_design_agent import SecurityDesignAgent
        assert SecurityDesignAgent is not None

    def test_import_performance_design_agent(self):
        from iaglobal.agents.performance_design_agent import PerformanceDesignAgent
        assert PerformanceDesignAgent is not None

    def test_import_security_audit_agent(self):
        from iaglobal.agents.security_audit_agent import SecurityAuditAgent
        assert SecurityAuditAgent is not None

    def test_import_performance_audit_agent(self):
        from iaglobal.agents.performance_audit_agent import PerformanceAuditAgent
        assert PerformanceAuditAgent is not None

    def test_import_result_agent(self):
        from iaglobal.agents.result_agent import ResultAgent
        assert ResultAgent is not None

    def test_import_new_skills(self):
        from iaglobal.evolution.skills.skill import (
            SKILL_ENHANCEMENT, SKILL_ORCHESTRATOR,
            SKILL_SECURITY_DESIGN, SKILL_PERFORMANCE_DESIGN,
            SKILL_SECURITY_AUDIT, SKILL_PERFORMANCE_AUDIT,
            SKILL_RESULT_AGENT,
        )
        assert SKILL_ENHANCEMENT.name == "enhancement"
        assert SKILL_ORCHESTRATOR.name == "orchestrator_agent"
        assert SKILL_SECURITY_DESIGN.name == "security_design"
        assert SKILL_PERFORMANCE_DESIGN.name == "performance_design"
        assert SKILL_SECURITY_AUDIT.name == "security_audit"
        assert SKILL_PERFORMANCE_AUDIT.name == "performance_audit"
        assert SKILL_RESULT_AGENT.name == "result_agent"


class TestPipelineAsyncExecution:

    def test_async_route_generate_imports(self):
        from iaglobal.providers.provider_router import async_route_generate
        import inspect
        assert inspect.iscoroutinefunction(async_route_generate)

    def test_async_providers_are_coroutines(self):
        import inspect
        from iaglobal.providers.ollama_provider import async_generate as o
        from iaglobal.providers.groq_provider import async_generate as g
        from iaglobal.providers.openrouter_provider import async_generate as r
        from iaglobal.providers.nvidia_provider import async_generate as n
        from iaglobal.providers.opencode_provider import async_generate as c
        for fn in [o, g, r, n, c]:
            assert inspect.iscoroutinefunction(fn), f"{fn} nao e coroutine"

    @pytest.mark.asyncio
    async def test_async_http_session(self):
        from iaglobal.providers.async_http import get_session, close_session
        session = await get_session()
        assert session is not None
        assert not session.closed
        await close_session()

    def test_execution_graph_has_async_method(self):
        from iaglobal.graphs.execution_graph import ExecutionGraph
        import inspect
        graph = ExecutionGraph()
        assert hasattr(graph, "async_run")
        assert inspect.iscoroutinefunction(graph.async_run)

    @pytest.mark.asyncio
    async def test_async_run_with_mock_nodes(self):
        from unittest.mock import patch
        from iaglobal.graphs.execution_graph import ExecutionGraph
        from iaglobal.graphs.node import Node

        graph = ExecutionGraph()
        graph.add_node(Node(name="node_a", run=lambda ctx: {"output": "a"}, depends_on=[]))
        graph.add_node(Node(name="node_b", run=lambda ctx: {"output": "b"}, depends_on=["node_a"]))

        with patch("iaglobal.graphs.execution_graph.checkpoint_db") as mock_db, \
             patch("iaglobal.graphs.execution_graph.exec_registry") as mock_reg, \
             patch("iaglobal.graphs.execution_graph.canonicalize", lambda x: x), \
             patch("iaglobal.graphs.execution_graph.make_context", return_value={}), \
             patch("iaglobal.graphs.execution_graph.compute_graph_hash", return_value=""):
            mock_reg.init_execution.return_value = None
            mock_reg.was_executed.return_value = False
            mock_reg.claim.return_value = True
            mock_db.get_checkpoint.return_value = {}
            mock_db.init_execution.return_value = None
            mock_db.get_node_retry_count.return_value = 0
            result = await graph.async_run({"task": "test"})
            assert result["success"] is True
            assert len(result["raw_results"]) == 2

    @pytest.mark.asyncio
    async def test_parallel_run_with_independent_nodes(self):
        from unittest.mock import patch
        from iaglobal.graphs.execution_graph import ExecutionGraph
        from iaglobal.graphs.node import Node

        graph = ExecutionGraph()
        for i in range(6):
            graph.add_node(Node(
                name=f"node_{i}",
                run=lambda ctx, i=i: {"output": f"done_{i}", "success": True},
                depends_on=[],
            ))

        with patch("iaglobal.graphs.execution_graph.checkpoint_db") as mock_db, \
             patch("iaglobal.graphs.execution_graph.exec_registry") as mock_reg, \
             patch("iaglobal.graphs.execution_graph.canonicalize", lambda x: x), \
             patch("iaglobal.graphs.execution_graph.make_context", return_value={}), \
             patch("iaglobal.graphs.execution_graph.compute_graph_hash", return_value=""):
            mock_reg.init_execution.return_value = None
            mock_reg.was_executed.return_value = False
            mock_reg.claim.return_value = True
            mock_db.get_checkpoint.return_value = {}
            mock_db.init_execution.return_value = None
            mock_db.get_node_retry_count.return_value = 0
            result = await graph.run_parallel({"task": "test"})
            assert result["success"] is True
            assert len(result["raw_results"]) == 6
            for name, res in result["raw_results"].items():
                assert res.get("success"), f"{name} falhou"

    @pytest.mark.asyncio
    async def test_parallel_run_with_linear_dag(self):
        from unittest.mock import patch
        from iaglobal.graphs.execution_graph import ExecutionGraph
        from iaglobal.graphs.node import Node

        graph = ExecutionGraph()
        graph.add_node(Node(name="a", run=lambda ctx: {"output": "a", "success": True}, depends_on=[]))
        graph.add_node(Node(name="b", run=lambda ctx: {"output": "b", "success": True}, depends_on=["a"]))
        graph.add_node(Node(name="c", run=lambda ctx: {"output": "c", "success": True}, depends_on=["b"]))
        graph.add_node(Node(name="d", run=lambda ctx: {"output": "d", "success": True}, depends_on=["c"]))

        with patch("iaglobal.graphs.execution_graph.checkpoint_db") as mock_db, \
             patch("iaglobal.graphs.execution_graph.exec_registry") as mock_reg, \
             patch("iaglobal.graphs.execution_graph.canonicalize", lambda x: x), \
             patch("iaglobal.graphs.execution_graph.make_context", return_value={}), \
             patch("iaglobal.graphs.execution_graph.compute_graph_hash", return_value=""):
            mock_reg.init_execution.return_value = None
            mock_reg.was_executed.return_value = False
            mock_reg.claim.return_value = True
            mock_db.get_checkpoint.return_value = {}
            mock_db.init_execution.return_value = None
            mock_db.get_node_retry_count.return_value = 0
            result = await graph.run_parallel({"task": "test"})
            assert result["success"] is True
            assert len(result["raw_results"]) == 4

    @pytest.mark.asyncio
    async def test_parallel_via_orchestrator(self):
        from unittest.mock import patch, MagicMock, AsyncMock
        from iaglobal.core.orchestrator import Orchestrator

        orch = Orchestrator.__new__(Orchestrator)
        orch.graph = MagicMock()
        orch.graph.run_parallel = AsyncMock(return_value={"success": True, "raw_results": {}})
        orch.graph.async_run = AsyncMock(return_value={"success": True, "raw_results": {}})
        orch.evolver = MagicMock()
        orch.evolver.designer = MagicMock()
        orch.evolver.designer.specialization_instructions = {}

        # parallel=True -> calls run_parallel
        result = await orch.async_run_graph_task("task", parallel=True)
        orch.graph.run_parallel.assert_awaited_once()
        assert result["success"] is True

        # parallel=False -> calls async_run
        result2 = await orch.async_run_graph_task("task", parallel=False)
        orch.graph.async_run.assert_awaited_once()
        assert result2["success"] is True

    @pytest.mark.asyncio
    async def test_parallel_via_pipeline_async_execute(self):
        from unittest.mock import patch, MagicMock, AsyncMock
        from iaglobal.pipeline.engine import PipelineEngine

        engine = PipelineEngine.__new__(PipelineEngine)
        engine.orchestrator = MagicMock()
        engine.orchestrator.bandit = MagicMock()
        engine.orchestrator.bandit.select_model = MagicMock(return_value="test-model")
        engine.orchestrator.async_run_graph_task = AsyncMock(
            return_value={"success": True, "raw_results": {}}
        )
        engine.orchestrator.evolver = MagicMock()

        with patch("iaglobal.pipeline.engine.credit_candidates_fn",
                   return_value=[("test", "test-model")]), \
             patch("iaglobal.pipeline.engine.PipelineEngine._memory_stage",
                   return_value=None), \
             patch("iaglobal.pipeline.engine.PipelineEngine._async_persistence_stage",
                   AsyncMock()), \
             patch("iaglobal.pipeline.engine.PipelineEngine._save_script",
                   return_value="/tmp/test.py"), \
             patch("iaglobal.pipeline.engine.ValidationEngine"):
            result = await engine.async_execute("test task", parallel=True)
            engine.orchestrator.async_run_graph_task.assert_awaited_with(
                "test task", chosen_model="test-model", parallel=True
            )
            assert result.success is True
