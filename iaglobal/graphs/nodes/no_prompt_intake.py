"""
IAGlobal v3 - Node 01: prompt_intake
- Recebe prompt bruto do usuário, normaliza e injeta no sistema
- Faz parser inicial de intenção, contexto e escopo
- Resultado: dicionário structureado que alimenta enhancement
"""

from typing import Dict, Any


async def run_prompt_intake(ctx: Dict[str, Any]) -> Dict[str, Any]:
    raw = ctx.get("raw_prompt") or ctx.get("input", {}).get("task", "")
    if not raw or not isinstance(raw, str):
        raw = str(ctx.get("input", {}).get("task", ""))
    if not raw:
        return {**ctx, "prompt": {"raw": "", "normalized": "", "tokens": 0, "intents": []}, "initial_scope": {"phase": "definition"}}

    normalized = raw.strip()

    # TBD: intents, entities parser (will be enhanced in enhancement node)
    prompt_def = {
        "raw": raw,
        "normalized": normalized,
        "tokens": len(normalized.split()),
        "intents": ["unknown"],
    }

    out = {**ctx, "prompt": prompt_def, "initial_scope": {"phase": "definition"}}
    return out
