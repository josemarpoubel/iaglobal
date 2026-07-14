import re
import sys
import subprocess
from typing import Optional, Set

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.sandbox.expansion")

_SECURITY_BLOCKLIST = {
    "os",
    "subprocess",
    "shutil",
    "socket",
    "ctypes",
    "fcntl",
    "signal",
    "multiprocessing",
    "threading",
    "inspect",
    "sys",
    "code",
    "codeop",
    "bdb",
    "pdb",
    "traceback",
    "atexit",
    "gc",
    "pickle",
    "shelve",
    "marshal",
    "imp",
    "importlib.metadata",
    "pkgutil",
    "plistlib",
    "sched",
    "spwd",
    "grp",
    "termios",
    "tty",
    "pty",
    "webbrowser",
    "winreg",
}

_PYPI_TO_MODULE = {
    "fpdf2": "fpdf",
    "fpdf": "fpdf",
    "Pillow": "PIL",
    "beautifulsoup4": "bs4",
    "python-dotenv": "dotenv",
    "scikit-learn": "sklearn",
    "pyyaml": "yaml",
    "python-multipart": "multipart",
    "opencv-python": "cv2",
    "python-dateutil": "dateutil",
}


class SandboxExpansion:
    def __init__(self):
        self._installed: Set[str] = set()

    @staticmethod
    def extract_missing_lib(error: ImportError) -> Optional[str]:
        msg = str(error)
        match = re.search(r"No module named ['\"]?([^'\"]+)['\"]", msg)
        if match:
            module_name = match.group(1).split(".")[0]
            return module_name
        match = re.search(r"Module (\S+) is not in", msg)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _module_to_pypi(module_name: str) -> str:
        if module_name in _PYPI_TO_MODULE:
            return _PYPI_TO_MODULE[module_name]
        if module_name.startswith("iaglobal"):
            return module_name
        return module_name

    def is_safe(self, module_name: str) -> bool:
        base = module_name.split(".")[0].split("-")[0].split("_")[0]
        if base in _SECURITY_BLOCKLIST:
            logger.warning(
                "[SANDBOX_EXPANSION] Lib bloqueada por seguranca: %s", module_name
            )
            return False
        return True

    def request_install(self, module_name: str) -> bool:
        pypi_name = self._module_to_pypi(module_name)
        if not self.is_safe(pypi_name):
            return False
        if pypi_name in self._installed:
            logger.info("[SANDBOX_EXPANSION] %s ja instalada", pypi_name)
            return True
        try:
            logger.info("[SANDBOX_EXPANSION] Instalando %s no sandbox...", pypi_name)
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pypi_name, "--quiet"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                self._installed.add(pypi_name)
                logger.info("[SANDBOX_EXPANSION] %s instalada com sucesso", pypi_name)
                self._add_to_allowed_modules(module_name)
                return True
            else:
                logger.error(
                    "[SANDBOX_EXPANSION] Falha ao instalar %s: %s",
                    pypi_name,
                    result.stderr,
                )
                return False
        except subprocess.TimeoutExpired:
            logger.error("[SANDBOX_EXPANSION] Timeout instalando %s", pypi_name)
            return False
        except Exception as e:
            logger.error("[SANDBOX_EXPANSION] Erro instalando %s: %s", pypi_name, e)
            return False

    def _add_to_allowed_modules(self, module_name: str) -> None:
        try:
            from iaglobal.security.sandbox_rules import SandboxRules

            rules = SandboxRules()
            rules.add_allowed_module(module_name)
            logger.info(
                "[SANDBOX_EXPANSION] %s adicionado ao allowed_modules", module_name
            )
        except Exception as e:
            logger.warning(
                "[SANDBOX_EXPANSION] Nao foi possivel atualizar allowed_modules: %s", e
            )


sandbox_expansion = SandboxExpansion()
