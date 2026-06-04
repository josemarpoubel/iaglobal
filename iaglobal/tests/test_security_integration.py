"""Tests for security module integration (SandboxExecutor, ASTGateway + SandboxRules, feedback loop)."""

import os
import sys
import unittest
import unittest.mock

raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, raiz_projeto)

from iaglobal.security.ast_gateway import ASTGateway, ASTResult
from iaglobal.security.sandbox_rules import SandboxRules
from iaglobal.security.sandbox_executor import SandboxExecutor, _sandbox_preexec
from iaglobal.security import SecurityEngine


class TestSandboxRules(unittest.TestCase):
    def test_allowed_modules_are_prepopulated(self):
        rules = SandboxRules()
        self.assertIn("math", rules.allowed_modules)
        self.assertIn("json", rules.allowed_modules)
        self.assertIn("collections", rules.allowed_modules)
        self.assertNotIn("os", rules.allowed_modules)
        self.assertNotIn("subprocess", rules.allowed_modules)

    def test_add_allowed_module(self):
        rules = SandboxRules()
        rules.add_allowed_module("numpy")
        self.assertIn("numpy", rules.allowed_modules)

    def test_block_operation(self):
        rules = SandboxRules()
        self.assertTrue(rules.is_operation_allowed("eval"))
        rules.block_operation("eval")
        self.assertFalse(rules.is_operation_allowed("eval"))

    def test_path_whitelist_read_permitido(self):
        rules = SandboxRules()
        self.assertTrue(rules.is_path_allowed_for_read("/tmp/file.txt"))
        self.assertTrue(rules.is_path_allowed_for_read("/dev/null"))

    def test_path_whitelist_read_bloqueado(self):
        rules = SandboxRules()
        self.assertFalse(rules.is_path_allowed_for_read("/etc/passwd"))
        self.assertFalse(rules.is_path_allowed_for_read("/home/user/secret.txt"))

    def test_path_whitelist_write_permitido(self):
        rules = SandboxRules()
        self.assertTrue(rules.is_path_allowed_for_write("/tmp/out.txt"))

    def test_path_whitelist_write_bloqueado(self):
        rules = SandboxRules()
        self.assertFalse(rules.is_path_allowed_for_write("/etc/config"))
        self.assertFalse(rules.is_path_allowed_for_write("/root/id_rsa"))

    def test_add_custom_path_rule(self):
        rules = SandboxRules()
        rules.add_allowed_read_path("/var/data")
        self.assertTrue(rules.is_path_allowed_for_read("/var/data/file.csv"))

    def test_block_path(self):
        rules = SandboxRules()
        rules.block_path("/opt")
        self.assertFalse(rules.is_path_allowed_for_read("/opt/app/config"))
        self.assertFalse(rules.is_path_allowed_for_write("/opt/app/data"))

    def test_env_sanitization_remove_sensiveis(self):
        rules = SandboxRules()
        env = {"PATH": "/usr/bin", "AWS_SECRET_ACCESS_KEY": "supersecret", "HOME": "/root"}
        clean = rules.sanitize_environment(env)
        self.assertIn("PATH", clean)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", clean)
        self.assertIn("HOME", clean)

    def test_env_sanitization_adiciona_sandbox_vars(self):
        rules = SandboxRules()
        env = rules.sanitize_environment({})
        self.assertIsInstance(env, dict)

    def test_get_config_snapshot(self):
        rules = SandboxRules()
        snap = rules.get_config_snapshot()
        self.assertIn("allowed_modules", snap)
        self.assertIn("blocked_paths", snap)
        self.assertIn("blocked_env_vars", snap)
        self.assertIn("stats", snap)
        self.assertGreater(len(snap["allowed_modules"]), 10)

    def test_get_stats(self):
        rules = SandboxRules()
        rules.is_module_allowed("os")
        rules.is_path_allowed_for_read("/etc/passwd")
        stats = rules.get_stats()
        self.assertGreaterEqual(stats["modules_checked"], 1)
        self.assertGreaterEqual(stats["paths_checked"], 1)

    def test_enable_disable(self):
        rules = SandboxRules()
        self.assertTrue(rules.is_enabled())
        rules.disable()
        self.assertFalse(rules.is_enabled())
        rules.enable()
        self.assertTrue(rules.is_enabled())


