"""Stub handler for validator — passes context through."""
from typing import Dict, Any


async def run_validator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx
