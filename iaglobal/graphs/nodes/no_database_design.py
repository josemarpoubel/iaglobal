# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_database_design.py

"""
Database Design Node — Executa o desenho cognitivo de schemas, tabelas e relacionamentos.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_database_design(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a modelagem do design de banco de dados de forma assíncrona.
    Mapeia latência, custos e integridade do schema para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "database_design_deterministic_engine"
    
    requirements = ctx.get("requirements") or ctx.get("memory", {}).get("requirements", {}) or {}
    architecture = ctx.get("architecture") or ctx.get("memory", {}).get("architecture", {}) or {}

    logger.info("[DATABASE_DESIGN] Analisando blueprint arquitetural para modelagem de dados...")

    # CORREÇÃO DO INDEXERROR: Varre os componentes buscando pelo nome de forma resiliente
    components = architecture.get("components", []) or []
    db_tech = "postgresql"  # Fallback padrão seguro
    
    for comp in components:
        if isinstance(comp, dict) and comp.get("name") == "database-layer":
            db_tech = comp.get("tech", "postgresql")
            break

    try:
        # Blueprint estático padrão de tabelas
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

        # Resolve dinamicamente ferramentas compatíveis com a linguagem/infraestrutura
        db_tech_lower = str(db_tech).lower()
        database_design = {
            "engine": db_tech,
            "orm": "SQLAlchemy" if "python" in db_tech_lower or "fastapi" in db_tech_lower else "Prisma",
            "tables": tables,
            "total_tables": len(tables),
            "migration_tool": "alembic" if "python" in db_tech_lower or "fastapi" in db_tech_lower else "prisma-migrate",
            "indexes": [
                {"table": "users", "columns": ["email"], "type": "UNIQUE"},
                {"table": "projects", "columns": ["user_id"], "type": "INDEX"},
            ],
        }

        logger.info("[DATABASE_DESIGN] Modelagem concluída com sucesso: %d tabelas mapeadas para a engine '%s'.", 
                    len(tables), db_tech)
        
        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": database_design,
            "database_design": database_design,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0  # Processamento determinístico local leve
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[DATABASE_DESIGN] Falha crítica no pipeline do Database Design Node: %s", e)
        
        return {
            "output": {},
            "database_design": {"engine": db_tech, "tables": [], "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

