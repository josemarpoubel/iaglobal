"""
IAGlobal v3 - Node 03: orchestrator_agent
- Orquestra a execução dos nós seguintes baseando-se no enhancement e escopo
- Decision node que roteia contexto entre phases e dispara cohortes de nós
"""

from typing import Dict, Any


async def run_orchestrator_agent(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrates downstream nodes based on enhanced context.

    Decides which phase cohort to activate next and propagates context.

    Output adds:
      - orchestration: { "next_phase": str , "active_nodes": List[str] }
    """
    enhancement = ctx.get("enhancement") or {}
    scope = enhancement.get("scope") or {}

    next_phase = scope.get("phases") and scope["phases"][0] if scope.get("phases") else "definition"
    orch = {
        "next_phase": next_phase,
        "active_nodes": [
            "pm",
            "requirements",
            "domain_analysis",
        ],
    }

    out = {**ctx, "orchestration": orch}
    return out
