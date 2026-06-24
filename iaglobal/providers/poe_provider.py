from iaglobal.utils.helpers import run_async_safe
# iaglobal/providers/poe_provider.py

from typing import Optional

from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.providers.token_usage import TokenCollector
from iaglobal.memory import cache
from iaglobal.utils.logger import logger


def generate(prompt: str, model: str = "poe/GLM-5-T", timeout: int = 180, token_collector: Optional[TokenCollector] = None) -> str:
    return run_async_safe(async_generate, prompt, model, timeout, token_collector)


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
