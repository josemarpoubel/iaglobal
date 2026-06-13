from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


async def run_system_design(ctx: Dict[str, Any]) -> Dict[str, Any]:
    architecture = ctx.get("architecture") or {}
    requirements = ctx.get("requirements") or {}

    components = architecture.get("components", [])
    patterns = architecture.get("patterns_applied", [])

    system_design = {
        "architecture_overview": architecture.get("pattern", "monolithic"),
        "component_details": [
            {
                "name": c.get("name"),
                "tech": c.get("tech"),
                "responsibility": c.get("responsibility"),
                "interfaces": ["REST API", "gRPC"],
                "scaling": "horizontal",
                "availability": "99.9%",
            }
            for c in components
        ],
        "data_flow": [
            {"from": "client", "to": "api-gateway", "protocol": "HTTPS"},
            {"from": "api-gateway", "to": "backend-service", "protocol": "HTTP/REST"},
            {"from": "backend-service", "to": "database-layer", "protocol": "SQL/TCP"},
        ],
        "patterns": patterns,
        "non_functional_requirements": {
            "scalability": "horizontal com auto-scaling",
            "security": "JWT + OAuth2 + HTTPS",
            "performance": "<200ms p95",
            "availability": "99.9% uptime",
        },
    }

    logger.info("[SYSTEM_DESIGN] Design de sistema concluido: %d componentes", len(components))

    return {**ctx, "system_design": system_design, "output": system_design}