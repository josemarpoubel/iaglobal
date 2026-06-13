"""Stub handler for tester — passes context through."""
from typing import Dict, Any


async def run_tester(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx
