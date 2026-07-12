# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/mcp/mcp_server.py
"""
FastMCP server — expõe tools metabólicas do iaglobal como servidor MCP.
"""

import logging
from typing import Any

logger = logging.getLogger("iaglobal.mcp")

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None
    logger.warning("FastMCP não disponível — instale 'mcp' para ativar o servidor MCP")

from iaglobal.mcp.mcp_agent import MCPAgent
from iaglobal.mcp.search_web import WebSearchTool
from iaglobal.mcp.file_system import FileSystemTool
from iaglobal.mcp.code_executor import CodeExecutorTool
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.mcp.server")

_agent: MCPAgent | None = None
_web_search: WebSearchTool | None = None
_file_system: FileSystemTool | None = None
_code_exec: CodeExecutorTool | None = None


def _get_agent() -> MCPAgent:
    global _agent
    if _agent is None:
        _agent = MCPAgent()
    return _agent


def _get_web_search() -> WebSearchTool:
    global _web_search
    if _web_search is None:
        _web_search = WebSearchTool()
    return _web_search


def _get_file_system() -> FileSystemTool:
    global _file_system
    if _file_system is None:
        _file_system = FileSystemTool()
    return _file_system


def _get_code_exec() -> CodeExecutorTool:
    global _code_exec
    if _code_exec is None:
        _code_exec = CodeExecutorTool()
    return _code_exec


if FastMCP is not None:

    mcp = FastMCP(
        "iaglobal",
        instructions="""Sistema imunológico evolutivo com ferramentas MCP integradas.

Tools disponíveis:
- metabolic_audit: auditoria metabólica completa
- get_ivm: Índice de Viabilidade Metabólica
- web_search: busca web com cache
- web_fetch: fetch de conteúdo de URL
- read_file: leitura segura de arquivos na whitelist
- write_file: escrita segura de arquivos na whitelist
- list_dir: listagem de diretórios na whitelist
- execute_code: execução de código em sandbox isolado
""",
    )

    @mcp.tool()
    async def metabolic_audit() -> dict:
        """Executa auditoria metabólica completa do sistema."""
        agent = _get_agent()
        audit = await agent.run_audit()
        return {
            "score": audit.score,
            "findings": {k: v["status"] for k, v in audit.findings.items()},
            "corrections": len(audit.corrections),
        }

    @mcp.tool()
    async def get_ivm() -> float:
        """Retorna o Índice de Viabilidade Metabólica atual."""
        return _get_agent()._get_ivm()

    @mcp.tool()
    async def web_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Busca na web e retorna resultados estruturados."""
        return await _get_web_search().search(query, max_results=max_results)

    @mcp.tool()
    async def web_fetch(url: str, timeout: int = 15) -> str | None:
        """Fetch do conteúdo de uma URL."""
        return await _get_web_search().fetch_page(url, timeout=timeout)

    @mcp.tool()
    async def read_file(path: str) -> str | None:
        """Lê arquivo seguro — apenas paths na whitelist."""
        return await _get_file_system().read_file(path)

    @mcp.tool()
    async def write_file(path: str, content: str) -> bool:
        """Escreve arquivo seguro — apenas paths na whitelist."""
        return await _get_file_system().write_file(path, content)

    @mcp.tool()
    async def list_dir(path: str) -> list[str]:
        """Lista diretório — apenas paths na whitelist."""
        return await _get_file_system().list_dir(path)

    @mcp.tool()
    async def execute_code(code: str, language: str = "python") -> dict[str, Any]:
        """Executa código em sandbox isolado com timeout."""
        return await _get_code_exec().execute(code, language=language)

else:

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

    mcp = MCPPlaceholder()


async def run_server(host: str = "0.0.0.0", port: int = 8100):
    """Inicia o servidor MCP via SSE ou stdio."""
    if FastMCP is None:
        logger.error("FastMCP não instalado. Não é possível iniciar o servidor.")
        return
    logger.info("Iniciando servidor MCP iaglobal em %s:%s", host, port)
    await mcp.run_sse(host=host, port=port)