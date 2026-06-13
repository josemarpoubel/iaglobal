"""Stub handler for interpreter — passes context through."""
from typing import Dict, Any


async def run_interpreter(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx
