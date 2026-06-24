# iaglobal/graphs/nodes/no_api_design.py

"""
API Design Node — Desenha de forma estruturada os endpoints, contratos e rotas da API.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_api_design(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o desenho e mapeamento de contratos de endpoints da API de forma assíncrona.
    Mapeia latência e integridade das rotas estruturadas para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "api_design_deterministic_engine"
    
    requirements = ctx.get("requirements") or ctx.get("memory", {}).get("requirements", {}) or {}
    architecture = ctx.get("architecture") or ctx.get("memory", {}).get("architecture", {}) or {}

    logger.info("[API_DESIGN] Analisando arquitetura do sistema para mapeamento de endpoints...")

    # CORREÇÃO DO INDEXERROR: Varre os componentes buscando pelo nome correto em vez de índice fixo
    components = architecture.get("components", []) or []
    backend_tech = "fastapi"  # Fallback padrão seguro
    
    for comp in components:
        if isinstance(comp, dict) and comp.get("name") == "backend-service":
            backend_tech = comp.get("tech", "fastapi")
            break

    try:
        functional = requirements.get("functional", []) or []

        # Contrato de endpoints RESTful padrão do ecossistema iaglobal
        endpoints = [
            {
                "path": "/api/v1/health",
                "method": "GET",
                "description": "Health check de infraestrutura",
                "auth": False,
            },
            {
                "path": "/api/v1/users",
                "method": "GET",
                "description": "Listar usuários cadastrados",
                "auth": True,
            },
            {
                "path": "/api/v1/users/{id}",
                "method": "GET",
                "description": "Obter metadados de usuário por ID",
                "auth": True,
            },
            {
                "path": "/api/v1/users",
                "method": "POST",
                "description": "Criar e registrar novo usuário",
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

        logger.info("[API_DESIGN] Desenho de API concluído: %d endpoints mapeados via framework '%s'.", 
                    len(endpoints), backend_tech)
        
        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": api_design,
            "api_design": api_design,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0  # Processamento determinístico puramente local
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[API_DESIGN] Falha crítica no pipeline do API Design Node: %s", e)
        
        return {
            "output": {},
            "api_design": {"framework": backend_tech, "endpoints": [], "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

