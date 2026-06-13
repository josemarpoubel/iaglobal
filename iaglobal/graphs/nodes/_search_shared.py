"""Shared utilities for search nodes — retry with backoff + cache exclusivamente em disco."""
import time
import random
import asyncio
import logging
from typing import Callable, Optional

from iaglobal.graphs.nodes._disk_swap import load_search, save_search

logger = logging.getLogger(__name__)


async def retry_call(fn: Callable, task: str, max_retries: int = 2, base_delay: float = 1.0, stagger: float = 0.0) -> str:
    """Call a sync/async search function with retry + exponential backoff."""
    if stagger > 0:
        await asyncio.sleep(random.uniform(0, stagger))

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(fn):
                result = await fn(task)
            else:
                result = await asyncio.get_running_loop().run_in_executor(None, fn, task)
            if result and len(result) > 10:
                return result
        except Exception as e:
            last_error = str(e)
            logger.debug("[SEARCH] Attempt %d/%d failed: %s", attempt + 1, max_retries + 1, e)
        if attempt < max_retries:
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            logger.info("[SEARCH] Retry %d/%d in %.1fs...", attempt + 1, max_retries, delay)
            await asyncio.sleep(delay)
    if last_error:
        logger.warning("[SEARCH] All %d attempts failed: %s", max_retries + 1, last_error)
    return ""
