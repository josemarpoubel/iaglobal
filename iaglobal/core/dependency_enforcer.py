# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
DependencyEnforcer — Verifica e repara imports em código gerado por agentes.

Filosofia:
  Agentes podem inventar bibliotecas que não existem. Este enforcer:
  1. Extrai todos os imports do código gerado
  2. Verifica cada um contra stdlib + pacotes instalados
  3. Envolve imports não-stdlib não-instalados em try/except ImportError
  4. Garante que o código compila mesmo sem a dependência externa
"""
import ast
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Tuple, Set, Dict, Optional
from dataclasses import dataclass, field

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.core.dependency_enforcer")

INSTRUCAO_DEPENDENCIAS = (
    "Use apenas a biblioteca padrão do Python. "
    "Se for necessária uma função auxiliar, escreva-a explicitamente dentro "
    "do bloco de código. Nunca presuma a existência de utilitários externos. "
    "O código deve ser íntegro e rodar sem erros de compilação."
)

# Caminho do requirements.txt do projeto
REQUIREMENTS_PATH = Path(__file__).parent.parent.parent / "requirements.txt"


@dataclass
class EnforcementResult:
    original: str = ""
    modified: str = ""
    stdlib_imports: List[str] = field(default_factory=list)
    installed_imports: List[str] = field(default_factory=list)
    wrapped_imports: List[str] = field(default_factory=list)
    unknown_imports: List[str] = field(default_factory=list)
    installed_imports: List[str] = field(default_factory=list)  # Novos installs
    was_modified: bool = False


class DependencyEnforcer:
    """Enforces dependency integrity on generated Python code."""

    _stdlib_cache: Optional[Set[str]] = None
    _installed_cache: Optional[Dict[str, str]] = None
    _installed_ts: float = 0.0
    _requirements_cache: Optional[Set[str]] = None

    def __init__(self, max_import_error_wraps: int = 10, auto_install: bool = True):
        self.max_wraps = max_import_error_wraps
        self.auto_install = auto_install

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enforce(self, code: str) -> EnforcementResult:
        """
        Analisa e repara imports no código.
        Retorna resultado com código modificado e relatório.
        """
        if not code or not code.strip():
            return EnforcementResult(original=code, modified=code)

        result = EnforcementResult(original=code)
        imports = self._extract_imports(code)

        if not imports:
            result.modified = code
            return result

        stdlib = self._get_stdlib()
        installed = self._get_installed()
        requirements = self._get_requirements() if self.auto_install else set()

        wrap_lines: List[Tuple[int, str, str]] = []

        for lineno, module, full_stmt in imports:
            top_module = module.split(".")[0]

            if top_module in stdlib:
                result.stdlib_imports.append(module)
                continue

            if top_module in installed:
                result.installed_imports.append(module)
                continue

            # Não-stdlib não-instalado → tenta instalar ou faz wrap
            if self.auto_install and top_module in requirements:
                if self._install_package(top_module):
                    result.installed_imports.append(module)
                    # Atualiza cache após install
                    installed = self._get_installed()
                    continue
            
            # Não conseguiu instalar → wrap com try/except
            if len(wrap_lines) < self.max_wraps:
                wrap_lines.append((lineno, module, full_stmt))
                result.wrapped_imports.append(module)
            else:
                result.unknown_imports.append(module)

        if wrap_lines:
            result.modified = self._wrap_imports(code, wrap_lines)
            result.was_modified = True
            logger.info(
                "[DEPENDENCY-ENFORCER] %d imports envolvidos em try/except",
                len(wrap_lines),
            )
        else:
            result.modified = code

        if result.unknown_imports:
            logger.warning(
                "[DEPENDENCY-ENFORCER] %d imports desconhecidos (além do limite): %s",
                len(result.unknown_imports),
                result.unknown_imports,
            )

        return result

    # ------------------------------------------------------------------
    # Import extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_imports(code: str) -> List[Tuple[int, str, str]]:
        """
        Extrai (linha, module_name, stmt_text) de imports Python
        usando AST. Fallback para regex se AST falhar.
        """
        imports: List[Tuple[int, str, str]] = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append((node.lineno, alias.name, _ast_to_code(node)))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append((node.lineno, node.module, _ast_to_code(node)))
        except SyntaxError:
            imports = _extract_imports_regex(code)
        return imports

    # ------------------------------------------------------------------
    # Stdlib detection (Python 3.10+ via sys.stdlib_module_names)
    # ------------------------------------------------------------------

    @classmethod
    def _get_stdlib(cls) -> Set[str]:
        if cls._stdlib_cache is not None:
            return cls._stdlib_cache
        # Python 3.10+ has sys.stdlib_module_names
        if hasattr(sys, "stdlib_module_names"):
            cls._stdlib_cache = set(sys.stdlib_module_names)
            return cls._stdlib_cache  # type: ignore[return-value]
        cls._stdlib_cache = _STDLIB_FALLBACK
        return cls._stdlib_cache

    # ------------------------------------------------------------------
    # Installed packages detection
    # ------------------------------------------------------------------

    @classmethod
    def _get_installed(cls) -> Dict[str, str]:
        import time
        now = time.time()
        if cls._installed_cache is not None and (now - cls._installed_ts) < 120.0:
            return cls._installed_cache
        cls._installed_cache = cls._fetch_installed()
        cls._installed_ts = now
        return cls._installed_cache

    @staticmethod
    def _fetch_installed() -> Dict[str, str]:
        """Retorna {package_name_lower: version} do pip list."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                return {p["name"].lower(): p["version"] for p in packages}
        except Exception:
            pass
        return {}

    @classmethod
    def _get_requirements(cls) -> Set[str]:
        """Carrega pacotes listados no requirements.txt."""
        if cls._requirements_cache is not None:
            return cls._requirements_cache
        
        cls._requirements_cache = set()
        if not REQUIREMENTS_PATH.exists():
            return cls._requirements_cache
        
        try:
            content = REQUIREMENTS_PATH.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Remove version specifiers (ex: package==1.0.0 → package)
                pkg = line.split("==")[0].split(">=")[0].split("<")[0].split("[")[0]
                pkg = pkg.lower().replace("-", "_")  # Normaliza
                cls._requirements_cache.add(pkg)
            logger.info(
                "[DEPENDENCY-ENFORCER] requirements.txt: %d pacotes carregados",
                len(cls._requirements_cache),
            )
        except Exception as e:
            logger.debug("[DEPENDENCY-ENFORCER] Falha ao ler requirements.txt: %s", e)
        
        return cls._requirements_cache

    def _install_package(self, package_name: str) -> bool:
        """
        Instala pacote via pip install.
        Retorna True se sucesso, False se falha.
        """
        logger.info(
            "[DEPENDENCY-ENFORCER] Instalando pacote: %s (auto-install)",
            package_name,
        )
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", package_name],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                logger.info(
                    "[DEPENDENCY-ENFORCER] ✅ %s instalado com sucesso",
                    package_name,
                )
                return True
            else:
                logger.warning(
                    "[DEPENDENCY-ENFORCER] ❌ Falha ao instalar %s: %s",
                    package_name, result.stderr[:200] if result.stderr else "erro desconhecido",
                )
                return False
        except subprocess.TimeoutExpired:
            logger.warning(
                "[DEPENDENCY-ENFORCER] ❌ Timeout ao instalar %s (60s)",
                package_name,
            )
            return False
        except Exception as e:
            logger.warning(
                "[DEPENDENCY-ENFORCER] ❌ Erro ao instalar %s: %s",
                package_name, e,
            )
            return False

    # ------------------------------------------------------------------
    # Import wrapping
    # ------------------------------------------------------------------

    def _wrap_imports(
        self, code: str, targets: List[Tuple[int, str, str]]
    ) -> str:
        """
        Substitui cada import não-stdlib não-instalado por
        try/except ImportError com fallback None.
        """
        lines = code.split("\n")
        # Processa de baixo pra cima para não quebrar numeração
        for lineno, module_name, _ in sorted(targets, key=lambda x: -x[0]):
            idx = lineno - 1
            if idx < 0 or idx >= len(lines):
                continue
            indent = _detect_indent(lines[idx])

            pad = "    " if not indent else ""
            try_lines = [
                f"{pad}try:",
                f"{pad}    {lines[idx]}",
                f"{pad}except ImportError:",
                f"{pad}    import logging",
                f"{pad}    logging.warning(",
                f"{pad}        \"[DEPENDENCY] {module_name} nao encontrado. \"",
                f"{pad}        \"Adicione ao requirements.txt e execute 'pip install -r requirements.txt'\"",
                f"{pad}    )",
                f"{pad}    {module_name.split('.')[0]} = None  # type: ignore[assignment]",
            ]
            lines[idx] = "\n".join(try_lines)

        return "\n".join(lines)


def _ast_to_code(node: ast.AST) -> str:
    """Converte nó AST de import de volta para string."""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _detect_indent(line: str) -> str:
    """Detecta indentação de uma linha."""
    return line[: len(line) - len(line.lstrip())]


def _extract_imports_regex(code: str) -> List[Tuple[int, str, str]]:
    """Fallback: extrai imports via regex quando AST falha."""
    imports: List[Tuple[int, str, str]] = []
    for i, line in enumerate(code.split("\n"), 1):
        stripped = line.strip()
        m = __import_re.match(stripped)
        if m:
            imports.append((i, m.group(1), stripped))
    return imports


__import_re = __import__("re").compile(
    r"^(?:import\s+(\w+(?:\.\w+)*)|from\s+(\w+(?:\.\w+)*)\s+import)"
)


# Fallback stdlib set for Python < 3.10
_STDLIB_FALLBACK: Set[str] = {
    "os", "sys", "re", "json", "math", "datetime", "time", "random",
    "collections", "itertools", "functools", "pathlib", "typing",
    "dataclasses", "abc", "enum", "hashlib", "base64", "binascii",
    "textwrap", "string", "struct", "io", "socket", "http", "urllib",
    "xml", "html", "csv", "configparser", "argparse", "logging",
    "warnings", "traceback", "pickle", "shelve", "dbm", "sqlite3",
    "bz2", "gzip", "zipfile", "tarfile", "shutil", "tempfile",
    "fileinput", "fnmatch", "glob", "linecache", "threading",
    "multiprocessing", "subprocess", "signal", "select", "selectors",
    "asyncio", "contextvars", "ssl", "email", "smtplib", "poplib",
    "imaplib", "telnetlib", "uuid", "copy", "pprint", "profile",
    "pstats", "calendar", "locale", "gettext", "inspect", "ast",
    "dis", "tokenize", "keyword", "token", "symbol", "parser",
    "compileall", "py_compile", "pyclbr", "pdb", "cprofile",
    "doctest", "unittest", "test", "venv", "ensurepip", "zipapp",
    "ctypes", "curses", "turtle", "tkinter", "webbrowser",
    "fractions", "decimal", "numbers", "statistics", "array",
    "weakref", "types", "code", "codeop", "rexec", "bastion",
    "imp", "importlib", "zipimport", "pkgutil", "modulefinder",
    "runpy", "site", "codecs", "encodings", "getpass", "grp",
    "pwd", "platform", "errno", "builtins", "__future__",
}


dependency_enforcer = DependencyEnforcer()
