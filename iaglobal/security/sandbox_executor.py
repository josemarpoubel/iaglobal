"""SandboxExecutor: isolated subprocess execution with resource & network lockdown."""

import subprocess
import tempfile
import os
import stat
import shutil
import sys
from typing import Dict, Any, Optional

from iaglobal.security.resource_limits import limitar_recursos_sandbox, ResourceLimiter
from iaglobal.security.network_guard import blindar_rede_sandbox, NetworkGuard
from iaglobal.security.ast_gateway import ASTGateway
from iaglobal.security.sandbox_rules import SandboxRules
from iaglobal.utils.logger import logger


def _sandbox_preexec():
    """Apply resource limits AND network isolation before code runs."""
    limitar_recursos_sandbox()
    blindar_rede_sandbox()


class SandboxExecutor:
    """Executes Python code in an isolated subprocess with full sandbox guards.

    Camadas de seguranca aplicadas:
    1. AST Gateway (imports + sintaxe)
    2. SandboxRules (path whitelist, env sanitization, operacoes)
    3. ResourceLimiter (RAM, CPU, fork)
    4. NetworkGuard (socket bloqueado)
    5. Subprocesso isolado com preexec_fn
    """

    def __init__(
        self,
        timeout: int = 30,
        python_exec: str = "python3",
        ast_gateway: Optional[ASTGateway] = None,
        sandbox_rules: Optional[SandboxRules] = None,
    ):
        self.timeout = timeout
        self.python_exec = python_exec
        self.rules = sandbox_rules or SandboxRules()
        self.gateway = ast_gateway or ASTGateway(sandbox_rules=self.rules)
        self.resource_limiter = ResourceLimiter()
        self.network_guard = NetworkGuard()
        self._execution_count = 0

    def execute(self, code: str, workdir: Optional[str] = None) -> Dict[str, Any]:
        """Validate via AST + SandboxRules, then run in isolated subprocess.

        Args:
            code: Codigo Python para executar
            workdir: Diretorio de trabalho (opcional, para salvar output)

        Returns:
            Dict com resultado da execucao
        """
        if not code or not code.strip():
            return {"sucesso": False, "erro": "EmptyCode", "details": "No code provided"}

        if not self.rules.is_enabled():
            logger.warning("[SANDBOX] Execucao com regras desativadas — modo inseguro!")

        # ── 1. AST validation (imports + sintaxe) ──
        ast_result = self.gateway.parse(code)
        if not ast_result.valid:
            logger.warning("[SANDBOX] AST bloqueou execucao: %s", ast_result.errors)
            return {
                "sucesso": False,
                "erro": "SecurityViolation",
                "details": "; ".join(ast_result.errors),
                "violacoes": ast_result.errors,
            }

        # ── 1b. GlutathioneGuardrails (padrões perigosos adicionais) ──
        from iaglobal.immunity.glutathione_guardrails import GlutathioneGuardrails
        guardrail = GlutathioneGuardrails.validate(code)
        if not guardrail["safe"]:
            logger.warning("[SANDBOX] Glutathione bloqueou execucao: %s", guardrail["issues"])
            return {
                "sucesso": False,
                "erro": "GlutathioneViolation",
                "details": "; ".join(i["message"] for i in guardrail["issues"]),
                "violacoes": guardrail["issues"],
            }

        self._execution_count += 1

        # ── 2. Verifica path do workdir contra as regras ──
        from iaglobal._paths import TEMP_DIR
        sandbox_dir = str(TEMP_DIR / "sandbox_exec")
        if not self.rules.is_path_allowed_for_write(sandbox_dir):
            logger.warning("[SANDBOX] Path '%s' nao permitido — criando em /tmp", sandbox_dir)
            sandbox_dir = "/tmp"

        os.makedirs(sandbox_dir, exist_ok=True)

        # ── 3. Cria arquivo temporario no sandbox_dir ──
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(
                suffix=".py", prefix="sandbox_", dir=sandbox_dir
            )
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                tmp.write(code)
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IXUSR)

            # ── 4. Prepara ambiente sanitizado ──
            env = self.rules.sanitize_environment(os.environ.copy())
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["SANDBOX_EXECUTION"] = "1"
            env["SANDBOX_ID"] = str(self._execution_count)

            logger.info("[SANDBOX] Executando codigo em subprocesso isolado (exec #%d)...",
                        self._execution_count)
            logger.debug("[SANDBOX] Regras ativas: %d modulos, %d paths leitura, %d paths escrita",
                         len(self.rules.allowed_modules), len(self.rules.allowed_read_paths),
                         len(self.rules.allowed_write_paths))

            result = subprocess.run(
                [self.python_exec, "-I", tmp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                preexec_fn=_sandbox_preexec,
                cwd=sandbox_dir,
            )

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            sucesso = result.returncode == 0

            # Auto-install: se falhou por ImportError, instala e tenta de novo
            if not sucesso and "ModuleNotFoundError" in stderr:
                import re
                match = re.search(r"ModuleNotFoundError: No module named '(\w+)'", stderr)
                if match:
                    lib = match.group(1)
                    logger.info("[SANDBOX] ImportError: '%s' não encontrado — instalando...", lib)
                    try:
                        subprocess.run(
                            [sys.executable, "-m", "pip", "install", lib],
                            capture_output=True, text=True, timeout=30,
                        )
                        result = subprocess.run(
                            [self.python_exec, "-I", tmp_path],
                            capture_output=True, text=True,
                            timeout=self.timeout, env=env,
                            preexec_fn=_sandbox_preexec, cwd=sandbox_dir,
                        )
                        stdout = (result.stdout or "").strip()
                        stderr = (result.stderr or "").strip()
                        sucesso = result.returncode == 0
                        if sucesso:
                            logger.info("[SANDBOX] ✅ Auto-install de '%s' OK — reexecução sucedida", lib)
                        else:
                            logger.warning("[SANDBOX] Auto-install de '%s' falhou — erro persiste", lib)
                    except Exception as e:
                        logger.warning("[SANDBOX] Auto-install de '%s' exceção: %s", lib, e)

            logger.info("[SANDBOX] Execucao #%d: returncode=%d | stdout=%d chars | stderr=%d chars",
                        self._execution_count, result.returncode, len(stdout), len(stderr))

            return {
                "sucesso": sucesso,
                "returncode": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "output": stdout if sucesso else stderr,
                "execution_id": self._execution_count,
            }

        except subprocess.TimeoutExpired:
            logger.warning("[SANDBOX] Timeout (%ds) na execucao #%d", self.timeout, self._execution_count)
            return {
                "sucesso": False,
                "erro": "TimeoutError",
                "details": f"Execution exceeded {self.timeout}s",
            }
        except PermissionError as e:
            logger.error("[SANDBOX] Erro de permissao: %s", e)
            return {"sucesso": False, "erro": "PermissionDenied", "details": str(e)}
        except Exception as e:
            logger.exception("[SANDBOX] Falha na execucao: %s", e)
            return {
                "sucesso": False,
                "erro": "SandboxRuntimeFailure",
                "details": str(e),
            }
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def validate(self, code: str) -> Dict[str, Any]:
        """Only run AST validation, no execution."""
        ast_result = self.gateway.parse(code)
        return {
            "valid": ast_result.valid,
            "errors": ast_result.errors,
        }

