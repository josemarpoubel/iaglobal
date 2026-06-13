from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


async def run_security_design(ctx: Dict[str, Any]) -> Dict[str, Any]:
    requirements = ctx.get("requirements") or {}
    api_design = ctx.get("api_design") or {}

    endpoints = api_design.get("endpoints", [])
    auth_endpoints = sum(1 for e in endpoints if e.get("auth"))

    security_design = {
        "authentication": {
            "method": "JWT",
            "strategy": "access + refresh tokens",
            "expiry": "15min access, 7d refresh",
            "storage": "httpOnly cookie + Authorization header",
        },
        "authorization": {
            "model": "RBAC",
            "roles": ["admin", "user", "guest"],
        },
        "owasp_mitigations": [
            {"vulnerability": "SQL Injection", "mitigation": "parameterized queries + ORM"},
            {"vulnerability": "XSS", "mitigation": "CSP headers + output encoding"},
            {"vulnerability": "CSRF", "mitigation": "anti-CSRF tokens + SameSite cookies"},
            {"vulnerability": "Rate Limiting", "mitigation": "100 req/min per IP"},
        ],
        "encryption": {
            "at_rest": "AES-256",
            "in_transit": "TLS 1.3",
            "passwords": "bcrypt (cost=12)",
        },
        "secure_endpoints": auth_endpoints,
        "total_endpoints": len(endpoints),
    }

    logger.info("[SECURITY_DESIGN] Controles de seguranca: %d endpoints protegidos", auth_endpoints)

    return {**ctx, "security_design": security_design, "output": security_design}