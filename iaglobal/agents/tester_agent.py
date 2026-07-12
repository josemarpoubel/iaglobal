# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/agents/tester_agent.py

import re
import ast
import hashlib
import asyncio
from dataclasses import dataclass
from typing import Union, Dict, Any, List, Optional

from iaglobal.models.task import Task
from iaglobal.utils.logger import get_logger
from iaglobal.agents.agent_base import AgentBase
from iaglobal.core.dependency_enforcer import dependency_enforcer

logger = get_logger("iaglobal.agents.tester_agent")

_DEFAULT_TIMEOUT = 180.0

@dataclass
class TestGenerationResult:
    success: bool
    test_code: str = ""
    error_message: Optional[str] = None
    language_detected: str = "unknown"
    execution_output: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "test_code": self.test_code,
            "error_message": self.error_message,
            "language_detected": self.language_detected,
            "execution_output": self.execution_output,
        }


class TesterAgent(AgentBase):
    __test__ = False

    def __init__(self, workdir: Optional[str] = None):
        super().__init__(agent_name="tester")
        self.history: List[Dict[str, Any]] = []
        self.workdir = workdir

    @staticmethod
    def _detect_language(code: str) -> str:
        code_lower = code.lower()
        if "def " in code or "import " in code or "pytest" in code_lower:
            return "Python (pytest)"
        if "function " in code or "const " in code or "require(" in code:
            return "JavaScript/TypeScript (Jest/Vitest)"
        if "public class " in code or "@Test" in code:
            return "Java (JUnit)"
        if "func " in code and "package " in code:
            return "Go (testing)"
        return "Desconhecida (use o framework padrao da linguagem)"

    def _extrair_funcoes_classes(self, codigo: str) -> Dict[str, List[str]]:
        funcoes = []
        classes = []
        try:
            tree = ast.parse(codigo)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    nome = node.name
                    args = [a.arg for a in node.args.args if a.arg != "self"]
                    params = ", ".join(args) if args else ""
                    funcoes.append((nome, params))
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
        except SyntaxError:
            for line in codigo.splitlines():
                line = line.strip()
                if line.startswith("def "):
                    nome = line.split("(")[0].replace("def ", "").strip()
                    params = line.split("(")[1].split(")")[0].strip()
                    funcoes.append((nome, params))
                elif line.startswith("class "):
                    nome = line.split("(")[0].replace("class ", "").strip().rstrip(":")
                    classes.append(nome)
        return {"funcoes": funcoes, "classes": classes}

    def _gerar_template_pytest(self, codigo: str) -> str:
        estrutura = self._extrair_funcoes_classes(codigo)
        linhas = [
            "import pytest",
            "import sys",
            "from pathlib import Path",
            "",
            "# Codigo sob teste",
            codigo.strip(),
            "",
        ]
        if estrutura["classes"]:
            for cls in estrutura["classes"]:
                linhas.append(f"class Test{cls}:")
                linhas.append(f"    def test_{cls.lower()}_basic(self):")
                linhas.append(f'        """Testa criacao basica de {cls}."""')
                linhas.append(f"        instance = {cls}()")
                linhas.append(f"        assert instance is not None")
                linhas.append("")
        if estrutura["funcoes"]:
            for nome, params in estrutura["funcoes"]:
                if nome.startswith("_"):
                    continue
                linhas.append(f"class Test{nome.capitalize()}:")
                if params:
                    linhas.append(f"    def test_{nome}_happy_path(self):")
                    linhas.append(f'        """Testa execucao basica de {nome}."""')
                    args = ", ".join(p.split(":")[0].split("=")[0].strip() for p in params.split(",") if p.strip())
                    if not args:
                        args = ""
                    call = f"{nome}({args})" if args else f"{nome}()"
                    linhas.append(f"        result = {call}")
                    linhas.append(f"        assert result is not None")
                else:
                    linhas.append(f"    def test_{nome}_executa(self):")
                    linhas.append(f'        """Testa que {nome} executa sem erros."""')
                    linhas.append(f"        result = {nome}()")
                    linhas.append(f"        assert result is not None")
                linhas.append("")
        if not estrutura["funcoes"] and not estrutura["classes"]:
            linhas.append("def test_basic():")
            linhas.append('    """Teste basico de sanidade."""')
            linhas.append("    assert True")
            linhas.append("")
        return "\n".join(linhas)

    async def _validar_testes_com_jedi(self, test_code: str, codigo_original: str) -> tuple[str, Dict[str, Any]]:
        try:
            from iaglobal.evolution.skills.skill_registry import skill_registry
            autocomplete_skill = skill_registry.get("python_autocomplete")
            if not autocomplete_skill:
                logger.debug("[TESTER] Skill autocomplete indisponivel")
                return test_code, {"valid": True}
            task = Task(
                objective="Validar testes",
                code=test_code,
                context={"codigo_original": codigo_original},
            )
            result = await autocomplete_skill.execute(task)
            analysis = result.get("analysis", {})
            has_errors = analysis.get("has_syntax_error", False) or len(analysis.get("issues", [])) > 0
            return test_code, {
                "valid": not has_errors,
                "issues": analysis.get("issues", []),
                "symbols": analysis.get("symbols", []),
            }
        except Exception as e:
            logger.debug("[TESTER] Validacao Jedi falhou: %s", e)
            return test_code, {"valid": True, "issues": []}

    async def _corrigir_testes_com_jedi(self, test_code: str, issues: List[Dict[str, Any]]) -> str:
        try:
            import jedi
            script = jedi.Script(code=test_code, path="test_example.py")
            try:
                script._get_module_node()
                return test_code
            except Exception:
                pass
            for issue in issues:
                msg = issue.get("message", "")
                line = issue.get("line")
                if line and ("undefined" in msg.lower() or "import" in msg.lower()):
                    lines = test_code.split("\n")
                    if 1 <= line <= len(lines):
                        line_content = lines[line - 1]
                        if line_content.strip().startswith("import "):
                            module = line_content.replace("import ", "").strip()
                            lines[line - 1] = f"# {line_content}  # modulo nao encontrado"
                            test_code = "\n".join(lines)
                            break
                elif line and "unexpected indent" in msg.lower():
                    lines = test_code.split("\n")
                    if 1 <= line <= len(lines):
                        lines[line - 1] = "    " + lines[line - 1].lstrip()
                        test_code = "\n".join(lines)
                        break
        except ImportError:
            logger.debug("[TESTER] Jedi nao instalado")
        except Exception as e:
            logger.debug("[TESTER] Correcao Jedi falhou: %s", e)
        return test_code

    async def _executar_testes(self, test_code: str, codigo_original: str) -> Dict[str, Any]:
        try:
            from iaglobal.security.sandbox_executor import SandboxExecutor
            executor = SandboxExecutor(timeout=30)
            codigo_completo = codigo_original + "\n\n" + test_code
            result = await asyncio.to_thread(executor.execute, codigo_completo)
            return {
                "sucesso": result.get("sucesso", False),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "returncode": result.get("returncode", -1),
            }
        except Exception as e:
            logger.debug("[TESTER] Execucao falhou: %s", e)
            return {"sucesso": False, "stdout": "", "stderr": str(e), "returncode": -1}

    def _extrair_erros_do_stderr(self, stderr: str) -> List[str]:
        erros = []
        for line in stderr.split("\n"):
            line = line.strip()
            if "Error" in line or "FAILED" in line or "AssertionError" in line:
                erros.append(line[:200])
            elif line.startswith("E   "):
                erros.append(line[4:200])
            elif "SyntaxError" in line or "NameError" in line or "ImportError" in line or "ModuleNotFoundError" in line:
                erros.append(line[:200])
        return erros

    async def _registrar_template_teste(self, test_code: str, task: str) -> None:
        try:
            from iaglobal.tools.tool_library import tool_library
            tags = ["test", "pytest"] + [w.lower() for w in task.split() if len(w) > 3][:3]
            tool_library.register_from_code(
                name=f"test_{hashlib.sha256(test_code.encode()).hexdigest()[:8]}",
                code=test_code,
                tags=tags,
            )
            logger.info("[EVOLUCAO] Tester registrou ToolLibrary | tags=%s", tags)
        except Exception as e:
            logger.debug("[EVOLUCAO] ToolLibrary Tester: %s", e)

    async def _avaliar_qualidade_testes(self, test_code: str) -> float:
        score = 50.0
        if not test_code:
            return 0.0
        linhas = test_code.splitlines()
        if len(linhas) >= 10:
            score += 10
        if "def test_" in test_code:
            score += 10
        if "assert " in test_code:
            score += 10
        if "import pytest" in test_code:
            score += 5
        if "class Test" in test_code:
            score += 5
        try:
            ast.parse(test_code)
            score += 10
        except SyntaxError:
            score -= 10
        return min(score, 100.0)

    async def gerar_testes(
        self,
        codigo: str,
        task: Union[str, Task],
        timeout: float = _DEFAULT_TIMEOUT,
        contexto: str = "",
    ) -> TestGenerationResult:
        logger.info("[TESTER AGENT]: Gerando testes com ferramentas locais...")

        if not codigo or not str(codigo).strip():
            return TestGenerationResult(success=False, error_message="Codigo vazio ou nulo fornecido.")

        task_text = str(task)
        if contexto:
            task_text = f"{contexto}\n\nTarefa original: {task_text}"
        lang_hint = self._detect_language(codigo)

        try:
            if lang_hint != "Python (pytest)":
                return TestGenerationResult(
                    success=False, test_code="",
                    error_message=f"Linguagem nao suportada: {lang_hint}",
                    language_detected=lang_hint,
                )

            test_code = self._gerar_template_pytest(codigo)

            if not test_code or len(test_code.strip()) < 20:
                return TestGenerationResult(
                    success=False,
                    error_message="Nao foi possivel gerar template de teste",
                    language_detected=lang_hint,
                )

            # Auto-correção: valida e repara o código de teste como compilador
            from iaglobal.core.auto_correction import auto_correction
            correcao = await asyncio.to_thread(auto_correction.corrigir, test_code, task_text)
            if correcao.foi_corrigido:
                test_code = correcao.codigo_final
                logger.info(
                    "[TESTER] Auto-correcao aplicada | issues=%d fixes=%d",
                    len(correcao.issues), len(correcao.fixes_aplicados),
                )

            # DependencyEnforcer — verifica imports contra stdlib/instalados
            enforce_result = await asyncio.to_thread(dependency_enforcer.enforce, test_code)
            if enforce_result.was_modified:
                test_code = enforce_result.modified
                logger.info(
                    "[TESTER] DependencyEnforcer aplicado | wrapped=%d unknown=%d",
                    len(enforce_result.wrapped_imports),
                    len(enforce_result.unknown_imports),
                )

            quality = await self._avaliar_qualidade_testes(test_code)
            test_code, validacao = await self._validar_testes_com_jedi(test_code, codigo)
            if not validacao.get("valid", True):
                logger.info("[TESTER] Corrigindo testes com Jedi...")
                test_code = await self._corrigir_testes_com_jedi(test_code, validacao.get("issues", []))

            result_exec = {"sucesso": False, "stdout": "", "stderr": ""}
            try:
                result_exec = await asyncio.wait_for(
                    self._executar_testes(test_code, codigo),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                result_exec = {"sucesso": False, "stdout": "", "stderr": "Timeout na execucao dos testes"}

            if not result_exec.get("sucesso", False):
                stderr = result_exec.get("stderr", "")
                if stderr:
                    erros = self._extrair_erros_do_stderr(stderr)
                    logger.info("[TESTER] Execucao falhou: %d erros detectados", len(erros))
                    test_code, _ = await self._validar_testes_com_jedi(test_code, codigo)
                    retry = await asyncio.wait_for(
                        self._executar_testes(test_code, codigo),
                        timeout=timeout,
                    )
                    if retry.get("sucesso", False):
                        result_exec = retry

            success = result_exec.get("sucesso", False) or result_exec.get("returncode") == 0
            exec_output = result_exec.get("stdout", "") or result_exec.get("stderr", "")

            result = TestGenerationResult(
                success=success,
                test_code=test_code,
                error_message=None if success else exec_output[:500],
                language_detected=lang_hint,
                execution_output=exec_output[:500],
            )

            # Evolucao: registra template de teste bem-sucedido no SkillRegistry
            if success:
                await self._registrar_template_teste(test_code, task_text)

            self.history.append(result.to_dict())
            logger.info(
                "[TESTER AGENT]: Testes gerados (%d chars, score=%.2f, success=%s)",
                len(test_code), quality, success,
            )
            return result

        except asyncio.TimeoutError:
            return TestGenerationResult(
                success=False, error_message=f"Timeout apos {timeout}s",
                language_detected=lang_hint,
            )
        except Exception as e:
            err_msg = f"Erro inesperado: {str(e)}"
            logger.warning("[TESTER AGENT]: %s", err_msg, exc_info=True)
            return TestGenerationResult(success=False, error_message=err_msg, language_detected=lang_hint)
