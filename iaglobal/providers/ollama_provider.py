# iaglobal/providers/ollama_provider.py

import asyncio
import logging
import requests

from typing import Optional

from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.providers.token_usage import TokenCollector
from iaglobal.memory.core import memory

logger = logging.getLogger("iaglobal.providers.ollama")

_loaded_models = set()


def warmup(model: str = None) -> bool:
    if model:
        model = model.replace("ollama/", "").strip()
    else:
        model = ProviderConfig.DEFAULT_OLLAMA_MODEL

    if model in _loaded_models:
        return True

    print(f"🔄 Carregando modelo Ollama [{model}] na RAM...")
    print(f"🔄 Verificando se o modelo Ollama [{model}] foi carregado na RAM...")
    try:
        from urllib.parse import urljoin
        base_url = ProviderConfig.OLLAMA_URL.strip().rstrip('/')
        url = urljoin(base_url + "/", "api/generate")
        payload = {"model": model, "prompt": "test", "stream": False, "options": {"num_predict": 1}}
        resp = requests.post(url, json=payload, timeout=(3, 30))
        resp.raise_for_status()
        _loaded_models.add(model)
        print(f"✅ Modelo [{model}] carregado e pronto!")
        return True
    except Exception as e:
        print(f"⚠️  Modelo [{model}] nao disponivel: {e}")
        return False


def generate(prompt: str, model: str = None, timeout: int = 600, token_collector: Optional[TokenCollector] = None) -> str:
    # Se o modelo vier com o prefixo do roteador (ex: 'ollama/qwen-hermes'), limpa o texto
    if model:
        model = model.replace("ollama/", "").strip()
    else:
        model = ProviderConfig.DEFAULT_OLLAMA_MODEL

    cache_key = f"ollama:{model}:{prompt}"

    # Tenta recuperar do cache persistente
    cached = memory.load(cache_key)
    if cached:
        logger.info(f"💾 Cache hit para o modelo local [{model}]")
        return cached["response"]

    from urllib.parse import urljoin
    base_url = ProviderConfig.OLLAMA_URL.strip().rstrip('/')
    system_msg = "Responda SEMPRE em português brasileiro. Se for código, use a linguagem apropriada (HTML, Python, etc)."
    endpoints = [
        ("/v1/chat/completions", {
            "model": model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"keep_alive": "10m"},
        }),
        ("/api/chat", {
            "model": model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }),
        ("/api/generate", {
            "model": model,
            "prompt": prompt,
            "system": system_msg,
            "stream": False,
        }),
    ]

    last_error = None
    for endpoint, payload in endpoints:
        url = urljoin(base_url + "/", endpoint.lstrip("/"))
        print(f"  📡 Ollama: {url} model={payload.get('model','?')}")
        try:
            headers = {"Connection": "close", "Content-Type": "application/json"}
            response = requests.post(url, json=payload, headers=headers, timeout=(3, timeout))
            print(f"  📡 Ollama: {url} -> {response.status_code} ({len(response.content)} bytes)")
            response.raise_for_status()
            data = response.json()

            if "choices" in data:
                result = data["choices"][0]["message"]["content"].strip()
            elif "message" in data:
                result = data["message"]["content"].strip()
            elif "response" in data:
                result = data["response"].strip()
            else:
                continue

            if result:
                memory.save(prompt=cache_key, response=result,
                            metadata={"provider": "ollama", "model": model})
                return result

        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Ollama não acessível em {base_url}.")
        except Exception as e:
            last_error = e
            logger.debug("[OLLAMA] Endpoint %s falhou: %s — tentando proximo", endpoint, e)
            continue

    raise RuntimeError(f"Ollama endpoints falharam: {last_error}")


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

