# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/_search_capabilities.py

"""Capability probe para fontes pesadas de busca (Playwright / YaCy).

Espelha o padrão de circuit-breaker / skip-list (SearXNG / BanditPolicy):
checagem BARATA e CACHEADA por TTL, para que `no_search.py` NÃO dispere
threads/ATP em fontes que jamais funcionam neste ambiente.

INVARIANTE ASYNC (crítico):
- `is_yacy_available` é `async` e executa a probe de rede (bloqueante, até 3s)
  dentro de `asyncio.to_thread`, NUNCA no event loop.
- Um `asyncio.Lock` (single-flight) garante que, na expiração do TTL com
  N buscas concorrentes, apenas UMA probe rode — as demais aguardam o
  resultado em cache (evita thundering herd, idem `EpigeneticBandit`).
"""

import time
import asyncio
import logging
import importlib.util

logger = logging.getLogger(__name__)

# Fontes que dependem de cada capacidade (devem bater com SOURCES em no_search.py)
_PLAYWRIGHT_SOURCES = {"google_pw", "bing_pw", "playwright_js"}
_YACY_SOURCES = {"yacy"}

_YACY_URL = "http://localhost:8090"
_YACY_TTL_DEFAULT = 300.0
# Cache do estado (disponível/indisponível) com TTL — evita re-probe a cada chamada
# e, combinado com o lock, impede thundering herd na expiração.
_yacy_state: bool = False
_yacy_state_until: float = 0.0

_yacy_lock: "asyncio.Lock | None" = None


def _get_yacy_lock() -> asyncio.Lock:
    """Lock criado lazy para não vincular a um event loop em import-time."""
    global _yacy_lock
    if _yacy_lock is None:
        _yacy_lock = asyncio.Lock()
    return _yacy_lock


def is_playwright_available() -> bool:
    """Checagem barata: o módulo playwright está instalado? (não sobe browser)."""
    return importlib.util.find_spec("playwright") is not None


def _probe_yacy_sync(url: str) -> bool:
    """Probe de rede SÍNCRONO (roda dentro de asyncio.to_thread)."""
    import urllib.request
    import urllib.error

    req = urllib.request.Request(url, headers={"User-Agent": "IAGlobal/1.0"})
    with urllib.request.urlopen(req, timeout=3.0) as r:
        if r.status >= 400:
            raise urllib.error.HTTPError(url, r.status, "", None, None)
    return True


async def is_yacy_available(
    ttl: float = _YACY_TTL_DEFAULT, url: str = _YACY_URL
) -> bool:
    """Probe de rede com TTL cache (ambos os estados) e single-flight.

    - Não bloqueia o event loop (probe roda em asyncio.to_thread).
    - Na expiração do TTL com N buscas concorrentes, apenas UMA probe roda
      (asyncio.Lock); as demais consomem o estado em cache.
    """
    global _yacy_state, _yacy_state_until
    # Fast path: cache ainda válido — sem lock, sem rede
    if time.monotonic() < _yacy_state_until:
        return _yacy_state
    async with _get_yacy_lock():
        # Double-checked: outra coroutine pode ter atualizado o estado aguardando o lock
        if time.monotonic() < _yacy_state_until:
            return _yacy_state
        try:
            ok = await asyncio.to_thread(_probe_yacy_sync, url)
        except Exception as e:
            logger.debug("[YACY] peer indisponível: %s — rechecando em %.0fs", e, ttl)
            ok = False
        _yacy_state = ok
        _yacy_state_until = time.monotonic() + ttl
        return ok


async def get_search_skip_list() -> set:
    """Retorna o conjunto de nomes de fonte a pular dado o ambiente atual."""
    skip: set = set()
    if not is_playwright_available():
        skip.update(_PLAYWRIGHT_SOURCES)
    if not await is_yacy_available():
        skip.update(_YACY_SOURCES)
    return skip
