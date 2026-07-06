"""
ASGI application para IAGLOBAL (modo produção - sem reload).
Servidor MCP + FastAPI otimizado para integração com OpenCode.
"""

from fastapi import FastAPI
from starlette.types import Scope, Receive, Send
from iaglobal.server.mcp_server import mcp_server

# Criar aplicação FastAPI base
app = FastAPI(title="IAGlobal MCP + API", version="0.1.0")

# Montar MCP Server na rota /mcp
app.mount("/mcp", mcp_server.app)

# Endpoint de root
@app.get("/")
async def root():
    return {
        "service": "iaglobal",
        "endpoints": {
            "/": "Bem-vindo ao MCP",
            "/mcp/health": "Health check do MCP",
            "/mcp/audit": "Auditoria metabólica",
            "/mcp/fix": "Acionar correção",
            "/mcp/jsonrpc": "JSON-RPC endpoint"
        }
    }

# ASGI app
async def asgi_app(scope: Scope, receive: Receive, send: Send) -> None:
    await app(scope, receive, send)

application = asgi_app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "iaglobal.asgi:application",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=False
    )