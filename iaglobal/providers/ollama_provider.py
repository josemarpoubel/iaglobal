from iaglobal.utils.helpers import run_async_safe
# iaglobal/providers/ollama_provider.py

import asyncio
import logging

from typing import Optional

from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.providers.token_usage import TokenCollector
from iaglobal.memory.core import memory

logger = logging.getLogger("iaglobal.providers.ollama")

# Lock compartilhado com bandit.py — apenas 1 inferência local por vez
_OLLAMA_CPU_LOCK = asyncio.Semaphore(1)
# Export para bandit.py usar o mesmo lock
OLLAMA_CPU_LOCK = _OLLAMA_CPU_LOCK
_ollama_semaphore = asyncio.Semaphore(4)
_loaded_models = set()

# PATCH: Modelos quantizados menores para fallback
_QUANTIZED_MODELS = ["qwen2.5:0.5b", "tinyllama:latest", "gemma:2b"]

async def warmup(model: str = None) -> bool:
    if model:
        model = model.replace("ollama/", "").strip()
    else:
        model = ProviderConfig.DEFAULT_OLLAMA_MODEL

    if model in _loaded_models:
        return True

    print(f"🔄 Carregando modelo Ollama [{model}] na RAM...")
    import aiohttp
    from urllib.parse import urljoin
    base_url = ProviderConfig.OLLAMA_URL.strip().rstrip('/')
    url = urljoin(base_url + "/", "api/generate")
    payload = {"model": model, "prompt": "test", "stream": False, "options": {"num_predict": 1}}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
        _loaded_models.add(model)
        print(f"✅ Modelo [{model}] carregado e pronto!")
        return True
    except Exception as e:
        print(f"⚠️  Modelo [{model}] nao disponivel: {e}")
        return False


def generate(prompt: str, model: str = None, timeout: int = 600, token_collector: Optional[TokenCollector] = None) -> str:
    return run_async_safe(async_generate, prompt, model, timeout, token_collector)


async def async_generate(prompt: str, model: str = None, timeout: int = 600, token_collector: Optional[TokenCollector] = None) -> str:
    if model:
        model = model.replace("ollama/", "").strip()
    else:
        model = ProviderConfig.DEFAULT_OLLAMA_MODEL

    import json
    from urllib.parse import urljoin
    from iaglobal.providers.async_http import get_session

    base_url = ProviderConfig.OLLAMA_URL.strip().rstrip('/')
    system_msg = "Responda SEMPRE em português brasileiro. Se for código, use a linguagem apropriada (HTML, Python, etc)."
    endpoints_payloads = [
        (urljoin(base_url + "/", "v1/chat/completions"), {
            "model": model,
            "messages": [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
            "stream": False, "options": {"keep_alive": "10m"},
        }),
        (urljoin(base_url + "/", "api/chat"), {
            "model": model,
            "messages": [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
            "stream": False,
        }),
        (urljoin(base_url + "/", "api/generate"), {
            "model": model, "prompt": prompt, "system": system_msg, "stream": False,
        }),
    ]

    last_error = None
    import aiohttp

    async with _ollama_semaphore:
        session = await get_session()
        for url, payload in endpoints_payloads:
            print(f"  📡 Ollama async: {url} model={payload.get('model','?')}")
            try:
                async with session.post(
                    url, json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    text = await resp.text()
                    print(f"  📡 Ollama async: {url} -> {resp.status} ({len(text)} bytes)")
                    if resp.status != 200:
                        last_error = f"HTTP {resp.status}"
                        continue
                    data = json.loads(text)

                    # Extrair token usage (Ollama retorna em formatos diferentes)
                    if token_collector:
                        if "usage" in data:
                            pt = data["usage"].get("prompt_tokens", 0)
                            ct = data["usage"].get("completion_tokens", 0)
                            if pt or ct:
                                token_collector(pt, ct)
                        elif "prompt_eval_count" in data:
                            pt = data.get("prompt_eval_count", 0)
                            ct = data.get("eval_count", 0)
                            if pt or ct:
                                token_collector(pt, ct)

                    if "choices" in data:
                        result = data["choices"][0]["message"]["content"].strip()
                    elif "message" in data:
                        result = data["message"]["content"].strip()
                    elif "response" in data:
                        result = data["response"].strip()
                    else:
                        last_error = "Formato de resposta desconhecido"
                        continue
                    if result:
                        return result
            except asyncio.TimeoutError:
                print(f"  ⏱️ Ollama async timeout: {url}")
                last_error = f"Timeout ({timeout}s)"
                continue
            except aiohttp.ClientConnectorError:
                raise RuntimeError(f"Ollama não acessível em {base_url}.")
            except Exception as e:
                last_error = str(e)
                continue
    raise RuntimeError(f"Ollama endpoints falharam: {last_error}")
