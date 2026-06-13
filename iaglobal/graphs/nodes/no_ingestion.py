"""Stub handler for ingestion — passes context through."""
from typing import Dict, Any


async def run_ingestion(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx
