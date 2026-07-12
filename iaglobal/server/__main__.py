# iaglobal/server/__main__.py
"""Entry point para iniciar o MCP Server diretamente."""

from iaglobal.server.mcp_server import mcp_server

if __name__ == "__main__":
    print("🔮 Iniciando MCP Server em http://127.0.0.1:8100")
    mcp_server.start_blocking(host="127.0.0.1", port=8100)