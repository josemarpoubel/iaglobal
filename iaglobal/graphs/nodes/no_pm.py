"""
IAGlobal v3 - Node 04: pm (Project Manager / Requirement Finetuning)
- Responsável por detalhar requisitos funcionais do projeto
- Integra uso de critic_agent pra classificações iniciais
- Produz requirements_inputs e escopo detalhado
"""

from typing import Dict, Any


async def run_pm(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Project Manager node. Elaborates requirements and refines scope.

    Expected ctx keys: enhancement, prompt

    Adds to output ctx:
      - requirements_inputs: Dict
    """
    enhancement = ctx.get("enhancement") or {}
    req_inputs = {
        "functional": [],
        "non_functional": [],
        "priority": "medium",
        "drivers": enhancement.get("intents_detected", []),
    }

    out = {**ctx, "requirements_inputs": req_inputs}
    return out
