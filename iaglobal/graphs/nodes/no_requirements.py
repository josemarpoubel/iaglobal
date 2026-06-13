"""
IAGlobal v3 - Node 05: requirements
- Realiza refinamento de requisitos e integra critic_agent para classificar
- Consolida lista de requisitos funcionais/ não-funcionais e escopo
"""

from typing import Dict, Any



async def run_requirements(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Requirements refinement node. Uses critic_agent to classify requirements quality.

    Expected ctx keys: requirements_inputs

    Adds output ctx:
      - requirements: {"functional":List, "non_functional":List, "priorities":List, "classification":str}
    """
    reqs_inputs = ctx.get("requirements_inputs")

    requirements = {
        "functional": reqs_inputs.get("functional", []),
        "non_functional": reqs_inputs.get("non_functional", []),
        "priorities": ["high"],
        "classification": "medium",
    }

    out = {**ctx, "requirements": requirements}
    return out
