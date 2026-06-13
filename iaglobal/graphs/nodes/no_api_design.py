from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


async def run_api_design(ctx: Dict[str, Any]) -> Dict[str, Any]:
    requirements = ctx.get("requirements") or {}
    architecture = ctx.get("architecture") or {}

    functional = requirements.get("functional", [])
    backend_tech = architecture.get("components", [{}])[1].get("tech", "fastapi") if len(architecture.get("components", [])) > 1 else "fastapi"

    endpoints = [
        {
            "path": "/api/v1/health",
            "method": "GET",
            "description": "Health check",
            "auth": False,
        },
        {
            "path": "/api/v1/users",
            "method": "GET",
            "description": "Listar usuarios",
            "auth": True,
        },
        {
            "path": "/api/v1/users/{id}",
            "method": "GET",
            "description": "Obter usuario por ID",
            "auth": True,
        },
        {
            "path": "/api/v1/users",
            "method": "POST",
            "description": "Criar usuario",
            "auth": True,
        },
    ]

    api_design = {
        "base_url": "/api/v1",
        "framework": backend_tech,
        "format": "REST + JSON",
        "auth_method": "JWT Bearer Token",
        "endpoints": endpoints,
        "total_endpoints": len(endpoints),
        "rate_limiting": "100 req/min por IP",
        "versioning": "url-based (/v1/)",
    }

    logger.info("[API_DESIGN] Design de API: %d endpoints, framework=%s", len(endpoints), backend_tech)

    return {**ctx, "api_design": api_design, "output": api_design}