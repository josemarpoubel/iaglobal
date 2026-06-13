from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


async def run_database_design(ctx: Dict[str, Any]) -> Dict[str, Any]:
    requirements = ctx.get("requirements") or {}
    architecture = ctx.get("architecture") or {}

    components = architecture.get("components", [])
    db_tech = components[3].get("tech", "postgresql") if len(components) > 3 else "postgresql"

    tables = [
        {
            "name": "users",
            "columns": [
                {"name": "id", "type": "UUID", "pk": True},
                {"name": "name", "type": "VARCHAR(255)", "nullable": False},
                {"name": "email", "type": "VARCHAR(255)", "unique": True},
                {"name": "created_at", "type": "TIMESTAMP", "default": "NOW()"},
            ],
        },
        {
            "name": "projects",
            "columns": [
                {"name": "id", "type": "UUID", "pk": True},
                {"name": "user_id", "type": "UUID", "fk": "users.id"},
                {"name": "name", "type": "VARCHAR(255)"},
                {"name": "status", "type": "VARCHAR(50)", "default": "active"},
            ],
        },
    ]

    database_design = {
        "engine": db_tech,
        "orm": "SQLAlchemy" if "python" in db_tech.lower() else "Prisma",
        "tables": tables,
        "total_tables": len(tables),
        "migration_tool": "alembic" if "python" in db_tech.lower() else "prisma-migrate",
        "indexes": [
            {"table": "users", "columns": ["email"], "type": "UNIQUE"},
            {"table": "projects", "columns": ["user_id"], "type": "INDEX"},
        ],
    }

    logger.info("[DATABASE_DESIGN] Schema: %d tabelas, engine=%s", len(tables), db_tech)

    return {**ctx, "database_design": database_design, "output": database_design}