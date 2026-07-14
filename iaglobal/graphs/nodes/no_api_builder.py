# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_api_builder.py

"""
API Builder Node — Construtor especializado no design e contratos de endpoints (API).
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.coder_agent import CoderAgent

logger = logging.getLogger(__name__)


async def run_api_builder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a geração dos contratos e rotas da API de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso sintático para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "api_builder_coder_llm"

    logger.info(
        "[API_BUILDER] Iniciando desenvolvimento da camada de rotas e contratos de API..."
    )

    # Coleta os dados de forma resiliente do contexto ou das memórias estruturadas
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))
    architecture_data = ctx.get("architecture", {}) or ctx.get("memory", {}).get(
        "architecture", {}
    )

    # Extrai dinamicamente o contexto do gateway ou padrão de API definido pelo arquiteto
    contexto_refinado = "API design"
    if architecture_data:
        components = architecture_data.get("components", [])
        gateway_tech = "REST"
        for comp in components:
            if comp.get("name") == "api-gateway":
                gateway_tech = comp.get("tech", "REST")
                break
        contexto_refinado = f"API architecture context using: {gateway_tech} and strict endpoints structure."

    try:
        # Inicializa o agente programador
        agent = CoderAgent()

        search_results = ctx.get("search_results", "") or ""

        # Garante a execução assíncrona nativa ou desvia com segurança para thread pool
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

        # Portão de segurança: validação de tamanho mínimo de código gerado
        is_success = bool(code_output and len(code_output.strip()) > 5)

        if is_success:
            logger.info(
                "[API_BUILDER] Camada de rotas e endpoints gerada com sucesso: %d caracteres.",
                len(code_output),
            )
        else:
            logger.warning(
                "[API_BUILDER] Geração retornou código de API vazio ou inválido."
            )

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem desempacotar o ctx na RAM)
        return {
            "output": code_output,
            "api_builder": {"output": code_output, "files": files_output},
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.012
                ),  # Geração de contratos de API consome inferência intermediária
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[API_BUILDER] Falha crítica no pipeline do API Builder Agent: %s", e
        )

        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "",
            "api_builder": {"output": "", "files": {}, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
