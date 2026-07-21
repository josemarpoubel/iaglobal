# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
CodeExecutorTool — Execução isolada de código em subprocesso com timeout.

Registrada automaticamente na ToolLibrary para que agentes possam
executar código via _resolve_with_tools() — usada principalmente pelo
debugger para testar hipóteses sem depender de LLM.
"""

import os
import subprocess
import sys
import tempfile
import textwrap
import time

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.tools.code_executor")

BLOCKED_IMPORTS = {
    "os.system",
    "os.popen",
    "subprocess",
    "shutil.rmtree",
    "shutil.copytree",
    "pathlib.Path.unlink",
    "__import__",
    "eval",
    "exec",
    "compile",
}
BLOCKED_KEYWORDS = {"__import__", "eval(", "exec(", "compile("}


def _has_blocked_code(code: str) -> bool:
    code_lower = code.lower()
    for keyword in BLOCKED_KEYWORDS:
        if keyword in code_lower:
            return True
    for blocked in BLOCKED_IMPORTS:
        if blocked in code_lower:
            return True
    return False


def execute_code(code: str, language: str = "python", timeout: int = 30) -> str:
    if not code or not code.strip():
        return ""

    lang = language.lower()

    if lang == "python":
        if _has_blocked_code(code):
            return "[CodeExecutor] Códulo bloqueado por segurança: uso de eval/exec/__import__ não permitido."

        wrapped = textwrap.dedent(f"""
import sys, io
try:
    _old_stdout = sys.stdout
    sys.stdout = _buf = io.StringIO()
    exec({code!r}, {{"__builtins__": __builtins__}})
    sys.stdout = _old_stdout
    result = _buf.getvalue()
    if result.strip():
        print(result)
except Exception as e:
    sys.stdout = _old_stdout
    print(f"<Error: {{type(e).__name__}}: {{e}}>")
""")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", prefix="iaglobal_exec_", delete=False
        ) as f:
            f.write(wrapped)
            tmp_path = f.name

        try:
            start = time.time()
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            elapsed = time.time() - start

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            rc = result.returncode

            output_parts = []
            if stdout:
                output_parts.append(stdout)
            if stderr:
                output_parts.append(f"[stderr] {stderr}")
            if rc != 0:
                output_parts.append(f"[exit code: {rc}]")

            output = "\n".join(output_parts) if output_parts else ""
            logger.info(
                "[CodeExecutor] Python OK (%d chars, %.2fs, rc=%d)",
                len(code),
                elapsed,
                rc,
            )
            return output
        except subprocess.TimeoutExpired:
            logger.warning("[CodeExecutor] Timeout (%ds) execução Python", timeout)
            return f"[Timeout] Execução excedeu {timeout}s"
        except Exception as e:
            logger.warning("[CodeExecutor] Erro: %s", e)
            return f"[Error] {e}"
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    elif lang == "bash":
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", prefix="iaglobal_exec_", delete=False
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            os.chmod(tmp_path, 0o700)
            start = time.time()
            result = subprocess.run(
                ["bash", tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.time() - start

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            rc = result.returncode

            output_parts = []
            if stdout:
                output_parts.append(stdout)
            if stderr:
                output_parts.append(f"[stderr] {stderr}")
            if rc != 0:
                output_parts.append(f"[exit code: {rc}]")

            output = "\n".join(output_parts) if output_parts else ""
            logger.info(
                "[CodeExecutor] Bash OK (%d chars, %.2fs, rc=%d)",
                len(code),
                elapsed,
                rc,
            )
            return output
        except subprocess.TimeoutExpired:
            logger.warning("[CodeExecutor] Timeout (%ds) execução Bash", timeout)
            return f"[Timeout] Execução excedeu {timeout}s"
        except Exception as e:
            logger.warning("[CodeExecutor] Erro: %s", e)
            return f"[Error] {e}"
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    else:
        return f"[CodeExecutor] Linguagem '{language}' não suportada. Use 'python' ou 'bash'."


# Registra na ToolLibrary no momento da importação
from iaglobal.tools.tool_library import tool_library

tool_library.register(
    name="code_executor",
    fn=execute_code,
    tags=["code", "executor", "python", "bash", "run", "test", "debug"],
    description="Executa código Python ou Bash em subprocesso isolado com timeout. Parâmetros: code (str), language (str='python'), timeout (int=30). Retorna stdout/stderr.",
)
