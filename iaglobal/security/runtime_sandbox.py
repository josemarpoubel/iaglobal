# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Runtime Sandbox — Segunda Barreira de Defesa (Runtime).

Intercepta chamadas perigosas que a análise estática (AST) não detecta:
  - String concatenação (__import__ via f-string)
  - Dict access dinâmico (builtins['exec'])
  - getattr(__builtins__, 'exec')
  - globals() / vars() introspection
  - setattr em dunder methods

Arquitetura:
  - audit_logger: Log síncrono/assíncrono para EpigeneticRegistry
  - _wrap_builtins: Cria dict de builtins seguros para __builtins__
  - restricted_exec: exec() com sandbox aplicado
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set

from iaglobal._paths import DATA_DIR
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.security.runtime_sandbox")

# Builtins que devem ser bloqueados totalmente
BLOCKED_BUILTINS: Set[str] = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "input",
    "breakpoint",
}

# Builtins com verificação contextual
RESTRICTED_BUILTINS: Set[str] = {
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "vars",
    "dir",
    "open",
}

# Módulos permitidos para importação
DEFAULT_ALLOWED_MODULES: Set[str] = {
    "math",
    "random",
    "datetime",
    "collections",
    "itertools",
    "functools",
    "typing",
    "dataclasses",
    "pathlib",
    "json",
    "re",
    "string",
    "time",
    "hashlib",
    "copy",
    "enum",
    "statistics",
    "decimal",
    "fractions",
}

# Módulos blacklistados
BLACKLISTED_MODULES: Set[str] = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "urllib",
    "requests",
    "http",
    "ftplib",
    "smtplib",
    "telnetlib",
    "shutil",
    "tempfile",
    "pickle",
    "marshal",
    "ctypes",
    "importlib",
    "signal",
    "resource",
    "threading",
    "multiprocessing",
    "asyncio",
}


class SecurityViolation(Exception):
    """Levantada quando Runtime Sandbox bloqueia operação perigosa."""

    def __init__(self, message: str, agent_id: Optional[str] = None):
        self.agent_id = agent_id
        self.message = message
        super().__init__(message)


class AuditLogger:
    """Logger de auditoria síncrono para Runtime Sandbox.

    Funciona com e sem event loop (fire-and-forget via create_task quando disponível).
    """

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or DATA_DIR / "audit"
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        self.log_path.mkdir(parents=True, exist_ok=True)

    def log_violation(
        self,
        agent_id: str,
        builtin_name: str,
        violation_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Registra violação. Usa create_task se houver loop, senão escreve direto."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._async_log(agent_id, builtin_name, violation_type, context)
            )
        except RuntimeError:
            self._write_file(agent_id, builtin_name, violation_type, context)

    async def _async_log(
        self,
        agent_id: str,
        builtin_name: str,
        violation_type: str,
        context: Optional[Dict[str, Any]],
    ) -> None:
        from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry

        registry = EpigeneticRegistry()
        task_hash = hashlib.sha256(
            f"{agent_id}:{builtin_name}:{violation_type}".encode()
        ).hexdigest()[:12]

        metadata = {
            "builtin_name": builtin_name,
            "violation_type": violation_type,
            "context": context or {},
            "timestamp": time.time(),
            "runtime_sandbox": True,
        }

        try:
            await registry.record_failure(
                agent_id=agent_id,
                task_hash=task_hash,
                error_type=violation_type,
                context=metadata,
            )
        except Exception as e:
            logger.warning("[RUNTIME_SANDBOX] Falha EpigeneticRegistry: %s", e)

        self._write_file(agent_id, builtin_name, violation_type, context)

    def _write_file(
        self,
        agent_id: str,
        builtin_name: str,
        violation_type: str,
        context: Optional[Dict[str, Any]],
    ) -> None:
        log_entry = {
            "agent_id": agent_id,
            "builtin_name": builtin_name,
            "violation_type": violation_type,
            "context": context or {},
            "timestamp": time.time(),
        }
        log_file = self.log_path / f"runtime_{time.strftime('%Y%m%d')}.jsonl"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(str(hashlib.sha256(str(log_entry).encode()).hexdigest()[:12]) + "\n")
        except Exception as e:
            logger.error("[RUNTIME_SANDBOX] Falha ao escrever log: %s", e)


