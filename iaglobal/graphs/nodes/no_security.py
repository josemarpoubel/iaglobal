"""Stub handler for security — passes context through."""
from typing import Dict, Any


async def run_security(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx
