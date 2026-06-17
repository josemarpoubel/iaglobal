"""Helper functions for common operations."""

from typing import Any, Dict, List, Callable, TypeVar
import json
import asyncio

T = TypeVar('T')


def run_async_safe(coro: Callable[..., T], *args, **kwargs) -> T:
    """Executa corrotina de forma segura tanto em contexto sync quanto async.
    
    Se já estiver em um event loop, cria uma task e aguarda.
    Se não, usa asyncio.run().
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop and loop.is_running():
        # Já em event loop - criar task e aguardar
        async def _runner():
            return await coro(*args, **kwargs)
        return asyncio.run_coroutine_threadsafe(_runner(), loop).result()
    else:
        # Sem event loop - usar asyncio.run
        return asyncio.run(coro(*args, **kwargs))


def format_output(data: Any, pretty: bool = True) -> str:
    """Format output as JSON string."""
    if pretty:
        return json.dumps(data, indent=2)
    return json.dumps(data)

def parse_input(data: str) -> Any:
    """Parse input as JSON."""
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return data

def merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """Recursively merge two dictionaries."""
    result = dict1.copy()
    for key, value in dict2.items():
        if isinstance(value, dict):
            result[key] = merge_dicts(result.get(key, {}), value)
        else:
            result[key] = value
    return result
