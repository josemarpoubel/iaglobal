# iaglobal/providers/opencode_provider.py

from typing import Optional

from iaglobal.providers.async_http import get_sync_session
from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.providers.token_usage import TokenCollector
from iaglobal.memory import cache
from iaglobal.utils.logger import logger


def generate(
    prompt: str,
    model: str = "opencode/deepseek-v4-flash-free",
    timeout: int = 60,
    token_collector: Optional[TokenCollector] = None
) -> str:

    model = model.replace("opencode/", "").strip()

    if not ProviderConfig.OPENCODE_API_KEY:
        logger.debug(f"[OpenCode Provider] API key not set, skipping")
        return ""

    cache_key = f"opencode:{model}:{prompt}"

    cached = cache.get(cache_key)
    if cached:
        return cached

    url = "https://opencode.ai/zen/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {ProviderConfig.OPENCODE_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    try:
        response = get_sync_session().post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout
        )

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
        logger.warning(f"[OpenCode Provider] {e}")
        return ""


async def async_generate(prompt: str, model: str = "opencode/deepseek-v4-flash-free", timeout: int = 60, token_collector: Optional[TokenCollector] = None) -> str:
    from iaglobal.providers.async_http import async_post
    api_key = ProviderConfig.OPENCODE_API_KEY or ""
    url = "https://opencode.ai/zen/v1/chat/completions"
    model_clean = model.replace("opencode/", "").strip()
    payload = {"model": model_clean, "messages": [{"role": "user", "content": prompt}], "stream": False}
    headers = {"Authorization": f"Bearer {api_key}"}
    return await async_post(url, payload, headers=headers, timeout=timeout)
