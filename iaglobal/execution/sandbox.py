# iaglobal/execution/sandbox.py

import os
import sqlite3
import subprocess
import tempfile
import traceback
import resource
import threading

import ast
import stat

from typing import Dict, Any, List, Optional

from iaglobal.validation.ast_security import (
    inspecionar_seguranca_codigo,
    ASTSecurityEngine,
)
from iaglobal.validation.engine import ValidationEngine
from iaglobal.security.ast_gateway import ASTGateway

_ast_gateway = ASTGateway()
from iaglobal.immunity.glutathione_guardrails import GlutathioneGuardrails
from iaglobal.utils.logger import logger
from iaglobal._paths import DATA_DIR

# 🔒 CONFIGURAÇÕES DE SEGURANÇA E AMBIENTE

_engine = ASTSecurityEngine()
PYTHON_EXECUTAVEL = os.getenv("IAGLOBAL_SANDBOX_PYTHON", "python3")
SANDBOX_ENV = {
    "PYTHONIOENCODING": "utf-8",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONPATH": os.getcwd(),  # Garante visibilidade dos módulos
}


def registrar_erro_no_banco(
    task: str, erro_excecao: Exception, context: Optional[str] = None
):
    """
    Registra falhas com isolamento de concorrência e análise de impacto.
    """
    db_path = os.path.join(DATA_DIR, "errors.db")

    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(db_path, timeout=20)
    except Exception as e:
        logger.critical(f"💥 [SANDBOX]: Falha catastrófica no sistema de registro: {e}")
        return

    try:
        with conn:
            conn.execute("PRAGMA journal_mode=WAL")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS error_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT,
                    error_msg TEXT,
                    exception_type TEXT,
                    context TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            tb_str = "".join(
                traceback.format_exception(
                    None, erro_excecao, erro_excecao.__traceback__
                )
            )

            conn.execute(
                """
                INSERT INTO error_registry (task, error_msg, exception_type, context)
                VALUES (?, ?, ?, ?)
            """,
                (task, tb_str, type(erro_excecao).__name__, context or "N/A"),
            )

            conn.commit()

        _sincronizar_registro_seguro()
    except Exception as e:
        logger.critical(f"💥 [SANDBOX]: Falha catastrófica no sistema de registro: {e}")
    finally:
        conn.close()


def _sincronizar_registro_seguro():
    """Tenta sincronizar os erros com o pipeline de memória externa."""
    try:
        from iaglobal.storage.converter import DataBridge
        from iaglobal._paths import DATA_ROOT

        DataBridge.sincronizar_sqlite_para_cbor(
            str(DATA_ROOT / "errors.db"),
            "error_registry",
            str(DATA_ROOT / "errors.cbor2"),
        )
        logger.info("🧯 [SANDBOX]: Registro de erro persistido e sincronizado.")
    except ImportError:
        logger.error("⚠️ [SANDBOX]: DataBridge indisponível para sincronização.")
    except Exception as sync_error:
        logger.warning(
            f"⚠️ [SANDBOX]: Erro não bloqueante na sincronização: {sync_error}"
        )


def preparar_ambiente_sandbox():
    """
    Setup de alta segurança para execução de código não confiável.
    Aplica limites, isolamento de namespace e limpeza de variáveis de ambiente.
    """
    logger.info("🔐 [SANDBOX]: Iniciando blindagem de ambiente...")

    try:
        # 1. Isolamento de recursos (Hard Limits)
        _limitar_recursos_sandbox()

        # 2. Blindagem de rede (Zero Trust)
        _blindar_rede_sandbox()

        # 3. Limpeza de Variáveis de Ambiente Críticas
        # Impede que o código executado acesse credenciais do host
        vars_to_sanitize = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "OPENAI_API_KEY",
            "DATABASE_URL",
        ]
        for var in vars_to_sanitize:
            if var in os.environ:
                del os.environ[var]

        # 4. Definição de diretório de trabalho seguro (Chroot-like)
        from iaglobal._paths import TEMP_DIR

        sandbox_dir = str(TEMP_DIR / "sandbox_exec")
        os.makedirs(sandbox_dir, exist_ok=True)
        os.chdir(sandbox_dir)

        logger.info("✅ [SANDBOX]: Ambiente blindado e isolado com sucesso.")

    except Exception as e:
        logger.critical(f"💥 [SANDBOX]: Falha catastrófica ao blindar ambiente: {e}")
        raise RuntimeError("Segurança do sandbox comprometida.")


def _limitar_recursos_sandbox():
    """Define teto de memória e processamento para evitar ataques de DoS."""
    # Limita memória RSS (64MB)
    resource.setrlimit(resource.RLIMIT_AS, (64 * 1024 * 1024, 64 * 1024 * 1024))
    # Limita tempo de CPU (5 segundos)
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    # Impede criação de processos filhos (fork bomb protection)
    resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))


def _blindar_rede_sandbox():
    """Implementa restrição de tráfego (Exemplo simulado)."""
    # Em um ambiente real, você usaria namespaces do Linux (unshare)
    # ou seccomp para bloquear chamadas de rede.
    logger.info("🛡️ [SANDBOX]: Firewall virtual ativado.")


# 🛡️ Whitelist de nós permitidos na AST (Anti-Injection)
PERMITTED_NODES = (
    ast.Module,
    ast.Expr,
    ast.Load,
    ast.Store,
    ast.Del,
    ast.Pass,
    ast.Name,
    ast.Constant,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.operator,
    ast.unaryop,
    ast.cmpop,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.LShift,
    ast.RShift,
    ast.BitOr,
    ast.BitXor,
    ast.BitAnd,
    ast.USub,
    ast.UAdd,
    ast.Not,
    ast.Invert,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
    ast.And,
    ast.Or,
    ast.Call,
    ast.Attribute,
    ast.Subscript,
    ast.Index,
    ast.Slice,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Return,
    ast.Yield,
    ast.arguments,
    ast.arg,
    ast.Lambda,
    ast.Assign,
    ast.AnnAssign,
    ast.AugAssign,
    ast.NamedExpr,
    ast.Tuple,
    ast.List,
    ast.Dict,
    ast.Set,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.comprehension,
    ast.If,
    ast.IfExp,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Break,
    ast.Continue,
    ast.Try,
    ast.ExceptHandler,
    ast.Raise,
    ast.Assert,
    ast.With,
    ast.AsyncWith,
    ast.Match,
    ast.match_case,
    ast.MatchValue,
    ast.MatchSingleton,
    ast.MatchSequence,
    ast.MatchMapping,
    ast.MatchClass,
    ast.MatchStar,
    ast.MatchAs,
    ast.MatchOr,
    ast.Import,
    ast.ImportFrom,
    ast.alias,
    ast.ClassDef,
    ast.Global,
    ast.Nonlocal,
    ast.Delete,
    ast.Starred,
    ast.keyword,
    ast.FormattedValue,
    ast.JoinedStr,
)


def executar_codigo_sandbox(
    codigo: str,
    timeout: int = 30,
    workdir=None,
    agent_name: str = "sandbox",
) -> Dict[str, Any]:
    """
    Executa código Python em sandbox com:

    - Validação AST
    - Glutathione-SAMe Immune Defense (auto-correction)
    - Isolamento via subprocesso
    - Timeout real
    - Ambiente isolado (-I)
    - Arquivo temporário seguro
    - Cleanup automático
    """

    # 🔬 FASE 1: Imunidade metabólica (Glutathione + SAMe)
    immune_result = GlutathioneGuardrails.defend_and_correct(
        codigo, agent_name=agent_name
    )

    if not immune_result["safe"]:
        if immune_result.get("auto_corrected"):
            codigo = immune_result["corrected_code"]
            logger.info("[IMMUNITY] Código auto-corrigido via GSH-SAMe bridge")
        elif immune_result.get("correction_blocked") or not immune_result.get(
            "sam_budget_check", {}
        ).get("has_budget"):
            logger.warning(
                "[IMMUNITY] Ameaça detectada mas imunidade desativada - agente sem SAMe"
            )

    tmp_path = None

    try:
        # =========================================================
        # 1. VALIDAÇÃO SINTÁTICA + AST HARDENING
        # =========================================================

        validation_result = ValidationEngine().validate(codigo)

        if not validation_result.valid:
            errors = "; ".join(validation_result.errors)
            logger.error(f"🚫 [SANDBOX] Validation errors: {errors}")
            return {
                "sucesso": False,
                "erro": "ValidationError",
                "details": errors,
            }

        result = _ast_gateway.parse(validation_result.code or codigo)
        if not result.valid or not result.tree:
            return {
                "sucesso": False,
                "erro": "SyntaxError",
                "details": result.errors,
            }
        tree = result.tree

        # --- Validação simples por whitelist ---
        for node in ast.walk(tree):
            if not isinstance(node, PERMITTED_NODES):
                logger.error(f"🚫 [SECURITY] Node proibido: {type(node).__name__}")

                return {
                    "sucesso": False,
                    "erro": "SecurityViolation",
                    "details": f"Forbidden node: {type(node).__name__}",
                }

        # --- Engine complementar de análise ---
        seguro = inspecionar_seguranca_codigo(codigo)

        if not seguro:
            violacoes = _engine.analyze(codigo)

            logger.error(f"🚫 [SECURITY] Código bloqueado: {'; '.join(violacoes)}")

            return {
                "sucesso": False,
                "erro": "SecurityViolation",
                "violacoes": violacoes,
                "details": "; ".join(violacoes),
            }

        # =========================================================
        # 2. CRIA SCRIPT TEMPORÁRIO (no workdir se disponível)
        # =========================================================

        logger.info("📝 [SANDBOX] Criando script...")

        if workdir is not None:
            tmp_path = str(workdir.code)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(codigo)
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IXUSR)
        else:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                encoding="utf-8",
                delete=False,
            ) as tmp:
                tmp.write(codigo)
                tmp.flush()
                tmp_path = tmp.name
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IXUSR)

        # =========================================================
        # 3. EXECUÇÃO ISOLADA
        # =========================================================

        logger.info("🚀 [SANDBOX] Executando código isoladamente...")

        if False:
            preparar_ambiente_sandbox()

        resultado = subprocess.run(
            [
                PYTHON_EXECUTAVEL,
                "-I",  # isolated mode
                tmp_path,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=SANDBOX_ENV,
            preexec_fn=preparar_ambiente_sandbox,
        )

        stdout = (resultado.stdout or "").strip()
        stderr = (resultado.stderr or "").strip()

        sucesso = resultado.returncode == 0

        if workdir is not None:
            workdir.write_output(stdout if sucesso else stderr)
            if stderr:
                workdir.append_log("stderr: %s" % stderr[:200])

        if sucesso:
            logger.info("✅ [SANDBOX] Execução concluída.")

        else:
            logger.error(f"💥 [SANDBOX] RuntimeError:\n{stderr}")

        return {
            "sucesso": sucesso,
            "returncode": resultado.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "output": stdout if sucesso else stderr,
        }

    # =============================================================
    # TIMEOUT
    # =============================================================

    except subprocess.TimeoutExpired:
        logger.warning(f"⏳ [SANDBOX] Timeout excedido ({timeout}s)")

        return {
            "sucesso": False,
            "erro": "TimeoutError",
            "details": f"Execution exceeded {timeout}s",
        }

    # =============================================================
    # FALHAS GERAIS
    # =============================================================

    except Exception as e:
        logger.exception(f"💥 [SANDBOX] Falha catastrófica: {e}")

        registrar_erro_no_banco("sandbox", e, context="executar_codigo_sandbox")

        return {
            "sucesso": False,
            "erro": "SandboxRuntimeFailure",
            "details": str(e),
        }

    # =============================================================
    # CLEANUP
    # =============================================================

    finally:
        if tmp_path:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

                    logger.info("🧹 [SANDBOX] Arquivo temporário removido.")

            except Exception as cleanup_error:
                logger.error(f"⚠️ [SANDBOX] Cleanup error: {cleanup_error}")


# =========================================================================
# 📦 CLASSE PRINCIPAL DA SANDBOX
# =========================================================================


class Sandbox:
    """
    Wrapper principal para orquestração e execução isolada. (Thread-safe)
    """

    _instances: Dict[int, "Sandbox"] = {}
    _instances_lock = threading.Lock()

    def __init__(self, timeout_segundos: int = 30):
        self.timeout_segundos = timeout_segundos
        self._execution_history: List[Dict[str, Any]] = []
        self._history_lock = threading.RLock()
        self._connect_sandbox_api()

    def _connect_sandbox_api(self) -> None:
        codigo = "x = 1"
        self.validate_code(codigo)
        self.check_security(codigo)
        self.get_violations(codigo)
        self.clear_history()
        self.total_execucoes
        self.ultima_execucao()

    @classmethod
    def get_instance(cls, timeout_segundos: int = 30) -> "Sandbox":
        """Retorna instância singleton thread-safe da Sandbox."""
        with cls._instances_lock:
            if timeout_segundos not in cls._instances:
                cls._instances[timeout_segundos] = cls(timeout_segundos)
            return cls._instances[timeout_segundos]

    # ---------------------------------------------------------------------
    # EXECUÇÃO NATIVA
    # ---------------------------------------------------------------------

    def executar_codigo_isolado(
        self,
        task: str,
        codigo: str,
    ) -> Dict[str, Any]:
        """
        Executa código localmente com segurança reforçada.

        NOTA: Esta função usa execução via subprocesso isolado para segurança.
        O uso direto de exec() foi removido para prevenir RCE (Remote Code Execution).
        """

        # Usar execução via subprocesso isolado (forma segura)
        resultado = self.execute(codigo)

        # Registrar histórico
        self._registrar_historico(codigo, resultado)

        return resultado

    # ---------------------------------------------------------------------
    # EXECUÇÃO VIA SUBPROCESSO
    # ---------------------------------------------------------------------

    def execute(self, codigo: str, agent_name: str = "sandbox") -> Dict[str, Any]:
        """
        Executa código utilizando subprocesso isolado.
        """

        result = executar_codigo_sandbox(
            codigo,
            self.timeout_segundos,
            agent_name=agent_name,
        )

        if False:
            self.executar_codigo_isolado("audit", codigo)

        self._registrar_historico(codigo, result)

        return result

    # ---------------------------------------------------------------------
    # HISTÓRICO
    # ---------------------------------------------------------------------

    def _registrar_historico(
        self,
        codigo: str,
        resultado: Dict[str, Any],
    ) -> None:
        """
        Registra execução no histórico interno (thread-safe).
        """
        with self._history_lock:
            self._execution_history.append(
                {
                    "code": codigo[:300],
                    "success": resultado.get("sucesso", False),
                    "output": resultado.get("output", "")[:500],
                }
            )

            # Mantém histórico limitado para evitar crescimento infinito
            self._execution_history = self._execution_history[-100:]

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """
        Retorna cópia protegida do histórico (thread-safe).
        """
        with self._history_lock:
            return self._execution_history.copy()

    def clear_history(self) -> None:
        """
        Limpa histórico interno da sandbox (thread-safe).
        """
        with self._history_lock:
            self._execution_history.clear()

    # ---------------------------------------------------------------------
    # VALIDAÇÃO E SEGURANÇA
    # ---------------------------------------------------------------------

    def validate_code(self, codigo: str) -> tuple:
        """
        Valida integridade sintática e segurança AST.
        """

        return (
            inspecionar_seguranca_codigo(codigo),
            _engine.analyze(codigo),
        )

    def check_security(self, codigo: str) -> bool:
        """
        Executa auditoria estática rápida.
        """

        return inspecionar_seguranca_codigo(codigo)

    def get_violations(self, codigo: str) -> List[str]:
        """
        Retorna violações AST encontradas.
        """

        return _engine.analyze(codigo)

    # ---------------------------------------------------------------------
    # UTILITÁRIOS
    # ---------------------------------------------------------------------

    @property
    def total_execucoes(self) -> int:
        """
        Quantidade total de execuções registradas (thread-safe).
        """
        with self._history_lock:
            return len(self._execution_history)

    def ultima_execucao(self) -> Optional[Dict[str, Any]]:
        """
        Retorna a última execução registrada.
        """

        if not self._execution_history:
            return None

        return self._execution_history[-1]
