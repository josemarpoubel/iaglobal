"""
FastAPI + ReactPy App para IAGLOBAL
====================================
Versão standalone (sem Django) usando FastAPI + Uvicorn.
"""

from pathlib import Path
from reactpy import component, html
from reactpy.backend.fastapi import configure as reactpy_configure, Options
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn

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


# Configurar ReactPy PRIMEIRO, antes de qualquer outra rota
reactpy_configure(app, AgentDashboard, Options(url_prefix="/@"))


# Servir arquivos estáticos do resultado
RESULTS_DIR = Path(__file__).parent.parent / "memory" / "data" / "result"
if RESULTS_DIR.exists():
    app.mount("/result", StaticFiles(directory=str(RESULTS_DIR)), name="result")


@app.get("/")
async def root():
    """Redireciona para o dashboard ReactPy."""
    return HTMLResponse(content='''
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="refresh" content="0; url=/@/AgentDashboard">
        <title>Redirecting...</title>
    </head>
    <body>
        <p>Redirecting to <a href="/@/AgentDashboard">Dashboard</a>...</p>
    </body>
    </html>
    ''')


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
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
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
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
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
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
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
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the ReactPy FastAPI server."""
    print(f"🚀 Starting IAGLOBAL UI server on http://{host}:{port}")
    print(f"📊 Dashboard: http://{host}:{port}/@/AgentDashboard")
    print(f"📁 Results: http://{host}:{port}/result")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()