# iaglobal/providers/gemini_provider.py

import requests
from typing import Optional

from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.providers.token_usage import TokenCollector
from iaglobal.memory import cache
from iaglobal.utils.logger import logger


def generate(
    prompt: str,
    model: str = "gemini/gemini-2.5-flash-lite",
    timeout: int = 60,
    token_collector: Optional[TokenCollector] = None
) -> str:

    model = model.replace("gemini/", "").strip()

    if not ProviderConfig.GEMINI_API_KEY:
        logger.debug(f"[Gemini Provider] API key not set, skipping")
        return ""

    cache_key = f"gemini:{model}:{prompt}"

    cached = cache.get(cache_key)
    if cached:
        return cached

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={ProviderConfig.GEMINI_API_KEY}"
    )

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout
        )

        response.raise_for_status()
        data = response.json()

        usage = data.get("usageMetadata")
        if usage and token_collector:
            pt = usage.get("promptTokenCount", 0)
            ct = usage.get("candidatesTokenCount", 0)
            token_collector(pt, ct)

        result = (
            data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
        )

        cache.set(cache_key, result)
        return result

    except Exception as e:
        logger.warning(f"[Gemini Provider] {e}")
        return ""


async def async_generate(prompt: str, model: str = "gemini/gemini-2.5-flash-lite", timeout: int = 60, token_collector: Optional[TokenCollector] = None) -> str:
    import json
    import aiohttp
    from iaglobal.providers.async_http import get_session

    api_key = ProviderConfig.GEMINI_API_KEY or ""
    model_clean = model.replace("gemini/", "").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_clean}:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    session = await get_session()
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            text = await resp.text()
            if resp.status != 200:
                return ""
            data = json.loads(text)
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    text = parts[0].get("text", "").strip()

                    usage = data.get("usageMetadata")
                    if usage and token_collector:
                        pt = usage.get("promptTokenCount", 0)
                        ct = usage.get("candidatesTokenCount", 0)
                        token_collector(pt, ct)

                    return text
            return ""
    except Exception as e:
        logger.warning(f"[Gemini Async] {e}")
        return ""