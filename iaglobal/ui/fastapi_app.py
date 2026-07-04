"""
FastAPI + ReactPy App para IAGLOBAL
====================================
Versão standalone (sem Django) usando FastAPI + Uvicorn.
"""

from pathlib import Path
from reactpy import component, html
from reactpy.backend.fastapi import configure as reactpy_configure
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

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


# Configure ReactPy no FastAPI (usa route padrão)
try:
    reactpy_configure(app, AgentDashboard)
except AttributeError:
    # Fallback para versões mais recentes do FastAPI
    from reactpy.backend.fastapi import Options
    options = Options()
    reactpy_configure(app, AgentDashboard, options=options)

# Servir arquivos estáticos do resultado
RESULTS_DIR = Path(__file__).parent.parent / "memory" / "data" / "result"
if RESULTS_DIR.exists():
    app.mount("/result", StaticFiles(directory=str(RESULTS_DIR)), name="result")


@app.get("/")
async def root():
    """Redireciona para o dashboard ReactPy."""
    return {"message": "IAGLOBAL UI", "dashboard": "/@/AgentDashboard"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "iaglobal-ui"}


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the ReactPy FastAPI server."""
    print(f"🚀 Starting IAGLOBAL UI server on http://{host}:{port}")
    print(f"📊 Dashboard: http://{host}:{port}/@/AgentDashboard")
    print(f"📁 Results: http://{host}:{port}/result")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()