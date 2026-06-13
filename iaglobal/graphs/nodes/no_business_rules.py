"""Stub handler for business_rules — passes context through."""
from typing import Dict, Any


async def run_business_rules(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx
