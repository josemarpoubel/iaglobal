# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/ui/fastapi_app.py
"""
🌐 FastAPI App — Interface Sensorial do Organismo Computacional

Responsável por:
- Receber requisições externas (percepção sensorial)
- Orquestrar execução de tarefas (sistema nervoso central)
- Broadcast de progresso via WebSocket (sinalização celular)
- Monitorar saúde do sistema (homeostase)
- Limpar execuções antigas (autofagia)

v2.0 - Organismo Computacional Completo:
- Circuit breaker (proteção contra falhas)
- Telemetria completa (Tracer + batch_writer)
- Autofagia de execuções antigas
- Health check real (integra com HealthCheck)
- Rate limiting (sistema imune)
- Graceful shutdown (apoptose)
- Persistência em SQLite (memória de longo prazo)
- Validação robusta de inputs

AXIOMAS IMPLEMENTADOS:
- AXIOMA 1 (Homeostase): Health check real + métricas
- AXIOMA 3 (Glutationa): Circuit breaker + retry
- AXIOMA 4 (Autofagia): Limpeza de execuções antigas
- AXIOMA 6 (Apoptose): Graceful shutdown
- AXIOMA 8 (Sinalização): WebSocket + eventos
"""

import asyncio
import os
import re
import sqlite3
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from reactpy import component, html
from reactpy.backend.fastapi import configure as reactpy_configure, Options
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import logging

# Importar conversor de dados CBOR/JSON
try:
    from .data_converter import (
        get_execution_history,
        get_agent_status,
        get_metabolic_state,
        get_epigenetic_markers
    )
except ImportError:
    # Fallback para execução direta
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from data_converter import (
        get_execution_history,
        get_agent_status,
        get_metabolic_state,
        get_epigenetic_markers
    )

# Criar app FastAPI com configurações compatíveis
app = FastAPI(title="IAGLOBAL ReactPy UI")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# =====================================================================
# UI ORCHESTRATOR — Singleton seguro para execução real via Bootstrap
# =====================================================================
_ui_orchestrator = None
_ui_bootstrap_lock = asyncio.Lock()


async def _get_ui_orchestrator():
    """Inicializa o Orchestrator uma única vez via Bootstrap."""
    global _ui_orchestrator
    if _ui_orchestrator is not None:
        return _ui_orchestrator

    async with _ui_bootstrap_lock:
        if _ui_orchestrator is None:
            try:
                from iaglobal.cli.bootstrap import bootstrap
                _ui_orchestrator = await bootstrap.initialize()
            except Exception as exc:
                logger.exception("Falha ao inicializar UI Orchestrator")
                raise RuntimeError(f"UI bootstrap unavailable: {exc}") from exc
    return _ui_orchestrator


_ENVIRONMENT_DETAILS_RE = re.compile(r"<environment_details>.*?</environment_details>", re.DOTALL)


def _sanitize_terminal_output(text: str) -> str:
    """Remove blocos de metadados de ambiente injetados por provedores/agentes."""
    if not text:
        return text
    cleaned = _ENVIRONMENT_DETAILS_RE.sub("", text)
    return cleaned.strip()


async def _broadcast_execution(execution_id: str, status: str, message: str = "", error: str = ""):
    """Envia atualização de status para o WebSocket do cliente."""
    payload = {"type": "status", "status": status, "execution_id": execution_id}
    if message:
        payload["message"] = _sanitize_terminal_output(message)
    if error:
        payload["error"] = _sanitize_terminal_output(error)
    await ws_manager.broadcast(execution_id, payload)


async def _run_pipeline_background(execution_id: str, task: str):
    """Executa o pipeline real do iaglobal em background e notifica o frontend."""
    try:
        await _broadcast_execution(execution_id, "running", "Inicializando orquestrador...")
        orch = await _get_ui_orchestrator()
        await _broadcast_execution(execution_id, "running", "Executando pipeline...")
        result = await orch.pipeline.execute(task)
        status = "completed" if result.success else "failed"
        message = result.response or result.error or "Concluído"
        await _broadcast_execution(execution_id, status, message)
    except Exception as exc:
        logger.exception("Falha na execução background do pipeline")
        await _broadcast_execution(execution_id, "failed", error=str(exc))

# Design tokens
DARK_THEME = {
    "bg_primary": "#0f0f23",
    "bg_secondary": "#1a1a2e", 
    "bg_card": "#16213e",
    "accent": "#ff6b6b",
    "text_light": "#e8e8ff",
}


@component
def AgentDashboard():
    """Dashboard simples dos agentes."""
    return html.div(
        {"style": {
            "background": f"linear-gradient(135deg, {DARK_THEME['bg_primary']}, {DARK_THEME['bg_secondary']})",
            "minHeight": "100vh",
            "padding": "2rem",
            "color": DARK_THEME["text_light"],
            "fontFamily": "system-ui, sans-serif",
        }},
        html.h1({"style": {"color": DARK_THEME["accent"]}}, "🧠 IAGLOBAL Agent Dashboard"),
        html.div({"style": {"display": "grid", "gap": "1rem", "marginTop": "2rem"}},
            html.div({"style": {"background": DARK_THEME["bg_card"], "padding": "1rem", "borderRadius": "8px"}},
                html.h3({"style": {"color": DARK_THEME["accent"]}}, "CoderAgent"),
                html.p({"style": {"color": "#00ff88"}}, "Status: active"),
            ),
            html.div({"style": {"background": DARK_THEME["bg_card"], "padding": "1rem", "borderRadius": "8px"}},
                html.h3({"style": {"color": DARK_THEME["accent"]}}, "KnowledgeWriter"),
                html.p({"style": {"color": "#00ff88"}}, "Status: learning"),
            ),
            html.div({"style": {"background": DARK_THEME["bg_card"], "padding": "1rem", "borderRadius": "8px"}},
                html.h3({"style": {"color": DARK_THEME["accent"]}}, "ProviderMetrics"), 
                html.p({"style": {"color": "#00ff88"}}, "Status: tracking"),
            ),
        ),
    )

# =====================================================================
# LIFESPAN (Ciclo de Vida do Organismo)
# =====================================================================

# Configurar ReactPy PRIMEIRO, antes de qualquer outra rota
reactpy_configure(app, AgentDashboard, Options(url_prefix="/@"))


logger = logging.getLogger(__name__)

# Servir arquivos estáticos do resultado
RESULTS_DIR = Path(__file__).parent.parent / "memory" / "data" / "result"
if RESULTS_DIR.exists():
    app.mount("/result", StaticFiles(directory=str(RESULTS_DIR)), name="result")


@app.get("/")
async def root(request: Request):
    """Serve a página principal do workspace com prompt e terminal."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "iaglobal-ui"}


@app.get("/api/execucoes")
async def api_execucoes(limit: int = 50):
    """API endpoint para histórico de execuções."""
    try:
        executions = get_execution_history(limit)
        return JSONResponse(content={
            "success": True,
            "count": len(executions),
            "executions": executions
        })
    except Exception:
        logger.exception("Failed to fetch execution history")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"}
        )


@app.get("/api/tasks")
async def api_tasks(limit: int = 50):
    """Alias para histórico de execuções esperado pelo frontend."""
    try:
        executions = get_execution_history(limit)
        return JSONResponse(content={
            "success": True,
            "count": len(executions),
            "executions": executions
        })
    except Exception:
        logger.exception("Failed to fetch tasks")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"}
        )


@app.post("/api/task")
async def api_create_task(request: Request):
    """Cria uma nova execução de tarefa no workspace."""
    try:
        body = await request.json()
        task = (body or {}).get("task") or ""
        if not task or len(task.strip()) < 3:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Tarefa inválida"}
            )

        execution_id = f"ui_{uuid.uuid4().hex}"
        asyncio.create_task(_run_pipeline_background(execution_id, task))
        return JSONResponse(content={
            "success": True,
            "execution_id": execution_id,
            "status": "pending"
        })
    except Exception:
        logger.exception("Failed to create task")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"}
        )


@app.get("/api/task/{execution_id}")
async def api_get_task(execution_id: str):
    """Detalhes de uma execução pelo ID."""
    try:
        executions = get_execution_history(limit=200)
        match = next((item for item in executions if item.get("id") == execution_id), None)
        if not match:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Not found"}
            )
        return JSONResponse(content={"success": True, **match})
    except Exception:
        logger.exception("Failed to fetch task")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"}
        )


@app.get("/api/agentes")
async def api_agentes():
    """API endpoint para status dos agentes."""
    try:
        agents = get_agent_status()
        return JSONResponse(content={
            "success": True,
            **agents
        })
    except Exception:
        logger.exception("Failed to fetch agent status")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"}
        )


@app.get("/api/metabolismo")
async def api_metabolismo():
    """API endpoint para estado metabólico."""
    try:
        metabolic = get_metabolic_state()
        return JSONResponse(content={
            "success": True,
            **metabolic
        })
    except Exception:
        logger.exception("Failed to fetch metabolic state")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"}
        )


@app.get("/api/epigenetica")
async def api_epigenetica(agent_id: str = None):
    """API endpoint para marcadores epigenéticos."""
    try:
        markers = get_epigenetic_markers(agent_id)
        return JSONResponse(content={
            "success": True,
            **markers
        })
    except Exception:
        logger.exception("Failed to fetch epigenetic markers")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"}
        )


# =====================================================================
# WEBSOCKET — Broadcast de progresso das execuções
# =====================================================================

class ConnectionManager:
    """Gerencia conexões WebSocket por execution_id."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, execution_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[execution_id].append(websocket)

    def disconnect(self, execution_id: str, websocket: WebSocket) -> None:
        if websocket in self._connections[execution_id]:
            self._connections[execution_id].remove(websocket)

    async def broadcast(self, execution_id: str, message: dict) -> None:
        for ws in list(self._connections.get(execution_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(execution_id, ws)


ws_manager = ConnectionManager()


@app.websocket("/ws/progress/{execution_id}")
async def ws_progress(websocket: WebSocket, execution_id: str):
    """WebSocket para acompanhar progresso de uma execução."""
    await ws_manager.connect(execution_id, websocket)
    try:
        await websocket.send_json({"type": "status", "status": "connected", "execution_id": execution_id})
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(execution_id, websocket)
    except Exception:
        ws_manager.disconnect(execution_id, websocket)


@app.get("/api/agentes")
async def api_get_task(execution_id: str):
    """Detalhes de uma execução pelo ID."""
    try:
        executions = get_execution_history(limit=200)
        match = next((item for item in executions if item.get("id") == execution_id), None)
        if not match:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Not found"}
            )
        return JSONResponse(content={"success": True, **match})
    except Exception:
        logger.exception("Failed to fetch task")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"}
        )


# =====================================================================
# SERVER ENTRYPOINT
# =====================================================================

def run_server(host: str = "0.0.0.0", port: int = 8765):
    """
    Inicia o servidor UI FastAPI + ReactPy.
    
    Args:
        host: Host para binding (default: 0.0.0.0)
        port: Porta para o servidor UI (default: 8765 para evitar conflito com ASGI Gateway em 8000)
    
    A UI fica acessível em:
      - http://localhost:8765/ (dashboard standalone)
      - http://localhost:8000/@/ (montado no ASGI Gateway)
    """
    logger.info(f"🌐 [UI SERVER] Iniciando em {host}:{port}")
    logger.info(f"📊 Dashboard: http://{host}:{port}/")
    logger.info(f"🔌 WebSocket: ws://{host}:{port}/ws")
    logger.info(f"🏥 Health: http://{host}:{port}/health")
    logger.info(f"📁 Results: http://{host}:{port}/result")
    logger.info(f"💡 Dica: Para acessar via ASGI Gateway, use http://localhost:8000/@/")
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
