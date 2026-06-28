# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_architect.py

"""
Architect Node — Componente de desenho de arquitetura de software do iaglobal.
Gera blueprints estruturais com telemetria ativa para o Bandit Policy.
"""
import time
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_architect(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o nó do arquiteto de forma assíncrona e não-bloqueante.
    Mapeia a latência e o sucesso do desenho de arquitetura para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "architect_deterministic_engine"
    
    requirements = ctx.get("requirements") or ctx.get("memory", {}).get("requirements", {}) or {}
    technology_selection = ctx.get("technology_selection") or ctx.get("memory", {}).get("technology_selection", {}) or {}

    functional = requirements.get("functional", []) or []
    non_functional = requirements.get("non_functional", []) or []

    # Extração resiliente da stack tecnológica decidida no passo anterior
    tech_stack = technology_selection.get("stack", {}) or technology_selection.get("technologies", {}) or {}
    
    # Suporta tanto strings diretas quanto listas vindas do nó de tecnologia
    def _extract_tech(value, default):
        if isinstance(value, list) and value:
            return value[0]
        return str(value) if value else default

    backend = _extract_tech(tech_stack.get("backend"), "python-fastapi")
    frontend = _extract_tech(tech_stack.get("frontend"), "react")
    database = _extract_tech(tech_stack.get("database"), "postgresql")

    logger.info("[ARCHITECT] Gerando planta arquitetural e mapeamento de componentes...")

    try:
        # Se no futuro este nó evoluir para chamar um ArchitectAgent via LLM, 
        # o ecossistema já está blindado por este bloco try/except e medição de tempo
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

        logger.info("[ARCHITECT] Arquitetura gerada com sucesso sob o padrão: %s", architecture["pattern"])
        
        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx)
        return {
            "output": architecture,
            "architecture": architecture,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0  # Atualmente computado localmente sem inferência pesada
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[ARCHITECT] Falha crítica no pipeline do Architect Node: %s", e)
        
        return {
            "output": {},
            "architecture": {},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

