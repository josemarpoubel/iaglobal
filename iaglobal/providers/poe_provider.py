# iaglobal/providers/poe_provider.py

from typing import Optional

from iaglobal.providers.async_http import get_sync_session
from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.providers.token_usage import TokenCollector
from iaglobal.memory import cache
from iaglobal.utils.logger import logger


def generate(
    prompt: str,
    model: str = "poe/GLM-5-T",
    timeout: int = 180,
    token_collector: Optional[TokenCollector] = None
) -> str:

    model = model.replace("poe/", "").strip()
    api_key = ProviderConfig.POE_API_KEY
    if not api_key:
        logger.debug("[POE] API key not set")
        return ""

    cache_key = f"poe:{model}:{prompt}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    url = "https://api.poe.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        response = get_sync_session().post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        usage = data.get("usage")
        if usage and token_collector:
            pt = usage.get("prompt_tokens", 0)
            ct = usage.get("completion_tokens", 0)
            token_collector(pt, ct)

        result = (
            data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
        )
        if result:
            cache.set(cache_key, result)
        return result

    except Exception as e:
        logger.warning(f"[POE] {e}")
        return ""


async def async_generate(
    prompt: str,
    model: str = "poe/GLM-5-T",
    timeout: int = 180,
    token_collector: Optional[TokenCollector] = None
) -> str:
    from iaglobal.providers.async_http import async_post
    api_key = ProviderConfig.POE_API_KEY or ""
    model_clean = model.replace("poe/", "").strip()
    url = "https://api.poe.com/v1/chat/completions"
    payload = {"model": model_clean, "messages": [{"role": "user", "content": prompt}], "stream": False}
    headers = {"Authorization": f"Bearer {api_key}"}
    return await async_post(url, payload, headers=headers, timeout=timeout)
