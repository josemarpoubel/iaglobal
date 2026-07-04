# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_database_builder.py

"""
Database Builder Node — Construtor especializado na camada de persistência e banco de dados.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.coder_agent import CoderAgent

logger = logging.getLogger(__name__)


async def run_database_builder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a geração de schemas e scripts de banco de dados de forma assíncrona.
    Mapeia latência, custos e sucesso sintático para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "database_builder_coder_llm"
    
    logger.info("[DATABASE_BUILDER] Iniciando geração da camada de persistência e schemas...")
    
    # Coleta os dados de forma resiliente do contexto ou das memórias estruturadas
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))
    architecture_data = ctx.get("architecture", {}) or ctx.get("memory", {}).get("architecture", {})
    
    # Extrai dinamicamente a tecnologia de banco de dados definida pelo arquiteto
    contexto_refinado = "database only"
    if architecture_data:
        components = architecture_data.get("components", [])
        db_tech = "SQL"
        for comp in components:
            if comp.get("name") == "database-layer":
                db_tech = comp.get("tech", "SQL")
                break
        contexto_refinado = f"database schema and script design context strictly using: {db_tech}"

    try:
        # Inicializa o agente programador
        agent = CoderAgent()
        
        # Garante a execução assíncrona ou desvia com segurança para thread pool
        if asyncio.iscoroutinefunction(agent.generate):
            artifact = await agent.generate(task=task, contexto=contexto_refinado)
        else:
            artifact = await asyncio.to_thread(agent.generate, task=task, contexto=contexto_refinado)
            
        # Extração segura de propriedades do artefato gerado
        code_output = artifact.code if hasattr(artifact, "code") else str(artifact)
        files_output = artifact.files if hasattr(artifact, "files") else {}
        
        # Portão de segurança: valida se o script gerado não veio em branco
        is_success = bool(code_output and len(code_output.strip()) > 5)
        
        if is_success:
            logger.info("[DATABASE_BUILDER] Scripts e schemas de banco de dados gerados: %d caracteres.", len(code_output))
        else:
            logger.warning("[DATABASE_BUILDER] Geração retornou código de banco de dados vazio.")

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx)
        return {
            "output": code_output,
            "database_builder": {
                "output": code_output,
                "files": files_output
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.012)  # Inferência focada em schemas estruturados
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[DATABASE_BUILDER] Falha crítica no pipeline do Database Builder Agent: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "",
            "database_builder": {"output": "", "files": {}, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

