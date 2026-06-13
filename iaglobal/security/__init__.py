import logging
from typing import Optional
from .ast_gateway import ASTGateway, ASTResult
from .network_guard import NetworkGuard
from .resource_limits import ResourceLimiter, limitar_recursos_sandbox
from .sandbox_rules import SandboxRules
from .sandbox_executor import SandboxExecutor

logger = logging.getLogger("ia-global")


class SecurityEngine:
    """Motor de seguranca unificado.

    Integra:
    - SandboxRules (modulos, paths, env, operacoes)
    - ASTGateway (parse + validacao)
    - NetworkGuard (isolamento de rede)
    - ResourceLimiter (RAM, CPU, fork)
    - SandboxExecutor (subprocesso isolado)
    """

    def __init__(self):
        self.rules = SandboxRules()
        self.ast = ASTGateway(sandbox_rules=self.rules)
        self.net = NetworkGuard(allow_network=False)
        self.res = ResourceLimiter()
        self.executor = SandboxExecutor(ast_gateway=self.ast, sandbox_rules=self.rules)
        logger.info("[SECURITY] SecurityEngine inicializada")
        logger.info("[SECURITY] %d modulos permitidos, %d paths leitura, %d paths escrita",
                    len(self.rules.allowed_modules), len(self.rules.allowed_read_paths),
                    len(self.rules.allowed_write_paths))

    def validate_and_prepare(self, code: str):
        ast_result = self.ast.parse(code)
        if not ast_result.valid:
            logger.warning("[SECURITY] Validacao falhou: %s", ast_result.errors)
            return False, ast_result.errors
        return True, []

    def execute(self, code: str, workdir: Optional[str] = None):
        logger.info("[SECURITY] Executando codigo em sandbox (workdir=%s)", workdir or "/tmp")
        return self.executor.execute(code, workdir=workdir)

    def get_config_snapshot(self) -> dict:
        return {
            "rules": self.rules.get_config_snapshot(),
            "timeout": self.executor.timeout,
            "python_exec": self.executor.python_exec,
            "execution_count": self.executor._execution_count,
        }
