"""Helper functions for common operations."""

from typing import Any, Dict, Callable, TypeVar
from concurrent.futures import ThreadPoolExecutor
import json
import asyncio

T = TypeVar("T")


def run_async_safe(coro: Callable[..., T], *args, **kwargs) -> T:
    """Executa corrotina de forma segura tanto em contexto sync quanto async."""

    def _runner() -> T:
        return asyncio.run(coro(*args, **kwargs))

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return _runner()

    if loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(_runner).result()

    return _runner()


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
