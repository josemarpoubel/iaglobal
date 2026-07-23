from iaglobal.utils.helpers import run_async_safe
# iaglobal/providers/ollama_provider.py

import asyncio
import logging

from typing import Optional

from iaglobal.providers.provider_config import (
    ProviderConfig,
    get_role_by_model_id,
    get_model_config,
)
from iaglobal.providers.token_usage import TokenCollector

logger = logging.getLogger("iaglobal.providers.ollama")

_loaded_models: set[str] = set()

# PATCH: Modelos quantizados menores para fallback
_QUANTIZED_MODELS = ["qwen2.5:0.5b", "tinyllama:latest", "gemma:2b"]


async def warmup(model: str | None = None) -> bool:
    if model:
        model = model.replace("ollama/", "").strip()
    else:
        model = ProviderConfig.DEFAULT_OLLAMA_MODEL

    if model in _loaded_models:
        return True

    print(f"🔄 Carregando modelo Ollama [{model}] na RAM...")
    import aiohttp
    from urllib.parse import urljoin

    base_url = ProviderConfig.OLLAMA_URL.strip().rstrip("/")
    url = urljoin(base_url + "/", "api/generate")
    payload = {
        "model": model,
        "prompt": "test",
        "stream": False,
        "options": {"num_predict": 1},
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                resp.raise_for_status()
        _loaded_models.add(model)
        print(f"✅ Modelo [{model}] carregado e pronto!")
        return True
    except Exception as e:
        print(f"⚠️  Modelo [{model}] nao disponivel: {e}")
        return False


async def warmup_cognitive_cortex() -> dict[str, bool]:
    """Desperta os modelos locais do Tribunal Cognitivo em paralelo."""
    from iaglobal.providers.provider_config import get_all_active_models, CognitiveRole

    models_to_wake = get_all_active_models()
    print(f"🧠 Iniciando warmup do córtex cognitivo: {models_to_wake}")

    results: dict[str, bool] = {}

    async def _wake(m: str):
        results[m] = await warmup(m)

    await asyncio.gather(*[_wake(m) for m in models_to_wake], return_exceptions=True)

    ok = sum(1 for v in results.values() if v)
    print(f"✅ Córtex cognitivo ativado: {ok}/{len(results)} modelos prontos")
    return results


def generate(
    prompt: str,
    model: str = None,
    timeout: int = 600,
    token_collector: Optional[TokenCollector] = None,
) -> str:
    return run_async_safe(async_generate, prompt, model, timeout, token_collector)


async def async_generate(
    prompt: str,
    model: str = None,
    timeout: int = 600,
    token_collector: Optional[TokenCollector] = None,
) -> str:
    if model:
        model = model.replace("ollama/", "").strip()
    else:
        model = ProviderConfig.DEFAULT_OLLAMA_MODEL

    import json
    from urllib.parse import urljoin
    from iaglobal.providers.async_http import get_session

    base_url = ProviderConfig.OLLAMA_URL.strip().rstrip("/")
    system_msg = "Always respond in English. If it's code, use the appropriate language (HTML, Python, etc)."

    role = get_role_by_model_id(model)
    model_config = get_model_config(role) if role else None
    num_predict = model_config.get("num_predict", 8192) if model_config else 8192
    num_ctx = model_config.get("context_window", 4096) if model_config else 4096
    # Optimized parameters for small local models:
    # - temperature=0.1 → deterministic, avoids syntax hallucination
    # - num_ctx → attention window, configurável por modelo via provider_config
    # - num_predict → limite de geração, configurável por modelo via provider_config
    # - keep_alive → mantém modelo na RAM por 10 minutos
    ollama_options = {
        "temperature": 0.1,
        "num_ctx": num_ctx,
        "num_predict": num_predict,
        "keep_alive": "10m",
    }
    logger.info(
        "[OLLAMA] model=%s num_ctx=%d num_predict=%d",
        model,
        num_ctx,
        num_predict,
    )
    endpoints_payloads = [
        (
            urljoin(base_url + "/", "v1/chat/completions"),
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": ollama_options,
            },
        ),
        (
            urljoin(base_url + "/", "api/chat"),
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": ollama_options,
            },
        ),
        (
            urljoin(base_url + "/", "api/generate"),
            {
                "model": model,
                "prompt": prompt,
                "system": system_msg,
                "stream": False,
                "options": ollama_options,
            },
        ),
    ]

    last_error = None
    import aiohttp

    session = await get_session()
    for url, payload in endpoints_payloads:
        print(f"  📡 Ollama async: {url} model={payload.get('model', '?')}")
        try:
            async with session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                text = await resp.text()
                print(f"  📡 Ollama async: {url} -> {resp.status} ({len(text)} bytes)")
                if resp.status != 200:
                    last_error = f"HTTP {resp.status}"
                    continue
                data = json.loads(text)

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


# Auto-registro no ProviderRegistry
from iaglobal.providers.contract import registry as _registry

_registry.register_funcs(
    "ollama",
    generate=generate,
    async_generate=async_generate,
    warmup=warmup,
)
