# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/mcp/file_system.py
"""
FileSystemTool — leitura/escrita segura de arquivos via SandboxRules whitelist.
"""

import os
import logging
from pathlib import Path
from typing import Optional

from iaglobal._paths import PROJECT_ROOT
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.mcp.file_system")

BASE = Path(PROJECT_ROOT).resolve()

ALLOWED_READ_PREFIXES = [
    BASE / "iaglobal",
    BASE / "tests",
    BASE / "docs",
    BASE / "memory" / "data" / "json",
]

ALLOWED_WRITE_PREFIXES = [
    BASE / "memory" / "data" / "json",
    BASE / "memory" / "data" / "script",
]


class FileSystemTool:
    """Leitura e escrita segura de arquivos com whitelist de paths."""

    async def read_file(self, path: str) -> Optional[str]:
        resolved = self._resolve(path)
        if not resolved or not self._is_path_allowed(resolved, ALLOWED_READ_PREFIXES):
            logger.warning("Leitura bloqueada: %s", path)
            return None
        try:
            return resolved.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("Erro ao ler %s: %s", resolved, e)
            return None

    async def write_file(self, path: str, content: str) -> bool:
        resolved = self._resolve(path)
        if not resolved or not self._is_path_allowed(resolved, ALLOWED_WRITE_PREFIXES):
            logger.warning("Escrita bloqueada: %s", path)
            return False
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            logger.info("Arquivo escrito: %s", resolved)
            return True
        except Exception as e:
            logger.error("Erro ao escrever %s: %s", resolved, e)
            return False

    async def list_dir(self, path: str) -> list[str]:
        resolved = self._resolve(path)
        if not resolved or not self._is_path_allowed(resolved, ALLOWED_READ_PREFIXES):
            logger.warning("Listagem bloqueada: %s", path)
            return []
        try:
            return sorted(
                str(p.relative_to(BASE)) if p.is_relative_to(BASE) else str(p)
                for p in resolved.iterdir()
            )
        except Exception as e:
            logger.error("Erro ao listar %s: %s", resolved, e)
            return []

    @staticmethod
    def _resolve(path: str) -> Optional[Path]:
        try:
            p = Path(path)
            if not p.is_absolute():
                p = BASE / p
            return p.resolve()
        except Exception:
            return None

    @staticmethod
    def _is_path_allowed(resolved: Path, allowed_prefixes: list[Path]) -> bool:
        for prefix in allowed_prefixes:
            prefix_resolved = prefix.resolve()
            try:
                resolved.relative_to(prefix_resolved)
                return True
            except ValueError:
                continue
        return False