class TestASTGatewayWithSandboxRules(unittest.TestCase):
    def setUp(self):
        self.rules = SandboxRules()
        self.gateway = ASTGateway(sandbox_rules=self.rules)

    def test_allows_safe_code_no_imports(self):
        result = self.gateway.parse("x = 1 + 1")
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_allows_allowed_import(self):
        self.rules.add_allowed_module("json")
        result = self.gateway.parse("import json")
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_allows_allowed_from_import(self):
        self.rules.add_allowed_module("math")
        result = self.gateway.parse("from math import sqrt")
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_blocks_disallowed_import(self):
        result = self.gateway.parse("import os")
        self.assertFalse(result.valid)
        self.assertTrue(any("os" in e for e in result.errors))

    def test_blocks_disallowed_from_import(self):
        result = self.gateway.parse("from subprocess import Popen")
        self.assertFalse(result.valid)
        self.assertTrue(any("subprocess" in e for e in result.errors))

    def test_blocks_unsafe_calls(self):
        result = self.gateway.parse("eval('1+1')")
        self.assertFalse(result.valid)
        self.assertTrue(any("eval" in e for e in result.errors))

    def test_blocks_unsafe_attribute_access(self):
        result = self.gateway.parse("os.system('ls')")
        self.assertFalse(result.valid)
        self.assertTrue(any("system" in e for e in result.errors))

    def test_blocks_dunder_access(self):
        result = self.gateway.parse("[].__class__.__base__.__subclasses__()")
        self.assertFalse(result.valid)
        self.assertTrue(any("__subclasses__" in e or "__class__" in e or "dunder" in e for e in result.errors))

    def test_accepts_safe_function_definition(self):
        code = """
def calculate(n):
    import math
    return math.sqrt(n)
"""
        self.rules.add_allowed_module("math")
        result = self.gateway.parse(code)
        self.assertTrue(result.valid)

    def test_empty_code(self):
        result = self.gateway.parse("")
        self.assertFalse(result.valid)
        self.assertIn("Empty", " ".join(result.errors))

    def test_invalid_syntax(self):
        result = self.gateway.parse("def foo(:")
        self.assertFalse(result.valid)
        self.assertTrue(len(result.errors) > 0)

    def test_gateway_uses_default_rules_if_none_given(self):
        gateway = ASTGateway()
        self.assertIsNotNone(gateway.sandbox_rules)


class TestSandboxExecutorExecute(unittest.TestCase):
    def setUp(self):
        self.rules = SandboxRules()
        self.executor = SandboxExecutor(sandbox_rules=self.rules)

    def test_execute_simple_code(self):
        result = self.executor.execute("print('hello')")
        self.assertTrue(result.get("sucesso"), f"Failed: {result}")
        self.assertIn("hello", result.get("stdout", ""))

    def test_execute_math_expression(self):
        result = self.executor.execute("print(2 + 2)")
        self.assertTrue(result.get("sucesso"))
        self.assertIn("4", result.get("stdout", ""))

    def test_execute_blocks_disallowed_import(self):
        result = self.executor.execute("import os\nprint('should not run')")
        self.assertFalse(result.get("sucesso"))
        self.assertEqual(result.get("erro"), "SecurityViolation")

    def test_execute_empty_code(self):
        result = self.executor.execute("")
        self.assertFalse(result.get("sucesso"))
        self.assertEqual(result.get("erro"), "EmptyCode")


class TestSandboxExecutorValidate(unittest.TestCase):
    def setUp(self):
        self.executor = SandboxExecutor()

    def test_validate_good_code(self):
        result = self.executor.validate("x = 1")
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])

    def test_validate_bad_code(self):
        result = self.executor.validate("import os")
        self.assertFalse(result["valid"])
        self.assertTrue(len(result["errors"]) > 0)


class TestSecurityEngineIntegration(unittest.TestCase):
    def setUp(self):
        self.engine = SecurityEngine()

    def test_validate_and_prepare_allows_safe_code(self):
        valid, errors = self.engine.validate_and_prepare("x = 1")
        self.assertTrue(valid)
        self.assertEqual(errors, [])

    def test_validate_and_prepare_blocks_unsafe_import(self):
        valid, errors = self.engine.validate_and_prepare("import os")
        self.assertFalse(valid)
        self.assertTrue(len(errors) > 0)

    def test_execute_uses_sandbox(self):
        result = self.engine.execute("print('engine test')")
        self.assertTrue(result.get("sucesso"), f"Failed: {result}")

    def test_execute_blocks_unsafe_code(self):
        result = self.engine.execute("import subprocess")
        self.assertFalse(result.get("sucesso"))


class TestCoderAgentSecurityFeedback(unittest.TestCase):
    """Verify that CoderAgent accepts and uses security_feedback parameter."""

    def test_gerar_codigo_accepts_security_feedback(self):
        from iaglobal.agents.coder_agent import CoderAgent

        agent = CoderAgent()
        feedback = "Module 'os' is not in allowed_modules"
        with unittest.mock.patch('iaglobal.agents.coder_agent.executar') as mock_exec:
            mock_exec.return_value = "```python\nprint('safe')\n```"
            result = agent.gerar_codigo("test task", security_feedback=feedback)
            self.assertIn("print('safe')", result)
            mock_exec.assert_called_once()
            args, kwargs = mock_exec.call_args
            payload = args[1]
            self.assertIn(feedback, payload["task"])


if __name__ == "__main__":
    unittest.main()
