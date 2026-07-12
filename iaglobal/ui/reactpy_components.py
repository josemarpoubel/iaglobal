"""
ReactPy Components para IAGLOBAL
=================================
Componentes reativos que permitem visualização dinâmica dos agentes,
métricas e knowledge base em tempo real via WebSockets.
"""

import asyncio
from typing import Any, Dict, List, Optional
from reactpy import component, html, use_state, use_effect, use_callback
import httpx2

# Design tokens metabólicos
DARK_THEME = {
    "bg_primary": "#0f0f23",
    "bg_secondary": "#1a1a2e",
    "bg_card": "#16213e",
    "accent": "#ff6b6b",
    "accent_green": "#00ff88",
    "accent_yellow": "#ffcc00",
    "accent_red": "#ff4444",
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
__all__ = ["AgentCard", "MetricsDashboard", "RestaurantMenuPage", "RestaurantProductCard", "EntropyDashboard"]


@component
def EntropyDashboard():
    """Dashboard reativo de entropia dos agentes."""
    
    async def fetch_entropy_state():
        """Busca estado entrópico do health endpoint."""
        try:
            async with httpx2.AsyncClient(timeout=5.0) as client:
                resp = await client.get("http://localhost:8000/health")
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("immune_state", {}).get("entropia", {})
        except Exception as e:
            return {"error": str(e)}
        return {}
    
    state, set_state = use_state({"loading": True, "data": {}})
    
    async def refresh():
        data = await fetch_entropy_state()
        set_state({"loading": False, "data": data})
    
    use_effect(refresh, dependencies=[])
    
    data = state["data"]
    loading = state["loading"]
    
    if loading:
        return html.div({"style": {"color": DARK_THEME["text_light"], "padding": "2rem"}},
            "Carregando entropia...")
    
    if "error" in data:
        return html.div({"style": {"color": DARK_THEME["accent_red"], "padding": "2rem"}},
            f"Erro: {data['error']}")
    
    total = data.get("total_profiles", 0)
    at_risk = data.get("agents_at_apoptosis_risk", 0)
    degrading = data.get("agents_degrading", 0)
    threshold = data.get("apoptosis_threshold", 0.8)
    min_exec = data.get("min_executions", 30)
    
    # Calcula status
    risk_percent = (at_risk / total * 100) if total > 0 else 0
    status_color = DARK_THEME["accent_green"] if risk_percent < 10 else DARK_THEME["accent_yellow"] if risk_percent < 30 else DARK_THEME["accent_red"]
    
    return html.div({"style": {
        "background": DARK_THEME["bg_secondary"],
        "color": DARK_THEME["text_light"],
        "padding": "1.5rem",
        "borderRadius": "8px",
        "margin": "1rem",
        "border": f"2px solid {status_color}",
    }},
        html.h2({"style": {"color": DARK_THEME["accent"], "marginBottom": "1rem"}},
            "🔥 Dashboard de Entropia"),
        
        # Cards de métricas
        html.div({"style": {
            "display": "grid",
            "gridTemplateColumns": "repeat(auto-fit, minmax(150px, 1fr))",
            "gap": "1rem",
            "marginBottom": "1.5rem",
        }},
            html.div({"style": {"background": DARK_THEME["bg_card"], "padding": "1rem", "borderRadius": "6px"}},
                html.div({"style": {"fontSize": "0.85rem", "color": DARK_THEME["text_dim"]}}, "Total Perfis"),
                html.div({"style": {"fontSize": "2rem", "fontWeight": "bold"}}, str(total)),
            ),
            html.div({"style": {"background": DARK_THEME["bg_card"], "padding": "1rem", "borderRadius": "6px"}},
                html.div({"style": {"fontSize": "0.85rem", "color": DARK_THEME["text_dim"]}}, "Em Risco"),
                html.div({"style": {"fontSize": "2rem", "fontWeight": "bold", "color": DARK_THEME["accent_red"] if at_risk > 0 else DARK_THEME["accent_green"]}},
                    str(at_risk)),
            ),
            html.div({"style": {"background": DARK_THEME["bg_card"], "padding": "1rem", "borderRadius": "6px"}},
                html.div({"style": {"fontSize": "0.85rem", "color": DARK_THEME["text_dim"]}}, "Degradando"),
                html.div({"style": {"fontSize": "2rem", "fontWeight": "bold", "color": DARK_THEME["accent_yellow"] if degrading > 0 else DARK_THEME["accent_green"]}},
                    str(degrading)),
            ),
        ),
        
        # Barra de progresso de risco
        html.div({"style": {"marginBottom": "1.5rem"}},
            html.div({"style": {"fontSize": "0.85rem", "color": DARK_THEME["text_dim"], "marginBottom": "0.5rem"}},
                f"Agentes em Risco de Apoptose: {risk_percent:.1f}%"),
            html.div({"style": {
                "background": DARK_THEME["bg_primary"],
                "borderRadius": "4px",
                "height": "20px",
                "overflow": "hidden",
            }},
                html.div({"style": {
                    "background": status_color,
                    "width": f"{risk_percent}%",
                    "height": "100%",
                    "transition": "width 0.3s ease",
                }}),
            ),
        ),
        
        # Configurações
        html.div({"style": {
            "display": "grid",
            "gridTemplateColumns": "1fr 1fr",
            "gap": "1rem",
            "fontSize": "0.85rem",
        }},
            html.div({"style": {"color": DARK_THEME["text_dim"]}},
                "Threshold de Apoptose: ",
                html.span({"style": {"color": DARK_THEME["text_light"], "fontWeight": "bold"}},
                    f"{threshold:.0%}"),
            ),
            html.div({"style": {"color": DARK_THEME["text_dim"]}},
                "Mínimo Execuções: ",
                html.span({"style": {"color": DARK_THEME["text_light"], "fontWeight": "bold"}},
                    str(min_exec)),
            ),
        ),
        
        # Botão de refresh
        html.button({
            "onClick": lambda event: refresh(),
            "style": {
                "background": DARK_THEME["accent"],
                "color": "#fff",
                "border": "none",
                "padding": "0.75rem 1.5rem",
                "borderRadius": "6px",
                "cursor": "pointer",
                "marginTop": "1.5rem",
                "fontSize": "0.9rem",
            },
        }, "🔄 Atualizar"),
    )