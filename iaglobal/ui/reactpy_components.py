"""
ReactPy Components para IAGLOBAL
=================================
Componentes reativos que permitem visualização dinâmica dos agentes,
métricas e knowledge base em tempo real via WebSockets.
"""

from typing import Any, Dict, List, Optional
from reactpy import component, html, use_state, use_effect

# Design tokens metabólicos
DARK_THEME = {
    "bg_primary": "#0f0f23",
    "bg_secondary": "#1a1a2e",
    "bg_card": "#16213e",
    "accent": "#ff6b6b",
    "text_light": "#e8e8ff",
    "text_dim": "#a8a8c8",
}


@component
def AgentCard(agent_name: str, status: str = "idle", metrics: Optional[Dict] = None):
    """Card reativo de agente com métricas em tempo real."""
    state, set_state = use_state({"status": status, "metrics": metrics or {}})
    
    async def refresh_metrics():
        # Hook para buscar métricas via WebSocket
        pass
    
    return html.div(
        {"className": "agent-card", "style": {
            "background": DARK_THEME["bg_card"],
            "border": f"1px solid {DARK_THEME['accent']}",
            "borderRadius": "8px",
            "padding": "1rem",
            "margin": "0.5rem",
        }},
        html.h3({"style": {"color": DARK_THEME["accent"], "marginBottom": "0.5rem"}}, agent_name),
        html.span({"style": {
            "color": "#00ff88" if state["status"] == "active" else DARK_THEME["text_dim"],
            "fontSize": "0.85rem",
        }}, f"Status: {state['status']}"),
        html.pre({
            "style": {
                "background": DARK_THEME["bg_primary"],
                "color": DARK_THEME["text_light"],
                "padding": "0.5rem",
                "borderRadius": "4px",
                "fontSize": "0.75rem",
                "marginTop": "0.5rem",
                "maxHeight": "100px",
                "overflow": "auto",
            }
        }, str(state["metrics"])),
    )


@component
def MetricsDashboard(agents: Optional[List[Dict]] = None):
    """Dashboard reativo com métricas dos agentes."""
    agents_list = agents or []
    
    return html.div(
        {"style": {
            "background": DARK_THEME["bg_secondary"],
            "minHeight": "100vh",
            "padding": "1rem",
            "color": DARK_THEME["text_light"],
            "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        }},
        html.h1({"style": {"color": DARK_THEME["accent"], "marginBottom": "1rem"}}, 
                "🧠 IAGLOBAL Agent Dashboard"),
        html.div(
            {"style": {
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(300px, 1fr))",
                "gap": "1rem",
            }},
            *[AgentCard(**agent) for agent in agents_list] if agents_list else [
                AgentCard(agent_name="CoderAgent", status="idle"),
                AgentCard(agent_name="KnowledgeWriter", status="active"),
                AgentCard(agent_name="HomeostasisController", status="monitoring"),
            ]
        ),
    )


@component  
def RestaurantProductCard(name: str, price: str, category: str = "dishes"):
    """Card de produto do restaurante - versão reativa."""
    return html.div(
        {"className": "product-card", "style": {
            "background": DARK_THEME["bg_card"],
            "border": f"1px solid {DARK_THEME['accent']}",
            "borderRadius": "8px",
            "padding": "1rem",
            "margin": "0.5rem 0",
            "transition": "transform 0.2s",
        }},
        html.h3({"style": {"color": DARK_THEME["text_light"], "marginBottom": "0.25rem"}}, name),
        html.p({"className": "price", "style": {
            "color": DARK_THEME["accent"],
            "fontWeight": "bold",
            "margin": "0.25rem 0",
        }}, f"R$ {price}"),
        html.button({
            "style": {
                "background": DARK_THEME["accent"],
                "color": "#fff",
                "border": "none",
                "padding": "0.5rem 1rem",
                "borderRadius": "4px",
                "cursor": "pointer",
            },
            "onClick": lambda e: None,
        }, "Adicionar ao Pedido"),
    )


@component
def RestaurantMenuPage():
    """Página do menu do restaurante - versão reativa ReactPy."""
    return html.div(
        {"style": {
            "background": f"linear-gradient(135deg, {DARK_THEME['bg_primary']} 0%, {DARK_THEME['bg_secondary']} 100%)",
            "minHeight": "100vh",
            "padding": "1rem",
        }},
        html.header({
            "style": {
                "background": DARK_THEME["bg_card"],
                "padding": "1rem",
                "borderBottom": f"2px solid {DARK_THEME['accent']}",
                "position": "sticky",
                "top": 0,
            }
        },
            html.h1({"style": {"color": DARK_THEME["accent"]}}, "Restaurante Sabor do Dia"),
        ),
        html.main({"style": {"maxWidth": "800px", "margin": "0 auto"}},
            html.section({},
                html.h2({"style": {"color": DARK_THEME["text_light"]}}, "Pratos do Dia"),
                RestaurantProductCard(name="Lasanha à Bolonhesa", price="32,90"),
                RestaurantProductCard(name="Filé Mignon", price="45,90"),
                RestaurantProductCard(name="Salada Caesar", price="28,90"),
            ),
            html.section({},
                html.h2({"style": {"color": DARK_THEME["text_light"], "marginTop": "2rem"}}, "Bebidas"),
                RestaurantProductCard(name="Coca-Cola 350ml", price="8,50"),
                RestaurantProductCard(name="Suco Natural", price="12,90"),
            ),
            html.section({},
                html.h2({"style": {"color": DARK_THEME["text_light"], "marginTop": "2rem"}}, "Sobremesas"),
                RestaurantProductCard(name="Petit Gateau", price="18,90"),
            ),
        ),
    )


# Exportar componentes para uso em views Django
__all__ = ["AgentCard", "MetricsDashboard", "RestaurantMenuPage", "RestaurantProductCard"]