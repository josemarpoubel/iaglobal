# iaglobal/mcp/placeholder.py
"""
MCPPlaceholder — Fallback quando FastMCP não está instalado.

Módulo compartilhado para evitar duplicação entre mcp_server.py e server.py.
"""

import logging

logger = logging.getLogger(__name__)


class MCPPlaceholder:
    """Placeholder quando FastMCP não está instalado."""

    def __init__(self, *args, **kwargs):
        pass

    def tool(self, *args, **kwargs):
        def decorator(f):
            return f

        return decorator

    async def run(self, *args, **kwargs):
        logger.error("FastMCP não instalado. Execute: pip install mcp")
        return
