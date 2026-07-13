# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/mcp/client.py
"""
MCPClient — conecta a servidores MCP externos via stdio ou SSE.
"""

import asyncio
import json
from typing import Any, Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.mcp.client")


class MCPClient:
    """Cliente MCP para conectar a servidores externos."""

    def __init__(self):
        self._process: Optional[asyncio.subprocess.Process] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._request_id = 0

    async def connect_stdio(self, command: str, args: list[str]) -> dict[str, Any]:
        """Conecta a um servidor MCP via subprocess stdio."""
        try:
            self._process = await asyncio.create_subprocess_exec(
                command,
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._reader = self._process.stdout
            self._writer = self._process.stdin
            self._connected = True

            initialized = await self._initialize()
            logger.info("Conectado via stdio: %s %s", command, " ".join(args))
            return initialized
        except Exception as e:
            logger.error("Falha ao conectar via stdio: %s", e)
            return {"error": str(e)}

    async def connect_sse(self, url: str) -> dict[str, Any]:
        """Conecta a um servidor MCP via SSE."""
        try:
            import aiohttp

            self._session = aiohttp.ClientSession()
            async with self._session.get(url) as resp:
                if resp.status != 200:
                    return {"error": f"HTTP {resp.status}"}
                self._sse_url = url
                self._connected = True
                logger.info("Conectado via SSE: %s", url)
                return {"status": "connected", "url": url}
        except Exception as e:
            logger.error("Falha ao conectar via SSE: %s", e)
            return {"error": str(e)}

    async def list_tools(self) -> list[dict[str, Any]]:
        if not self._connected:
            return []
        result = await self._send_request("tools/list", {})
        return result.get("tools", result.get("result", {}).get("tools", []))

    async def call_tool(self, name: str, arguments: dict) -> dict[str, Any]:
        if not self._connected:
            return {"error": "Not connected"}
        return await self._send_request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )

    async def _send_request(self, method: str, params: dict) -> dict[str, Any]:
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        if self._writer:
            data = (json.dumps(request) + "\n").encode()
            self._writer.write(data)
            await self._writer.drain()

            line = await self._reader.readline()
            if line:
                return json.loads(line.decode())
        return {"error": "No response"}

    async def close(self):
        self._connected = False
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None
        if hasattr(self, "_session"):
            await self._session.close()
