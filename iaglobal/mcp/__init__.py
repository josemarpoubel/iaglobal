# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
iaglobal.mcp — Módulo MCP (Model Context Protocol) unificado.

Este módulo consolida todos os servidores MCP do iaglobal em uma arquitetura coesa:

Arquitetura:
- server.py: Servidor MCP unificado (FastMCP + FastAPI gateway)
- mcp_agent.py: Agente de auditoria metabólica
- tools/Tools especializadas (web_search, file_system, code_executor)
- discovery.py: Descoberta de serviços MCP
- client.py: Cliente MCP para conexão com servidores remotos

DNA do sistema:
- Todos arquivos devem ter LINEAGE_MARKER
- Comunicação assíncrona via AcetylcholineBus
- Circuit breakers para proteção contra falhas em cascata
"""

import importlib
from typing import Any


def __getattr__(name: str) -> Any:
    """Lazy import para evitar RuntimeWarning de import circular."""
    module_map = {
        "mcp": "iaglobal.mcp.server",
        "run_server": "iaglobal.mcp.server",
        "run_http_server": "iaglobal.mcp.server",
        "get_app": "iaglobal.mcp.server",
        "metabolic_audit": "iaglobal.mcp.server",
        "get_ivm": "iaglobal.mcp.server",
        "run_task": "iaglobal.mcp.server",
        "get_status": "iaglobal.mcp.server",
        "get_history": "iaglobal.mcp.server",
        "web_search": "iaglobal.mcp.server",
        "web_fetch": "iaglobal.mcp.server",
        "read_file": "iaglobal.mcp.server",
        "write_file": "iaglobal.mcp.server",
        "list_dir": "iaglobal.mcp.server",
        "execute_code": "iaglobal.mcp.server",
        "evolution_status": "iaglobal.mcp.server",
        "evolve_strategy": "iaglobal.mcp.server",
        "evolution_dashboard": "iaglobal.mcp.server",
        "reflexion_fix": "iaglobal.mcp.server",
        "reflexion_loop": "iaglobal.mcp.server",
        "get_error_history": "iaglobal.mcp.server",
        "MCPAgent": "iaglobal.mcp.mcp_agent",
        "MCPDiscovery": "iaglobal.mcp.discovery",
    }
    if name in module_map:
        mod = importlib.import_module(module_map[name])
        return getattr(mod, name)
    raise AttributeError(f"module 'iaglobal.mcp' has no attribute {name!r}")
