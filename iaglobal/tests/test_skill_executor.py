import os
import sys
import unittest
from unittest.mock import patch, MagicMock

raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, raiz_projeto)

from iaglobal.evolution.skills.skill_executor import SkillExecutor, SkillExecutionError
from iaglobal.evolution.skills.skill import Skill, ExecutionPolicy
from iaglobal.graphs.artifact import SolutionArtifact


class TestBuildContractCtx(unittest.TestCase):
    def setUp(self):
        self.executor = SkillExecutor()

    def test_extrai_task_do_input(self):
        skill = Skill(name="test", inputs=["task"])
        ctx = {"input": {"task": "hello"}, "memory": {}, "workdir": None}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertEqual(result.get("task"), "hello")

    def test_extrai_code_de_memory_output(self):
        skill = Skill(name="test", inputs=["code"])
        artifact = SolutionArtifact(code="print(1)")
        ctx = {"input": {}, "memory": {"coder": {"output": artifact}}, "workdir": None}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertEqual(result.get("code"), "print(1)")

    def test_extrai_artifact_de_memory_output(self):
        skill = Skill(name="test", inputs=["artifact"])
        artifact = SolutionArtifact(code="x = 1", score=85.0)
        ctx = {"input": {}, "memory": {"coder": {"output": artifact}}, "workdir": None}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertIs(result.get("artifact"), artifact)

    def test_extrai_error_de_runtime_error(self):
        skill = Skill(name="test", inputs=["error"])
        artifact = SolutionArtifact(runtime_error="div by zero")
        ctx = {"input": {}, "memory": {"tester": {"output": artifact}}, "workdir": None}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertEqual(result.get("error"), "div by zero")

    def test_extrai_score_do_artifact(self):
        skill = Skill(name="test", inputs=["score"])
        artifact = SolutionArtifact(score=92.5)
        ctx = {"input": {}, "memory": {"critic": {"output": artifact}}, "workdir": None}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertEqual(result.get("score"), 92.5)

    def test_extrai_plan_do_code_do_planner(self):
        skill = Skill(name="test", inputs=["plan"])
        artifact = SolutionArtifact(code="step1: do x")
        ctx = {"input": {}, "memory": {"planner": {"output": artifact}}, "workdir": None}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertEqual(result.get("plan"), "step1: do x")

    def test_extrai_needs_web_de_result_key(self):
        skill = Skill(name="test", inputs=["needs_web"])
        ctx = {"input": {}, "memory": {"web_classifier": {"needs_web": True, "output": ""}}, "workdir": None}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertTrue(result.get("needs_web"))

    def test_extrai_gatekeeper_passed_de_result_key(self):
        skill = Skill(name="test", inputs=["gatekeeper_passed"])
        ctx = {"input": {}, "memory": {"final_gatekeeper": {"gatekeeper_passed": True, "output": ""}}, "workdir": None}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertTrue(result.get("gatekeeper_passed"))

    def test_extrai_workdir_do_ctx_raiz(self):
        skill = Skill(name="test", inputs=["workdir"])
        ctx = {"input": {}, "memory": {}, "workdir": "/tmp/wd"}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertEqual(result.get("workdir"), "/tmp/wd")

    def test_extrai_execution_result_do_memory(self):
        skill = Skill(name="test", inputs=["execution_result"])
        memory = {"planner": {"output": "plan"}}
        ctx = {"input": {}, "memory": memory, "workdir": None}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertIs(result.get("execution_result"), memory)

    def test_retorna_dict_vazio_sem_inputs(self):
        skill = Skill(name="test", inputs=["nonexistent"])
        ctx = {"input": {}, "memory": {}, "workdir": None}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertNotIn("nonexistent", result)

    def test_extrai_code_de_output_string(self):
        skill = Skill(name="test", inputs=["code"])
        ctx = {"input": {}, "memory": {"coder": {"output": "raw_code"}}, "workdir": None}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertEqual(result.get("code"), "raw_code")

    def test_ignora_output_none(self):
        skill = Skill(name="test", inputs=["code"])
        ctx = {"input": {}, "memory": {"coder": {"output": None}}, "workdir": None}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertNotIn("code", result)

    def test_prioriza_ultimo_output_no_memory(self):
        skill = Skill(name="test", inputs=["code"])
        a1 = SolutionArtifact(code="old_code")
        a2 = SolutionArtifact(code="new_code")
        ctx = {"input": {}, "memory": {"n1": {"output": a1}, "n2": {"output": a2}}, "workdir": None}
        result = self.executor._build_contract_ctx(skill, ctx)
        self.assertEqual(result.get("code"), "new_code")


class TestSkillExecutorExecute(unittest.TestCase):
    def setUp(self):
        self.executor = SkillExecutor()

    def test_execute_com_inputs_disponiveis(self):
        skill = Skill(name="echo", inputs=["task"], run_fn=lambda ctx: {"output": ctx.get("input", {}).get("task", "")})
        self.executor.registry.register(skill)
        ctx = {"input": {"task": "hello"}, "memory": {}, "workdir": None}
        result = self.executor.execute("echo", ctx)
        self.assertEqual(result.get("output"), "hello")

    def test_execute_bloqueia_quando_input_faltando(self):
        skill = Skill(name="needy", inputs=["code", "error"], run_fn=lambda ctx: {"output": "ok"})
        self.executor.registry.register(skill)
        ctx = {"input": {"task": "x"}, "memory": {}, "workdir": None}
        with self.assertRaises(SkillExecutionError) as cm:
            self.executor.execute("needy", ctx)
        self.assertIn("code", str(cm.exception))
        self.assertIn("error", str(cm.exception))

    def test_execute_bloqueia_skill_inexistente(self):
        with self.assertRaises(SkillExecutionError) as cm:
            self.executor.execute("fake_skill", {})
        self.assertIn("fake_skill", str(cm.exception))

    def test_execute_bloqueia_skill_sem_run_fn(self):
        skill = Skill(name="empty", inputs=["task"])
        self.executor.registry.register(skill)
        ctx = {"input": {"task": "x"}, "memory": {}, "workdir": None}
        with self.assertRaises(SkillExecutionError) as cm:
            self.executor.execute("empty", ctx)
        self.assertIn("run_fn", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
