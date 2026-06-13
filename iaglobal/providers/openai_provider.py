# iaglobal/providers/openai_provider.py

from typing import Optional

from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.providers.token_usage import TokenCollector
from iaglobal.memory import cache
from iaglobal.utils.logger import logger


def generate(
    prompt: str,
    model: str = "openai/gpt-4o-mini",
    timeout: int = 60,
    token_collector: Optional[TokenCollector] = None,
) -> str:
    from iaglobal.providers.async_http import get_sync_session

    model = model.replace("openai/", "").strip()

    api_key = ProviderConfig.OPENAI_API_KEY
    if not api_key:
        logger.debug("[OpenAI] API key not set, skipping")
        return ""

    cache_key = f"openai:{model}:{prompt}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        resp = get_sync_session().post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

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
        logger.warning(f"[OpenAI Provider] {e}")
        return ""


async def async_generate(
    prompt: str,
    model: str = "openai/gpt-4o-mini",
    timeout: int = 60,
    token_collector: Optional[TokenCollector] = None,
) -> str:
    import aiohttp
    from iaglobal.providers.async_http import get_session

    api_key = ProviderConfig.OPENAI_API_KEY or ""
    if not api_key:
        return ""

    model_clean = model.replace("openai/", "").strip()
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model_clean,
        "messages": [{"role": "user", "content": prompt}],
    }

    session = await get_session()
    try:
        async with session.post(
            url, json=payload, headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            text = await resp.text()
            if resp.status != 200:
                logger.warning(f"[OpenAI Async] {resp.status}: {text[:200]}")
                return ""
            import json; data = json.loads(text)
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "").strip()
                usage = data.get("usage")
                if usage and token_collector:
                    pt = usage.get("prompt_tokens", 0)
                    ct = usage.get("completion_tokens", 0)
                    token_collector(pt, ct)
                return content
            return ""
    except Exception as e:
        logger.warning(f"[OpenAI Async] {e}")
        return ""
