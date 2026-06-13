# iaglobal/providers/async_http.py

import asyncio
import json
import logging
import threading
import time
from typing import Dict

import aiohttp
import requests
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

_sessions: Dict[int, aiohttp.ClientSession] = {}
_lock = threading.Lock()

# BANNED_DOMAINS - aborta ANTES do request (PATCH 3)
_BANNED_DOMAINS: set = set()

# Circuit Breaker - providers bloqueados por erro fatal
_BLOCKED_PROVIDERS: Dict[str, float] = {}
_BLOCK_WINDOW = 3600
_BLOCK_AUTH_WINDOW = 86400


def is_provider_blocked(provider: str) -> bool:
    """Verifica se provider está bloqueado pelo Circuit Breaker."""
    if provider not in _BLOCKED_PROVIDERS:
        return False
    unblock_time = _BLOCKED_PROVIDERS[provider]
    if time.time() < unblock_time:
        return True
    del _BLOCKED_PROVIDERS[provider]
    return False


def block_provider(provider: str, status: int):
    """Bloqueia provider por erro fatal (402, 401, 429)."""
    if status in (401, 402, 429):
        block_time = _BLOCK_AUTH_WINDOW if status in (401, 402) else _BLOCK_WINDOW
        _BLOCKED_PROVIDERS[provider] = time.time() + block_time
        logger.warning("[CIRCUIT-BREAKER] Provider %s bloqueado por status %d por %ds", provider, status, block_time)


async def get_session() -> aiohttp.ClientSession:
    """Retorna sessão aiohttp para o event loop atual.

    Mantém uma sessão POR event loop. Sessões nunca são fechadas
    automaticamente — apenas por close_session() explícito.
    """
    current_loop = asyncio.get_running_loop()
    loop_id = id(current_loop)
    with _lock:
        session = _sessions.get(loop_id)
        if session is None or session.closed:
            session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120),
                headers={"Content-Type": "application/json"},
            )
            _sessions[loop_id] = session
    return session


async def close_session():
    """Fecha APENAS a sessão do event loop atual."""
    global _sessions
    try:
        current_loop = asyncio.get_running_loop()
        loop_id = id(current_loop)
    except RuntimeError:
        # Sem loop rodando — fecha todas
        with _lock:
            for lid, session in _sessions.items():
                if session and not session.closed:
                    await session.close()
            _sessions.clear()
        return

    with _lock:
        session = _sessions.pop(loop_id, None)
        if session and not session.closed:
            await session.close()


_sync_session = None
_sync_session_lock = threading.Lock()


def get_sync_session() -> requests.Session:
    global _sync_session
    if _sync_session is None:
        with _sync_session_lock:
            if _sync_session is None:
                _sync_session = requests.Session()
                _sync_session.headers.update({"Content-Type": "application/json"})
                adapter = HTTPAdapter(pool_connections=10, pool_maxsize=30, max_retries=0)
                _sync_session.mount("https://", adapter)
                _sync_session.mount("http://", adapter)
    return _sync_session


async def close_all_sessions():
    """Fecha todas as sessões de todos os event loops.

    PATCH 1: Hard cleanup - também fecha o connector TCP.
    """
    global _sessions
    with _lock:
        for lid, session in _sessions.items():
            if session and not session.closed:
                try:
                    # Fecha o connector TCP subjacente
                    if session.connector and not session.connector.closed:
                        session.connector.close()
                    await session.close()
                except Exception:
                    pass
        _sessions.clear()


async def async_post(
    url: str,
    json_data: dict,
    headers: dict | None = None,
    timeout: int = 60,
    provider: str = "",
) -> str:
    # PATCH 3: BANNED_DOMAINS - aborta ANTES do request
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    if domain in _BANNED_DOMAINS:
        logger.warning("[CIRCUIT-BREAKER] Abortando request para domínio banido: %s", domain)
        raise Exception(f"CircuitBreaker ABERTO: {domain} está banido")

    # Circuit breaker check (provider-level)
    if provider and is_provider_blocked(provider):
        logger.warning("[ASYNC-HTTP] Provider %s está bloqueado (circuit breaker)", provider)
        return ""

    session = await get_session()
    merged_headers = {"Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)
    try:
        async with session.post(
            url, json=json_data, headers=merged_headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            text = await resp.text()
            if resp.status != 200:
                # Circuit breaker: bloqueia por erro fatal
                if provider:
                    block_provider(provider, resp.status)
                logger.warning("[ASYNC-HTTP] %s -> %d: %.200s", url, resp.status, text)
                return ""
            data = json.loads(text)
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "") or ""
            return ""
    except asyncio.TimeoutError:
        logger.warning("[ASYNC-HTTP] Timeout (%ds) para %s", timeout, url)
        return ""
    except aiohttp.ClientConnectorError:
        logger.warning("[ASYNC-HTTP] Conexao recusada em %s (offline)", url)
        return ""
    except Exception as e:
        logger.debug("[ASYNC-HTTP] Erro em %s: %s", url, e)
        return ""
