# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/mcp/code_executor.py
"""
CodeExecutorTool — wrapper MCP do SandboxExecutor para execução segura de código.
"""

import logging
from typing import Any, Optional

from iaglobal.security.sandbox_executor import SandboxExecutor
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.mcp.code_executor")


class CodeExecutorTool:
    """Executa código em sandbox isolado via SandboxExecutor."""

    def __init__(self, timeout: int = 30):
        self._executor = SandboxExecutor(timeout=timeout)

    async def execute(self, code: str, language: str = "python") -> dict[str, Any]:
        if language != "python":
            return {
                "sucesso": False,
                "erro": "UnsupportedLanguage",
                "details": f"Idioma '{language}' não suportado. Use 'python'.",
            }
        return await self._run_in_thread(code)

    async def _run_in_thread(self, code: str) -> dict[str, Any]:
        import asyncio
        return await asyncio.to_thread(self._executor.execute, code)

    async def validate(self, code: str) -> dict[str, Any]:
        import asyncio
        return await asyncio.to_thread(self._executor.validate, code)