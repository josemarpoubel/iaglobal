# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/mcp/discovery.py
"""
MCPDiscovery — descoberta dinâmica de tools MCP internas e externas.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional

from iaglobal._paths import PROJECT_ROOT
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.mcp.discovery")

CACHE_PATH = (
    Path(PROJECT_ROOT) / "iaglobal" / "memory" / "data" / "json" / "mcp_tools.json"
)

INTERNAL_TOOLS = [
    {
        "name": "metabolic_audit",
        "description": "Executa auditoria metabólica completa e retorna score de saúde (0-1).",
        "server": "internal",
        "parameters": {},
    },
    {
        "name": "get_ivm",
        "description": "Retorna o Índice de Viabilidade Metabólica atual.",
        "server": "internal",
        "parameters": {},
    },
    {
        "name": "web_search",
        "description": "Busca na web e retorna resultados estruturados (title, url, snippet).",
        "server": "internal",
        "parameters": {
            "query": {"type": "string", "description": "Termo de busca"},
            "max_results": {"type": "integer", "default": 5},
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch do conteúdo de uma URL.",
        "server": "internal",
        "parameters": {
            "url": {"type": "string"},
            "timeout": {"type": "integer", "default": 15},
        },
    },
    {
        "name": "read_file",
        "description": "Lê arquivo seguro — apenas paths na whitelist do projeto.",
        "server": "internal",
        "parameters": {"path": {"type": "string"}},
    },
    {
        "name": "write_file",
        "description": "Escreve arquivo seguro — apenas paths na whitelist.",
        "server": "internal",
        "parameters": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
    },
    {
        "name": "list_dir",
        "description": "Lista diretório — apenas paths na whitelist.",
        "server": "internal",
        "parameters": {"path": {"type": "string"}},
    },
    {
        "name": "execute_code",
        "description": "Executa código Python em sandbox isolado.",
        "server": "internal",
        "parameters": {
            "code": {"type": "string"},
            "language": {"type": "string", "default": "python"},
        },
    },
]


class MCPDiscovery:
    """Descoberta dinâmica de tools MCP."""

    def __init__(self):
        self._tools_cache: dict[str, dict[str, Any]] = {}
        self._cache_path = CACHE_PATH

    async def discover_all(self) -> dict[str, Any]:
        """Descobre tools de todos os servidores registrados."""
        tools: list[dict[str, Any]] = list(INTERNAL_TOOLS)

        external_tools = await self._discover_external_servers()
        tools.extend(external_tools)

        cache_data = {
            "version": 1,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tools": tools,
        }
        self._persist_cache(cache_data)
        self._tools_cache = {t["name"]: t for t in tools}
        return cache_data

    async def get_tool(self, name: str) -> Optional[dict[str, Any]]:
        if name in self._tools_cache:
            return self._tools_cache[name]

        if not self._tools_cache:
            await self.discover_all()
        return self._tools_cache.get(name)

    async def _discover_external_servers(self) -> list[dict[str, Any]]:
        from iaglobal.mcp.client import MCPClient

        servers = self._load_server_registry()
        all_tools = []

        for server in servers:
            client = MCPClient()
            try:
                if server.get("type") == "stdio":
                    await client.connect_stdio(
                        server["command"], server.get("args", [])
                    )
                elif server.get("type") == "sse":
                    await client.connect_sse(server["url"])
                else:
                    continue

                tools = await client.list_tools()
                for t in tools:
                    t["server"] = server.get("name", "external")
                    all_tools.append(t)
                await client.close()
            except Exception as e:
                logger.warning(
                    "Falha ao descobrir tools em %s: %s", server.get("name"), e
                )

        return all_tools

    def _load_server_registry(self) -> list[dict[str, Any]]:
        registry_path = (
            Path(PROJECT_ROOT)
            / "iaglobal"
            / "memory"
            / "data"
            / "json"
            / "mcp_servers.json"
        )
        if registry_path.exists():
            try:
                data = json.loads(registry_path.read_text())
                return data.get("servers", [])
            except Exception as e:
                logger.warning("Erro ao carregar registro de servidores: %s", e)
        return []

    def _persist_cache(self, data: dict[str, Any]):
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.info(
                "Cache MCP salvo: %s (%d tools)", self._cache_path, len(data["tools"])
            )
        except Exception as e:
            logger.error("Erro ao persistir cache MCP: %s", e)
