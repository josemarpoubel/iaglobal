# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/agents/tool_caller_agent.py
"""
ToolCallerAgent — seleciona e chama tools MCP baseado no plano do orchestrator.
Registra execution_metrics para BanditPolicy.
"""

import time
import logging
from typing import Any, Optional

from iaglobal.mcp.discovery import MCPDiscovery
from iaglobal.mcp.search_web import WebSearchTool
from iaglobal.mcp.file_system import FileSystemTool
from iaglobal.mcp.code_executor import CodeExecutorTool
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.agents.tool_caller")

_TOOL_MAP = {
    "web_search": lambda: WebSearchTool().search,
    "web_fetch": lambda: WebSearchTool().fetch_page,
    "read_file": lambda: FileSystemTool().read_file,
    "write_file": lambda: FileSystemTool().write_file,
    "list_dir": lambda: FileSystemTool().list_dir,
    "execute_code": lambda: CodeExecutorTool().execute,
}


class ToolCallerAgent:
    """Seleciona e executa tools MCP com registro de métricas."""

    def __init__(self):
        self.discovery = MCPDiscovery()

    async def run(self, task: dict) -> dict[str, Any]:
        """Executa uma task de tool MCP.

        task esperado:
        {
            "tool": "web_search",
            "arguments": {"query": "...", "max_results": 5},
            "agent_id": "planner_agent" (opcional)
        }
        """
        tool_name = task.get("tool_name") or task.get("tool")
        arguments = task.get("arguments", {})
        agent_id = task.get("agent_id", "unknown")
        start = time.time()
        error = None

        try:
            if tool_name in _TOOL_MAP:
                handler = _TOOL_MAP[tool_name]()
                result = await handler(**arguments)
            else:
                result = await self._call_external_tool(tool_name, arguments)
        except Exception as e:
            logger.exception("ToolCallerAgent falhou em %s: %s", tool_name, e)
            result = {"error": str(e)}
            error = str(e)

        latency = time.time() - start
        success = error is None and (not isinstance(result, dict) or "error" not in result)

        execution_metrics = {
            "tool_name": tool_name,
            "arguments": arguments,
            "success": success,
            "latency": latency,
            "error": error,
            "result_summary": self._summarize(result),
        }

        return {
            "result": result,
            "execution_metrics": execution_metrics,
        }

    async def _call_external_tool(self, tool_name: str, arguments: dict) -> Any:
        from iaglobal.mcp.client import MCPClient

        tool_schema = await self.discovery.get_tool(tool_name)
        if not tool_schema:
            return {"error": f"Tool '{tool_name}' não encontrada no discovery"}

        server_name = tool_schema.get("server", "unknown")
        if server_name == "internal":
            return {"error": f"Tool interna '{tool_name}' não mapeada no ToolCallerAgent"}

        client = MCPClient()
        try:
            result = await client.call_tool(tool_name, arguments)
            return result
        finally:
            await client.close()

    @staticmethod
    def _summarize(result: Any, max_len: int = 200) -> str:
        text = str(result)
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text