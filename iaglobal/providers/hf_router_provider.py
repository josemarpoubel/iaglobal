# iaglobal/providers/hf_router_provider.py

from __future__ import annotations

import os
import re
import time
from typing import Optional, List, Dict, Union, Any, Callable
from threading import Lock
from iaglobal.utils.helpers import run_async_safe

# FIX: Importamos AsyncOpenAI para não travar o Event Loop da corrida paralela
from openai import AsyncOpenAI

from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.utils.logger import get_logger

logger = get_logger(__name__)

# ==========================================================
# CONFIGURAÇÕES
# ==========================================================
DEFAULT_MODEL = "Qwen/Qwen3-Coder-480B-A35B-Instruct:novita"
MAX_TOKENS = 4096

# ==========================================================
# API KEY E CLIENTES (SYNC / ASYNC)
# ==========================================================

def get_api_key() -> str:
    key = ProviderConfig.HUGGINGFACE_API_KEY or os.getenv("HF_TOKEN")
    if not key:
        logger.warning("⚠️ [HF_Router] Chave de API ausente (HUGGINGFACE_API_KEY ou HF_TOKEN).")
    return key or ""

_async_client: Optional[AsyncOpenAI] = None
_client_lock = Lock()

def get_async_client() -> AsyncOpenAI:
    global _async_client
    if not _async_client:
        with _client_lock:
            if not _async_client:
                _async_client = AsyncOpenAI(api_key=get_api_key(), base_url="https://router.huggingface.co/v1")
    return _async_client

# ==========================================================
# MULTIMODAL (Processamento de Imagens no Prompt)
# ==========================================================

IMAGE_REGEX = re.compile(r'!\[.*?\]\(([^)]+)\)')

def build_multimodal_messages(prompt: str) -> List[Dict[str, Any]]:
    parts = []
    current = 0
    for match in IMAGE_REGEX.finditer(prompt):
        if match.start() > current:
            parts.append({"type": "text", "text": prompt[current:match.start()]})
        parts.append({"type": "image_url", "image_url": {"url": match.group(1)}})
        current = match.end()

    if current < len(prompt):
        parts.append({"type": "text", "text": prompt[current:]})

    if not parts or len(parts) == 1 and parts[0]["type"] == "text":
        return [{"role": "user", "content": prompt}]
    return [{"role": "user", "content": parts}]

# ==========================================================
# EXECUÇÃO ASSÍNCRONA (A Corrida Paralela)
# ==========================================================

def generate(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 30, token_collector: Optional[Callable] = None, **kwargs) -> str:
    return run_async_safe(async_generate, prompt, model, timeout, token_collector, **kwargs)


async def async_generate(
    prompt: str, 
    model: str = DEFAULT_MODEL, 
    timeout: int = 30, 
    token_collector: Optional[Callable] = None,
    **kwargs # Absorve parâmetros extras do Router sem quebrar
) -> str:
    """
    Função Assíncrona Pura. Não roteia, não pensa. Apenas executa a chamada 
    na API da Hugging Face usando a biblioteca oficial de forma não-bloqueante.
    """
    if not get_api_key():
        return ""

    # Limpa o prefixo do modelo (ex: 'hf_router/Qwen' -> 'Qwen')
    import re
    clean_model = re.sub(r'^hf_router_\w+/', '', model)
    clean_model = clean_model.replace("hf_router/", "", 1).strip() or DEFAULT_MODEL
    messages = build_multimodal_messages(prompt) if isinstance(prompt, str) else prompt

    client = get_async_client()
    
    start = time.perf_counter()
    try:
        # A Mágica Assíncrona: Libera os 4 núcleos da CPU enquanto espera a rede!
        completion = await client.chat.completions.create(
            model=clean_model,
            messages=messages,
            timeout=float(timeout),
            max_tokens=MAX_TOKENS
        )
        
        latency = time.perf_counter() - start
        
        # Coleta de tokens
        if hasattr(completion, 'usage') and completion.usage:
            pt = completion.usage.prompt_tokens or 0
            ct = completion.usage.completion_tokens or 0
            if token_collector:
                token_collector(pt, ct)

        result = completion.choices[0].message.content or ""
        logger.debug(f"[HF_Router ASYNC] {clean_model} respondeu em {latency:.2f}s ({len(result)} chars)")
        return result.strip()

    except Exception as e:
        logger.error(f"[HF_Router ASYNC] Erro ao chamar {clean_model}: {e}")
        raise # Joga o erro pro Router registrar no Circuit Breaker
