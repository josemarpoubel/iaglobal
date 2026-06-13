"""Multi-coder paralelo — gera backend, frontend e database em paralelo."""
from typing import Dict, Any, List, Tuple
import asyncio
import logging

from iaglobal.providers.provider_router import async_route_generate
from iaglobal.memory.memory_error import record_error

logger = logging.getLogger(__name__)

_PARTS = [
    ("backend", "backend", "Gere APENAS o codigo do BACKEND (API, rotas, servidor)"),
    ("frontend", "frontend", "Gere APENAS o codigo do FRONTEND (interface, componentes)"),
    ("database", "database", "Gere APENAS o codigo do BANCO DE DADOS (models, migracoes, schema)"),
]

_ACTIVE_PROVIDERS = [
    "ollama/qwen2.5:0.5b",
    "openrouter/meta-llama/llama-3.1-8b-instruct",
    "nvidia/mistralai/mistral-small-4-119b-2603",
    "gemini/gemini-2.5-flash-lite",
]


async def _generate_part(part_key: str, part_label: str, instruction: str, prompt: str, model: str) -> Tuple[str, str, str]:
    system = "Você eh um engenheiro de software especialista."
    full_prompt = f"{system}\n\n{prompt}\n\n{instruction}\n\nGere APENAS codigo, sem explicacoes."
    try:
        code = await async_route_generate(model=model, prompt=full_prompt, task_type="coding")
        if code and len(code) > 30:
            logger.info("[MULTI_CODER] %s OK: %d chars (model=%s)", part_label, len(code), model)
            return (part_key, code, "")
        logger.debug("[MULTI_CODER] %s vazio", part_label)
        return (part_key, "", f"{part_label} empty")
    except Exception as e:
        logger.warning("[MULTI_CODER] %s falhou: %s", part_label, e)
        return (part_key, "", str(e))


async def run_multi_coder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    prompt_builder_data = memory.get("prompt_builder", {})

    built_prompt = prompt_builder_data.get("built_prompt", "") or prompt_builder_data.get("output", "")
    if not built_prompt:
        built_prompt = str(ctx.get("input", {}).get("task", ""))

    if not built_prompt or len(built_prompt) < 10:
        logger.warning("[MULTI_CODER] Prompt vazio, repassando coder output")
        coder_out = memory.get("coder", {}).get("output", "")
        return {**ctx, "output": coder_out, "multi_coder": {"status": "passthrough"}}

    tasks = []
    for i, (key, label, instruction) in enumerate(_PARTS):
        model = _ACTIVE_PROVIDERS[i % len(_ACTIVE_PROVIDERS)]
        tasks.append(_generate_part(key, label, instruction, built_prompt, model))

    logger.info("[MULTI_CODER] Gerando %d partes em paralelo...", len(tasks))
    results = await asyncio.gather(*tasks)

    parts = {}
    all_code = []
    failures = 0
    for key, code, error in results:
        parts[key] = code
        if code:
            all_code.append(f"# === {key.upper()} ===\n{code}")
        else:
            failures += 1

    multi_output = "\n\n".join(all_code) if all_code else ""
    status = "partial" if failures > 0 and failures < len(_PARTS) else ("full" if failures == 0 else "failed")

    logger.info("[MULTI_CODER] Status=%s, %d/%d partes, %d chars total",
                status, len(_PARTS) - failures, len(_PARTS), len(multi_output))

    if failures == len(_PARTS):
        record_error("multi_coder", "Todas as partes falharam", {"prompt_len": len(built_prompt)})

    return {
        **ctx,
        "output": multi_output,
        "multi_coder": {
            "status": status,
            "parts": parts,
            "total_chars": len(multi_output),
            "failures": failures,
        },
    }
