# iaglobal/execution/executor.py

"""Minimal executor module - provides blackjack_executar_local wrapper."""

import os


async def blackjack_executar_local(modelo: str, prompt: str) -> str:
    """Execute LLM call via Ollama (async-safe wrapper)."""
    from iaglobal.providers.provider_config import ProviderConfig
    from iaglobal.providers.async_http import get_session

    url = ProviderConfig.OLLAMA_URL.rstrip("/") + "/api/generate"
    model_name = modelo or ProviderConfig.DEFAULT_OLLAMA_MODEL

    if "/" in model_name:
        model_name = ProviderConfig.DEFAULT_OLLAMA_MODEL

    try:
        session = await get_session()
        async with session.post(
            url,
            json={"model": model_name, "prompt": prompt, "stream": False},
            timeout=600,
        ) as r:
            r.raise_for_status()
            data = await r.json()
            return data.get("response", "")
    except Exception as e:
        from iaglobal.utils.logger import logger

        logger.warning("[Ollama] %s", e)
        return ""


async def executar(modelo: str, payload: dict) -> str:
    """Router unified execution - delegates to provider router."""
    from iaglobal.agents.critic_agent import _get_critic
    from iaglobal.providers.provider_router import route_generate

    model = (modelo or "").lower().strip()
    prompt = payload.get("task") or payload.get("prompt") or ""

    if not model or model == "auto":
        result = await _get_critic().arbitrar_geracao(
            node_id="executor",
            prompt=prompt,
            task_type="general",
        )
        if result:
            return result

        logger.warning(
            "[EXECUTOR] Crítico retornou vazio — fallback para route_generate (critic_batch)"
        )
        return (
            await route_generate(
                "", prompt, task_type="general", node_id="critic_batch"
            )
            or ""
        )

    # Fallback to local for non-auto models
    return await blackjack_executar_local(model, prompt)
