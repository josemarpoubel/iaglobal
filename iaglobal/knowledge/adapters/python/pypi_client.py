# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

PYPI_JSON_URL = "https://pypi.org/pypi/{package}/json"
PYPI_XMLRPC_URL = "https://pypi.org/pypi"
# XML-RPC search is not used in minimal version to avoid xmlrpc client import.
# Future: use https://pypi.org/simple/ or XML-RPC search().


async def fetch_metadata(
    package_name: str,
    session: aiohttp.ClientSession | None = None,
) -> dict | None:
    """Fetch full PyPI JSON metadata for a package.

    Returns the ``info`` dict from PyPI's JSON API, or ``None`` if the
    package does not exist or the request fails.

    Boundary Rule compliant: read-only HTTP, no side effects.
    """
    url = PYPI_JSON_URL.format(package=package_name.lower().strip())
    close_session = session is None
    if session is None:
        session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
        )
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.debug(
                    "PyPI metadata fetch failed for %s: HTTP %d",
                    package_name,
                    resp.status,
                )
                return None
            data = await resp.json()
            return data.get("info")
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
        logger.debug("PyPI metadata fetch error for %s: %s", package_name, exc)
        return None
    finally:
        if close_session:
            await session.close()


async def search_pypi(
    query: str,
    limit: int = 10,
    session: aiohttp.ClientSession | None = None,
) -> list[str]:
    """Search PyPI via the simple API HTML index.

    Fetches ``https://pypi.org/simple/`` and filters package names
    that contain the query substring.  This is intentionally basic;
    a proper XML-RPC or JSON search endpoint would be added in a
    future iteration.

    Boundary Rule compliant: read-only HTTP, no side effects.
    """
    url = "https://pypi.org/simple/"
    close_session = session is None
    if session is None:
        session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
        )
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.debug("PyPI simple index fetch failed: HTTP %d", resp.status)
                return []
            text = await resp.text()
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        logger.debug("PyPI simple index fetch error: %s", exc)
        return []
    finally:
        if close_session:
            await session.close()

    # Parse HTML — extract text between <a>...</a>
    results: list[str] = []
    q = query.lower()
    for match in re.finditer(r"<a[^>]*>([^<]+)</a>", text):
        name = match.group(1).strip().rstrip("/")
        if q in name.lower():
            results.append(name)
            if len(results) >= limit:
                break
    return results
