# iaglobal/providers/nvidia_provider.py

from typing import Optional

from iaglobal.providers.async_http import get_sync_session
from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.providers.token_usage import TokenCollector
from iaglobal.memory import cache
from iaglobal.utils.logger import logger


def generate(
    prompt: str,
    model: str = "nvidia/mistralai/mistral-small-4-119b-2603",
    timeout: int = 60,
    token_collector: Optional[TokenCollector] = None
) -> str:

    model = model.replace("nvidia/", "").strip()

    if not ProviderConfig.NVIDIA_API_KEY:
        logger.debug(f"[NVIDIA Provider] API key not set, skipping")
        return ""

    cache_key = f"nvidia:{model}:{prompt}"

    cached = cache.get(cache_key)
    if cached:
        return cached

    url = "https://integrate.api.nvidia.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {ProviderConfig.NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 2048,
        "stream": False,
    }

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

        cache.set(cache_key, result)
        return result

    except Exception as e:
        logger.warning(f"[NVIDIA Provider] {e}")
        return ""


async def async_generate(prompt: str, model: str = "nvidia/mistralai/mistral-small-4-119b-2603", timeout: int = 60, token_collector: Optional[TokenCollector] = None) -> str:
    from iaglobal.providers.async_http import async_post
    api_key = ProviderConfig.NVIDIA_API_KEY or ""
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    model_clean = model.replace("nvidia/", "").strip()
    payload = {"model": model_clean, "messages": [{"role": "user", "content": prompt}], "stream": False}
    headers = {"Authorization": f"Bearer {api_key}"}
    return await async_post(url, payload, headers=headers, timeout=timeout)
