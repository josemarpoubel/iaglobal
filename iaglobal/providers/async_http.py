# iaglobal/providers/async_http.py

import asyncio
import json
import logging
import threading
from typing import Dict

import aiohttp

logger = logging.getLogger(__name__)

_sessions: Dict[int, aiohttp.ClientSession] = {}
_lock = threading.Lock()


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


async def close_all_sessions():
    """Fecha todas as sessões de todos os event loops."""
    global _sessions
    with _lock:
        for lid, session in _sessions.items():
            if session and not session.closed:
                try:
                    await session.close()
                except Exception:
                    pass
        _sessions.clear()


async def async_post(
    url: str,
    json_data: dict,
    headers: dict | None = None,
    timeout: int = 60,
) -> str:
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
