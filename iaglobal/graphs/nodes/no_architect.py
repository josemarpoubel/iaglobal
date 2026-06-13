from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


async def run_architect(ctx: Dict[str, Any]) -> Dict[str, Any]:
    requirements = ctx.get("requirements") or {}
    technology_selection = ctx.get("technology_selection") or {}
    knowledge_data = ctx.get("knowledge") or {}

    functional = requirements.get("functional", [])
    non_functional = requirements.get("non_functional", [])

    tech_stack = technology_selection.get("stack", {})
    backend = tech_stack.get("backend", "python-fastapi")
    frontend = tech_stack.get("frontend", "react")
    database = tech_stack.get("database", "postgresql")

    architecture = {
        "pattern": "layered-microservices",
        "components": [
            {"name": "api-gateway", "tech": "nginx-traefik", "responsibility": "roteamento e autenticacao"},
            {"name": "backend-service", "tech": backend, "responsibility": "logica de negocios e API"},
            {"name": "frontend-app", "tech": frontend, "responsibility": "interface do usuario"},
            {"name": "database-layer", "tech": database, "responsibility": "persistencia de dados"},
        ],
        "layers": ["presentation", "api", "business", "data"],
        "patterns_applied": ["clean-architecture", "dependency-injection", "repository-pattern"],
        "requirements_coverage": {
            "functional": len(functional),
            "non_functional": len(non_functional),
        },
    }

    logger.info("[ARCHITECT] Arquitetura gerada: %s", architecture["pattern"])

    return {**ctx, "architecture": architecture, "output": architecture}