class RestrictedBuiltins:
    """Wrapper síncrono para builtins perigosos.

    Usado pela AuditLogger para bloquear operações.
    """

    def __init__(
        self,
        agent_id: str,
        audit_logger: Optional[AuditLogger] = None,
        allowed_modules: Optional[Set[str]] = None,
    ):
        self.agent_id = agent_id
        self.audit_logger = audit_logger or AuditLogger()
        self.allowed_modules = allowed_modules or DEFAULT_ALLOWED_MODULES
        self._original = sys.modules["builtins"]

    def __getattr__(self, name: str) -> Any:
        if name in BLOCKED_BUILTINS:
            self.audit_logger.log_violation(
                self.agent_id, name, "builtin_blocked",
                {"reason": "builtin perigoso bloqueado"},
            )
            raise SecurityViolation(
                f"[RUNTIME_SANDBOX] {name} bloqueado: builtin_blocked",
                agent_id=self.agent_id,
            )
        if name == "__import__":
            return self._restricted_import
        if name in ("getattr", "setattr", "delattr"):
            return getattr(self._original, name)
        if name in ("globals", "vars", "dir"):
            return self._filtered_introspection(name)
        return getattr(self._original, name)

    def __getitem__(self, name: str) -> Any:
        if name in BLOCKED_BUILTINS:
            self.audit_logger.log_violation(
                self.agent_id, name, "dict_access_blocked",
                {"reason": "dict access para builtin perigoso"},
            )
            raise SecurityViolation(
                f"[RUNTIME_SANDBOX] {name} bloqueado: dict_access_blocked",
                agent_id=self.agent_id,
            )
        return getattr(self._original, name)

    def _restricted_import(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if name in BLACKLISTED_MODULES or name not in self.allowed_modules:
            self.audit_logger.log_violation(
                self.agent_id, "__import__", "import_blocked",
                {"module": name},
            )
            raise SecurityViolation(
                f"[RUNTIME_SANDBOX] import bloqueado: {name}",
                agent_id=self.agent_id,
            )
        return self._original.__import__(name, *args, **kwargs)

    def _filtered_introspection(self, name: str) -> Any:
        if name == "globals":
            g = self._original.globals()
            return {k: v for k, v in g.items() if not k.startswith("__") and k not in BLOCKED_BUILTINS}
        if name == "vars":
            import inspect
            frame = inspect.currentframe().f_back
            return {k: v for k, v in frame.f_locals.items() if not k.startswith("__")}
        if name == "dir":
            return []
        return getattr(self._original, name)()


def _block(name: str, agent_id: str, audit_logger: AuditLogger) -> Any:
    """Cria função que sempre levanta SecurityViolation."""
    def blocker(*args: Any, **kwargs: Any) -> Any:
        audit_logger.log_violation(agent_id, name, "builtin_blocked", {"reason": name})
        raise SecurityViolation(
            f"[RUNTIME_SANDBOX] {name} bloqueado: builtin_blocked",
            agent_id=agent_id,
        )
    blocker.__name__ = name
    return blocker


def _restricted_import_func(
    agent_id: str,
    audit_logger: AuditLogger,
    allowed_modules: Set[str],
) -> Any:
    """__import__ com whitelist/blacklist."""
    _orig = sys.modules["builtins"]

    def restricted_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name in BLACKLISTED_MODULES or name not in allowed_modules:
            audit_logger.log_violation(
                agent_id, "__import__", "import_blocked", {"module": name}
            )
            raise SecurityViolation(
                f"[RUNTIME_SANDBOX] import bloqueado: {name}",
                agent_id=agent_id,
            )
        return _orig.__import__(name, *args, **kwargs)

    restricted_import.__name__ = "__import__"
    return restricted_import


def _safe_getattr(agent_id: str, audit_logger: AuditLogger) -> Any:
    _orig = sys.modules["builtins"]

    def safe_getattr(obj: Any, name: str, *args: Any) -> Any:
        blocked = False
        obj_type = ""
        if obj is _orig:
            blocked = True
            obj_type = "builtins_module"
        elif isinstance(obj, dict) and any(k in obj for k in BLOCKED_BUILTINS):
            blocked = True
            obj_type = "builtins_dict"
        elif isinstance(obj, type) and obj.__name__ in {"os", "sys", "subprocess"}:
            blocked = True
            obj_type = f"sensitive_module:{obj.__name__}"
        if blocked:
            audit_logger.log_violation(
                agent_id, "getattr", "builtins_access",
                {"object": obj_type, "attribute": name}
            )
            raise SecurityViolation(
                f"[RUNTIME_SANDBOX] getattr bloqueado: {obj_type}.{name}",
                agent_id=agent_id,
            )
        return _orig.getattr(obj, name, *args)

    safe_getattr.__name__ = "getattr"
    return safe_getattr


def _safe_setattr(agent_id: str, audit_logger: AuditLogger) -> Any:
    _orig = sys.modules["builtins"]

    def safe_setattr(obj: Any, name: str, value: Any) -> None:
        if name.startswith("__") and name.endswith("__"):
            audit_logger.log_violation(
                agent_id, "setattr", "dunder_modification",
                {"object": type(obj).__name__, "attribute": name}
            )
            raise SecurityViolation(
                f"[RUNTIME_SANDBOX] setattr bloqueado: dunder {name}",
                agent_id=agent_id,
            )
        return _orig.setattr(obj, name, value)

    safe_setattr.__name__ = "setattr"
    return safe_setattr


def _safe_delattr(agent_id: str, audit_logger: AuditLogger) -> Any:
    _orig = sys.modules["builtins"]

    def safe_delattr(obj: Any, name: str) -> None:
        if name.startswith("__") and name.endswith("__"):
            audit_logger.log_violation(
                agent_id, "delattr", "dunder_deletion",
                {"object": type(obj).__name__, "attribute": name}
            )
            raise SecurityViolation(
                f"[RUNTIME_SANDBOX] delattr bloqueado: dunder {name}",
                agent_id=agent_id,
            )
        return _orig.delattr(obj, name)

    safe_delattr.__name__ = "delattr"
    return safe_delattr


def _make_restricted_builtins(
    agent_id: str,
    audit_logger: AuditLogger,
    allowed_modules: Set[str],
) -> Dict[str, Any]:
    """Constrói o dict de builtins para __builtins__.

    Este dict é o que exec() consome como namespace de builtins.
    """
    _orig = sys.modules["builtins"]
    restricted: Dict[str, Any] = {}

    # 1. Bloqueia builtins perigosos
    for name in BLOCKED_BUILTINS:
        restricted[name] = _block(name, agent_id, audit_logger)

    # 2. Restringe builtins contextuais
    restricted["__import__"] = _restricted_import_func(agent_id, audit_logger, allowed_modules)
    restricted["getattr"] = _safe_getattr(agent_id, audit_logger)
    restricted["setattr"] = _safe_setattr(agent_id, audit_logger)
    restricted["delattr"] = _safe_delattr(agent_id, audit_logger)

    # globals/vars/dir filtrados
    restricted["globals"] = _blocked_introspection("globals")
    restricted["vars"] = _blocked_introspection("vars")
    restricted["dir"] = _blocked_introspection("dir")

    # open bloqueado
    restricted["open"] = _block("open", agent_id, audit_logger)

    # 3. Copia builtins seguros do módulo original
    safe_names = (
        "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
        "callable", "chr", "classmethod", "complex", "delattr", "dict",
        "divmod", "enumerate", "filter", "float", "format", "frozenset",
        "hasattr", "hash", "hex", "id", "int", "isinstance", "issubclass",
        "iter", "len", "list", "map", "max", "memoryview", "min", "next",
        "object", "oct", "ord", "pow", "print", "property", "range",
        "repr", "reversed", "round", "set", "setattr", "slice",
        "sorted", "staticmethod", "str", "sum", "super", "tuple",
        "type", "zip", "__build_class__", "__name__",
    )
    for name in safe_names:
        if hasattr(_orig, name):
            restricted[name] = getattr(_orig, name)

    # 4. Módulos permitidos ficam disponíveis
    for mod_name in allowed_modules:
        try:
            import importlib
            restricted[mod_name] = importlib.import_module(mod_name)
        except ImportError:
            pass

    return restricted


def _blocked_introspection(name: str) -> Any:
    """globals/vars/dir que retornam dados filtrados."""
    def func(*args: Any, **kwargs: Any) -> Any:
        if name == "globals":
            g = sys._getframe(1).f_globals
            return {k: v for k, v in g.items() if not k.startswith("__") and k not in BLOCKED_BUILTINS}
        if name == "vars":
            obj = args[0] if args else sys._getframe(1)
            d = vars(obj) if hasattr(obj, "__dict__") else {}
            return {k: v for k, v in d.items() if not k.startswith("__")}
        if name == "dir":
            obj = args[0] if args else sys._getframe(1)
            result = dir(obj) if hasattr(obj, "__dir__") else []
            return [n for n in result if not n.startswith("__") and n not in BLOCKED_BUILTINS]
        return []
    func.__name__ = name
    return func


class SafeGlobals(dict):
    """Dicionário global seguro para exec().

    Uso:
        safe = SafeGlobals(agent_id="coder-1")
        exec(code, safe)
    """

    def __init__(
        self,
        agent_id: str,
        audit_logger: Optional[AuditLogger] = None,
        allowed_modules: Optional[Set[str]] = None,
        extra_safe_funcs: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        self._agent_id = agent_id
        self._audit_logger = audit_logger or AuditLogger()
        self._allowed_modules = allowed_modules or DEFAULT_ALLOWED_MODULES

        # Cria dict de builtins restritos
        restricted = _make_restricted_builtins(
            agent_id, self._audit_logger, self._allowed_modules
        )
        super().__setitem__("__builtins__", restricted)

        # Adiciona funções extras seguras
        if extra_safe_funcs:
            for name, func in extra_safe_funcs.items():
                if not name.startswith("__") and name not in BLOCKED_BUILTINS:
                    self[name] = func

    def __setitem__(self, key: str, value: Any) -> None:
        if key in BLOCKED_BUILTINS:
            raise SecurityViolation(
                f"[RUNTIME_SANDBOX] Atribuição bloqueada: {key}"
            )
        super().__setitem__(key, value)


def create_sandboxed_exec(
    agent_id: str,
    audit_logger: Optional[AuditLogger] = None,
    allowed_modules: Optional[Set[str]] = None,
    extra_safe_funcs: Optional[Dict[str, Any]] = None,
) -> tuple[SafeGlobals, AuditLogger]:
    """Factory function para criar ambiente de execução sandbox.

    Args:
        agent_id: ID do agente
        audit_logger: Logger customizado (cria default se None)
        allowed_modules: Módulos permitidos para import
        extra_safe_funcs: Funções extras seguras

    Returns:
        (SafeGlobals, AuditLogger)
    """
    al = audit_logger or AuditLogger()
    safe = SafeGlobals(
        agent_id=agent_id,
        audit_logger=al,
        allowed_modules=allowed_modules,
        extra_safe_funcs=extra_safe_funcs,
    )
    return safe, al
