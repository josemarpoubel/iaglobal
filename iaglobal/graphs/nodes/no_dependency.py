"""Stub handler for dependency — passes context through."""
from typing import Dict, Any


async def run_dependency(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx
