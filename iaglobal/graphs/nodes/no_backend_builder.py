# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_backend_builder.py

"""
Backend Builder Node — Construtor especializado na camada de serviços de retaguarda (Backend).
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.coder_agent import CoderAgent

logger = logging.getLogger(__name__)


async def run_backend_builder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a geração de código backend de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso sintático para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "backend_builder_coder_llm"

    logger.info(
        "[BACKEND_BUILDER] Iniciando geração da camada de backend e serviços..."
    )

    # Coleta os dados de forma resiliente do contexto ou das memórias estruturadas
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))
    architecture_data = ctx.get("architecture", {}) or ctx.get("memory", {}).get(
        "architecture", {}
    )

    # Enriquece o contexto com as decisões de arquitetura anteriores
    contexto_refinado = "backend only"
    if architecture_data:
        backend_tech = architecture_data.get("components", [{}, {}])[1].get(
            "tech", "python-fastapi"
        )
        contexto_refinado = f"backend architecture context using: {backend_tech}"

    try:
        # Inicializa o agente programador
        agent = CoderAgent()

        # Busca resultados da web para montagem nativa de código
        search_results = ctx.get("search_results", "") or ""

        # Como a geração de código é guiada por LLM, garantimos a execução assíncrona nativa
        if asyncio.iscoroutinefunction(agent.generate):
            artifact = await agent.generate(
                task=task,
                contexto=contexto_refinado,
                search_results=search_results,
            )
        else:
            artifact = await asyncio.to_thread(
                agent.generate,
                task=task,
                contexto=contexto_refinado,
                search_results=search_results,
            )

        # Extração segura de propriedades do artefato gerado
        code_output = artifact.code if hasattr(artifact, "code") else str(artifact)
        files_output = artifact.files if hasattr(artifact, "files") else {}

        # Portão de segurança: se gerar código vazio ou excessivamente curto, considera falha técnica
        is_success = bool(code_output and len(code_output.strip()) > 5)

        if is_success:
            logger.info(
                "[BACKEND_BUILDER] Camada de backend gerada com sucesso: %d caracteres.",
                len(code_output),
            )
        else:
            logger.warning(
                "[BACKEND_BUILDER] Geração retornou código vazio ou inválido."
            )

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx)
        return {
            "output": code_output,
            "backend_builder": {"output": code_output, "files": files_output},
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.015
                ),  # Custo estimado para codificação pesada de LLM
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[BACKEND_BUILDER] Falha crítica no pipeline do Backend Builder Agent: %s",
            e,
        )

        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "",
            "backend_builder": {"output": "", "files": {}, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
