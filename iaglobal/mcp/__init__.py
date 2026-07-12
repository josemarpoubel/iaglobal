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

from iaglobal.mcp.server import (
    mcp,
    run_server,
    run_http_server,
    get_app,
    metabolic_audit,
    get_ivm,
    run_task,
    get_status,
    get_history,
    web_search,
    web_fetch,
    read_file,
    write_file,
    list_dir,
    execute_code,
    evolution_status,
    evolve_strategy,
    evolution_dashboard,
    reflexion_fix,
    reflexion_loop,
    get_error_history,
)

from iaglobal.mcp.mcp_agent import MCPAgent
from iaglobal.mcp.discovery import MCPDiscovery

__all__ = [
    # Servidor unificado
    "mcp",
    "run_server",
    "run_http_server",
    "get_app",
    # Tools metabólicas
    "metabolic_audit",
    "get_ivm",
    # Tools IAGlobal API
    "run_task",
    "get_status",
    "get_history",
    # Tools Web
    "web_search",
    "web_fetch",
    # Tools File System
    "read_file",
    "write_file",
    "list_dir",
    # Tools Code Execution
    "execute_code",
    # Tools Evolution
    "evolution_status",
    "evolve_strategy",
    "evolution_dashboard",
    # Tools Glutationa (Auto-cura)
    "reflexion_fix",
    "reflexion_loop",
    "get_error_history",
    # Agente
    "MCPAgent",
    # Descoberta
    "MCPDiscovery",
]