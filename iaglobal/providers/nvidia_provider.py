from iaglobal.utils.helpers import run_async_safe
# iaglobal/providers/nvidia_provider.py

from typing import Optional

from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.providers.token_usage import TokenCollector


def generate(
    prompt: str,
    model: str = "nvidia/mistralai/mistral-large-3-675b-instruct-2512",
    timeout: int = 60,
    token_collector: Optional[TokenCollector] = None,
) -> str:
    return run_async_safe(async_generate, prompt, model, timeout, token_collector)


async def async_generate(
    prompt: str,
    model: str = "nvidia/mistralai/mistral-large-3-675b-instruct-2512",
    timeout: int = 60,
    token_collector: Optional[TokenCollector] = None,
) -> str:
    from iaglobal.providers.async_http import async_post

    api_key = ProviderConfig.NVIDIA_API_KEY or ""
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    model_clean = model.replace("nvidia/", "").strip()
    payload = {
        "model": model_clean,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    return await async_post(
        url, payload, headers=headers, timeout=timeout, token_collector=token_collector
    )
