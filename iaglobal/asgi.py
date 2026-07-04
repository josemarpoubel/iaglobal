"""
ASGI application para IAGLOBAL
===============================
Servidor MCP + FastAPI (puro) em uma única aplicação.
"""

from fastapi import FastAPI
from starlette.types import Scope, Receive, Send
from iaglobal.server.mcp_server import mcp_server

# Criar aplicação FastAPI base
app = FastAPI(title="IAGlobal MCP + API", version="0.1.0")

# Montar MCP Server na rota /mcp
app.mount("/mcp", mcp_server.app)

# Middleware para logar requisições
@app.middleware("http")
async def log_requests(request, call_next):
    from iaglobal.utils.logger import logger
    logger.info(f"⚡ Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"✅ Response: {response.status_code}")
    return response

# Endpoint de root
@app.get("/")
async def root():
    return {
        "service": "iaglobal",
        "endpoints": {
            "/": "Bem-vindo ao MCP",
            "/health": "Status do sistema",
            "/mcp/health": "Health check do MCP",
            "/mcp/audit": "Auditoria metabólica",
            "/mcp/fix": "Acionar correção",
            "/mcp/jsonrpc": "JSON-RPC endpoint (compatibilidade)"
        }
    }

# ASGI app
async def asgi_app(scope: Scope, receive: Receive, send: Send) -> None:
    await app(scope, receive, send)

application = asgi_app

if __name__ == "__main__":
    import uvicorn
    print("🚀 Iniciando MCP Server + API em http://localhost:8000")
    print("🔮 Endpoints MCP disponíveis em http://localhost:8000/mcp")
    uvicorn.run(
        "iaglobal.asgi:application",
        host="0.0.0.0",
        port=8000,
        reload=True,
        access_log=True
    )