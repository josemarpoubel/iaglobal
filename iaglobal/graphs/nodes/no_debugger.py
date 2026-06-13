"""Stub handler for debugger — passes context through."""
from typing import Dict, Any


async def run_debugger(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx
