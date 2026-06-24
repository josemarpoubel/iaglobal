# iaglobal/execution/executor.py

"""Minimal executor module - provides blackjack_executar_local wrapper."""

import requests
from typing import Optional


def blackjack_executar_local(modelo: str, prompt: str) -> str:
    """Execute LLM call via Ollama (wrapper for backward compatibility)."""
    from iaglobal.providers.provider_config import ProviderConfig
    
    url = ProviderConfig.OLLAMA_URL.rstrip("/") + "/api/generate"
    model_name = modelo or ProviderConfig.DEFAULT_OLLAMA_MODEL
    
    if "/" in model_name:
        model_name = ProviderConfig.DEFAULT_OLLAMA_MODEL
    
    try:
        r = requests.post(
            url,
            json={"model": model_name, "prompt": prompt, "stream": False},
            timeout=600
        )
        r.raise_for_status()
        return r.json().get("response", "")
    except Exception as e:
        from iaglobal.utils.logger import logger
        logger.warning(f"[Ollama] {e}")
        return ""


async def executar(modelo: str, payload: dict) -> str:
    """Router unified execution - delegates to provider router."""
    from iaglobal.providers.provider_router import route_generate
    
    model = (modelo or "").lower().strip()
    prompt = payload.get("task") or payload.get("prompt") or ""
    
    if not model or model == "auto":
        result = await route_generate("", prompt, task_type="general")
        return result
    
    # Fallback to local for non-auto models
    return blackjack_executar_local(model, prompt)