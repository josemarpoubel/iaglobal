"""
IAGlobal v3 - Node 02: enhancement
- Analisa e enriquece o prompt normalizado (melhora intenções, entidades, escopo)
- Realiza parse de contexto para definir requisitos e escopo
- Injeta instruções de especialização via MetaAgentDesigner se aplicável
"""

from typing import Dict, Any


async def run_enhancement(ctx: Dict[str, Any]) -> Dict[str, Any]:
    prompt = ctx.get("prompt")
    if not prompt or not isinstance(prompt, dict) or not prompt.get("normalized"):
        task = str(ctx.get("input", {}).get("task", ""))
        prompt = {"raw": task, "normalized": task, "tokens": len(task.split()), "intents": ["unknown"]}

    raw = prompt["normalized"]
    # TBD: real intent/entity parser; stub
    intents = ["analysis", "planning"]
    entities = []

    enhancement_def = {
        "intents_detected": intents,
        "entities": entities,
        "scope": {
            "phases": ["definition"],
            "complexity": "medium",
        },
        "specialization_instructions": None,
    }

    out = {**ctx, "enhancement": enhancement_def}
    return out
