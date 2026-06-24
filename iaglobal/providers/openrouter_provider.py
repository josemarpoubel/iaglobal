from iaglobal.utils.helpers import run_async_safe
# iaglobal/providers/openrouter_provider.py

from typing import Optional

from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.providers.token_usage import TokenCollector
from iaglobal.memory import cache
from iaglobal.utils.logger import logger


def generate(prompt: str, model: str = "openrouter/meta-llama/llama-3.2-3b-instruct:free", timeout: int = 60, token_collector: Optional[TokenCollector] = None) -> str:
    return run_async_safe(async_generate, prompt, model, timeout, token_collector)


async def async_generate(prompt: str, model: str = "openrouter/meta-llama/llama-3.2-3b-instruct:free", timeout: int = 60, token_collector: Optional[TokenCollector] = None) -> str:
    from iaglobal.providers.async_http import async_post
    from iaglobal.providers.provider_config import ProviderConfig
    import asyncio

    api_key = ProviderConfig.OPENROUTER_API_KEY or ""
    url = "https://openrouter.ai/api/v1/chat/completions"
    model_clean = model.replace("openrouter/", "").strip()
    payload = {"model": model_clean, "messages": [{"role": "user", "content": prompt}], "stream": False}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com",
        "X-Title": "IAGlobal Framework",
    }

    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        result = await async_post(url, payload, headers=headers, timeout=timeout, provider="openrouter", token_collector=token_collector)
        if result:
            return result
        if attempt < MAX_RETRIES - 1:
            backoff = 2 ** attempt
            logger.info(f"[OpenRouter] tentativa {attempt+1} falhou — retry em {backoff}s")
            await asyncio.sleep(backoff)
    return ""
