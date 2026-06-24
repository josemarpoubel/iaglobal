# iaglobal/evolution/skills/reactpy_skill_registry.py
"""
ReactPy Skill Registry
======================
Skills pré-definidas para geração automática de componentes ReactPy.
"""

from typing import Dict, Any, Optional
from iaglobal.evolution.skills.skill import Skill, ExecutionPolicy
from iaglobal.utils.logger import logger


def _create_agent_card() -> Skill:
    """Skill para gerar AgentCard component."""
    async def run_agent_card(task: str, contexto: str = "") -> Dict[str, Any]:
        code = '''
from reactpy import component, html

@component
def AgentCard(agent_name: str, status: str = "idle", metrics: dict = None):
    """Card de agente com status e métricas."""
    return html.div({
        "className": "agent-card",
        "style": {
            "background": "#16213e",
            "border": "1px solid #ff6b6b",
            "borderRadius": "8px",
            "padding": "1rem",
        }
    }, [
        html.h3({"style": {"color": "#ff6b6b"}}, agent_name),
        html.span({"style": {"color": "#00ff88"}}, f"Status: {status}"),
    ])
'''
        return {"code": code, "files": {"agent_card.py": code}}
    
    return Skill(
        name="reactpy_agent_card",
        version="1.0.0",
        description="Gera componente ReactPy para visualização de agente",
        inputs=["task"],
        outputs=["component", "code"],
        constraints=["dark-theme", "async"],
        run_fn=run_agent_card,
        tags=["reactpy", "ui", "agent"],
    )


def _create_dashboard() -> Skill:
    """Skill para gerar Dashboard completo."""
    async def run_dashboard(task: str, contexto: str = "") -> Dict[str, Any]:
        code = '''
from reactpy import component, html

@component
def AgentDashboard():
    """Dashboard dos agentes IAGLOBAL."""
    return html.div({
        "style": {
            "background": "linear-gradient(135deg, #0f0f23, #1a1a2e)",
            "minHeight": "100vh",
            "padding": "2rem",
            "color": "#e8e8ff",
        }
    }, [
        html.h1({"style": {"color": "#ff6b6b"}}, "IAGLOBAL Dashboard"),
        html.p("Agentes em operação..."),
    ])
'''
        return {"code": code, "files": {"dashboard.py": code}}
    
    return Skill(
        name="reactpy_dashboard", 
        version="1.0.0",
        description="Gera dashboard ReactPy completo",
        inputs=["task"],
        outputs=["component", "code"],
        constraints=["dark-theme"],
        run_fn=run_dashboard,
        tags=["reactpy", "dashboard", "ui"],
    )


REACTPY_SKILLS = {
    "reactpy_agent_card": _create_agent_card(),
    "reactpy_dashboard": _create_dashboard(),
}