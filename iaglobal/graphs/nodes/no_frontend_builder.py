# iaglobal/graphs/nodes/no_frontend_builder.py

"""
Frontend Builder Node — Construtor especializado na camada de interface do usuário (Frontend).
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.coder_agent import CoderAgent

logger = logging.getLogger(__name__)


async def run_frontend_builder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a geração de código frontend de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso sintático para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "frontend_builder_coder_llm"
    
    logger.info("[FRONTEND_BUILDER] Iniciando geração da camada de interface e telas...")
    
    # Coleta os dados de forma resiliente do contexto ou das memórias estruturadas
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))
    architecture_data = ctx.get("architecture", {}) or ctx.get("memory", {}).get("architecture", {})
    
    # Enriquece o contexto com as decisões de arquitetura anteriores
    contexto_refinado = "frontend only"
    if architecture_data:
        frontend_tech = architecture_data.get("components", [{}, {}, {}]).get("tech", "react")
        contexto_refinado = f"frontend user interface context using: {frontend_tech}"

    try:
        # Inicializa o agente programador
        agent = CoderAgent()
        
        # Garante a execução assíncrona ou desvia para thread pool
        if asyncio.iscoroutinefunction(agent.generate):
            artifact = await agent.generate(task=task, contexto=contexto_refinado)
        else:
            artifact = await asyncio.to_thread(agent.generate, task=task, contexto=contexto_refinado)
            
        # Extração segura de propriedades do artefato gerado
        code_output = artifact.code if hasattr(artifact, "code") else str(artifact)
        files_output = artifact.files if hasattr(artifact, "files") else {}
        
        # Portão de segurança: validação básica de saída vazia
        is_success = bool(code_output and len(code_output.strip()) > 5)
        
        if is_success:
            logger.info("[FRONTEND_BUILDER] Interface de usuário gerada com sucesso: %d caracteres.", len(code_output))
        else:
            logger.warning("[FRONTEND_BUILDER] Geração retornou código de interface vazio ou inválido.")

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem desempacotar o ctx)
        return {
            "output": code_output,
            "frontend_builder": {
                "output": code_output,
                "files": files_output
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.015)  # Geração de código de interface consome inferência densa
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[FRONTEND_BUILDER] Falha crítica no pipeline do Frontend Builder Agent: %s", e)
        
        return {
            "output": "",
            "frontend_builder": {"output": "", "files": {}, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

