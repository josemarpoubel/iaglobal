"""Stub handler for metrics — passes context through."""
from typing import Dict, Any


async def run_metrics(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx
