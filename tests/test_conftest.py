"""
Pytest conftest para cleanup automático de recursos.
"""

import pytest
import asyncio
import sys

sys.path.insert(0, "/home/kitohamachi/projeto-iaglobal")


@pytest.fixture(autouse=True, scope="session")
def cleanup_aiohttp():
    """Cleanup aiohttp sessions after all tests."""
    yield
    # Cleanup sync (não precisa ser async)
    try:
        from iaglobal.providers.async_http import close_all_sessions
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(close_all_sessions())
        loop.close()
    except Exception:
        pass