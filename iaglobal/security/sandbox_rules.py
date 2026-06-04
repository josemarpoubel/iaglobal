"""Sandbox rules enforcement for secure code execution."""

import os
import sys
import logging
from typing import Set, Optional, List, Dict

logger = logging.getLogger("ia-global")


class SandboxRules:
    """Defines and enforces sandbox rules for code execution.

    Camadas de protecao:
    1. Modulos permitidos (whitelist de imports)
    2. Paths permitidos para leitura/escrita
    3. Operacoes bloqueadas
    4. Limites de recursos
    5. Sanitizacao de variaveis de ambiente
    6. Isolamento de filesystem
    """

    # ─────────────────────────────────────────────
    # DEFAULTS
    # ─────────────────────────────────────────────

    DEFAULT_ALLOWED_MODULES: Set[str] = {
        "math", "json", "collections", "itertools", "functools",
        "random", "datetime", "typing", "re", "string",
        "decimal", "fractions", "statistics", "uuid",
        "hashlib", "base64", "binascii",
        "textwrap", "pprint", "enum",
        "dataclasses", "abc", "copy",
        "operator", "bisect", "heapq",
        "array", "struct", "time",
        "django", "flask", "fastapi", "tkinter",
    }

    DEFAULT_ALLOWED_READ_PATHS: Set[str] = {
        "/tmp", "/dev/null", "/proc/self/fd/1", "/proc/self/fd/2",
    }

    DEFAULT_ALLOWED_WRITE_PATHS: Set[str] = {
        "/tmp",
    }

    DEFAULT_BLOCKED_PATHS: Set[str] = {
        "/etc", "/boot", "/root", "/home", "/var/log",
        "/proc/1", "/sys", "/dev/sda",
    }

    BLOCKED_ENV_VARS: Set[str] = {
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
        "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID",
        "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "GITHUB_TOKEN", "GITLAB_TOKEN", "DOCKER_HOST",
        "KUBERNETES_SERVICE_HOST", "KUBERNETES_SERVICE_PORT",
        "PGPASSWORD", "MYSQL_PASSWORD", "REDIS_PASSWORD",
        "SSH_KEY", "SECRET_KEY", "PRIVATE_KEY",
        "TOKEN", "PASSWORD", "SECRET",
    }

    DANGEROUS_OS_FUNCTIONS: Set[str] = {
        "system", "popen", "fork", "execv", "execl", "execve",
        "execlp", "execvp", "execle", "execvpe",
        "spawnl", "spawnle", "spawnlp", "spawnlpe",
        "spawnv", "spawnve", "spawnvp", "spawnvpe",
        "posix_spawn", "posix_spawnp",
    }

    DANGEROUS_SUBPROCESS_ATTRS: Set[str] = {
        "Popen", "call", "run", "check_call", "check_output",
        "getoutput", "getstatusoutput",
    }

    def __init__(self):
        self.allowed_modules: Set[str] = set(self.DEFAULT_ALLOWED_MODULES)
        self.allowed_read_paths: Set[str] = set(self.DEFAULT_ALLOWED_READ_PATHS)
        self.allowed_write_paths: Set[str] = set(self.DEFAULT_ALLOWED_WRITE_PATHS)
        self.blocked_paths: Set[str] = set(self.DEFAULT_BLOCKED_PATHS)
        self.blocked_operations: Set[str] = set()
        self.resource_limits: Dict[str, int] = {}
        self.blocked_env_vars: Set[str] = set(self.BLOCKED_ENV_VARS)
        self._enabled = True
        self._stats = {"modules_checked": 0, "paths_checked": 0, "ops_blocked": 0}

    # ─────────────────────────────────────────────
    # MODULE WHITELIST
    # ─────────────────────────────────────────────

    def is_module_allowed(self, module_name: str) -> bool:
        self._stats["modules_checked"] += 1
        base = module_name.split(".")[0]
        if base not in self.allowed_modules:
            logger.warning("[SANDBOX-RULES] Modulo bloqueado: '%s' (base='%s')", module_name, base)
            return False
        return True

    def add_allowed_module(self, module_name: str) -> None:
        self.allowed_modules.add(module_name)
        logger.info("[SANDBOX-RULES] Modulo permitido adicionado: %s", module_name)

    def remove_allowed_module(self, module_name: str) -> None:
        self.allowed_modules.discard(module_name)
        logger.info("[SANDBOX-RULES] Modulo permitido removido: %s", module_name)

    # ─────────────────────────────────────────────
    # FILESYSTEM ISOLATION (path whitelist)
    # ─────────────────────────────────────────────

    def is_path_allowed_for_read(self, path: str) -> bool:
        """Verifica se um path pode ser lido."""
        self._stats["paths_checked"] += 1
        abs_path = os.path.abspath(path)

        for blocked in self.blocked_paths:
            if abs_path.startswith(blocked):
                logger.warning("[SANDBOX-RULES] Path bloqueado para leitura: %s", abs_path)
                return False

        for allowed in self.allowed_read_paths:
            if abs_path.startswith(allowed):
                return True

        if abs_path.startswith("/proc/self"):
            return True

        logger.warning("[SANDBOX-RULES] Path nao permitido para leitura: %s", abs_path)
        return False

    def is_path_allowed_for_write(self, path: str) -> bool:
        """Verifica se um path pode ser escrito."""
        self._stats["paths_checked"] += 1
        abs_path = os.path.abspath(path)

        for blocked in self.blocked_paths:
            if abs_path.startswith(blocked):
                logger.warning("[SANDBOX-RULES] Path bloqueado para escrita: %s", abs_path)
                return False

        for allowed in self.allowed_write_paths:
            if abs_path.startswith(allowed):
                return True

        logger.warning("[SANDBOX-RULES] Path nao permitido para escrita: %s", abs_path)
        return False

    def add_allowed_read_path(self, path: str) -> None:
        self.allowed_read_paths.add(os.path.abspath(path))
        logger.info("[SANDBOX-RULES] Path de leitura permitido: %s", path)

    def add_allowed_write_path(self, path: str) -> None:
        self.allowed_write_paths.add(os.path.abspath(path))
        logger.info("[SANDBOX-RULES] Path de escrita permitido: %s", path)

    def block_path(self, path: str) -> None:
        self.blocked_paths.add(os.path.abspath(path))
        logger.info("[SANDBOX-RULES] Path bloqueado: %s", path)

    # ─────────────────────────────────────────────
    # ENVIRONMENT SANITIZATION
    # ─────────────────────────────────────────────

    def sanitize_environment(self, env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Remove variaveis de ambiente sensiveis.
        Se env for None, usa os.environ.
        """
        target = dict(env or os.environ)
        removed = []
        for var in list(target.keys()):
            upper = var.upper()
            for blocked in self.blocked_env_vars:
                if blocked in upper:
                    removed.append(var)
                    del target[var]
                    break

        if removed:
            logger.info("[SANDBOX-RULES] Variaveis de ambiente sanitizadas: %d removidas", len(removed))
            for v in removed:
                logger.debug("[SANDBOX-RULES]   - %s", v)

        return target

    def add_blocked_env_var(self, var_name: str) -> None:
        self.blocked_env_vars.add(var_name.upper())

    # ─────────────────────────────────────────────
    # OPERATION BLOCKING
    # ─────────────────────────────────────────────

    def block_operation(self, operation: str) -> None:
        self.blocked_operations.add(operation)
        logger.info("[SANDBOX-RULES] Operacao bloqueada: %s", operation)

    def unblock_operation(self, operation: str) -> None:
        self.blocked_operations.discard(operation)

    def is_operation_allowed(self, operation: str) -> bool:
        allowed = operation not in self.blocked_operations
        if not allowed:
            self._stats["ops_blocked"] += 1
            logger.warning("[SANDBOX-RULES] Operacao bloqueada: %s", operation)
        return allowed

    # ─────────────────────────────────────────────
    # RESOURCE LIMITS
    # ─────────────────────────────────────────────

    def set_resource_limit(self, resource: str, limit: int) -> None:
        self.resource_limits[resource] = limit
        logger.info("[SANDBOX-RULES] Limite de recurso: %s = %d", resource, limit)

    def get_resource_limit(self, resource: str) -> int:
        return self.resource_limits.get(resource, -1)

    def get_all_resource_limits(self) -> Dict[str, int]:
        return dict(self.resource_limits)

    # ─────────────────────────────────────────────
    # CONTROL
    # ─────────────────────────────────────────────

    def enable(self) -> None:
        self._enabled = True
        logger.info("[SANDBOX-RULES] Regras ativadas")

    def disable(self) -> None:
        self._enabled = False
        logger.warning("[SANDBOX-RULES] Regras desativadas — MODO INSEGURO")

    def is_enabled(self) -> bool:
        return self._enabled

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)

    def get_config_snapshot(self) -> Dict[str, any]:
        return {
            "enabled": self._enabled,
            "allowed_modules": sorted(self.allowed_modules),
            "allowed_read_paths": sorted(self.allowed_read_paths),
            "allowed_write_paths": sorted(self.allowed_write_paths),
            "blocked_paths": sorted(self.blocked_paths),
            "blocked_operations": sorted(self.blocked_operations),
            "blocked_env_vars": sorted(self.blocked_env_vars),
            "resource_limits": dict(self.resource_limits),
            "stats": dict(self._stats),
        }
