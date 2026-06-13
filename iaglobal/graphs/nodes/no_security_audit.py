"""Stub handler for security_audit — passes context through."""
from typing import Dict, Any


async def run_security_audit(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx
