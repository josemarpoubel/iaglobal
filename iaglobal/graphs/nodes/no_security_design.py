# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_security_design.py

"""
Security Design Node — Injeta controles de segurança estruturais na arquitetura.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md com telemetria ativa.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.security_design_agent import SecurityDesignAgent

logger = logging.getLogger(__name__)


async def run_security_design(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a análise de design de segurança de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e controles criados para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "security_design_agent_llm"

    requirements = (
        ctx.get("requirements") or ctx.get("memory", {}).get("requirements", {}) or {}
    )
    architecture = (
        ctx.get("architecture") or ctx.get("memory", {}).get("architecture", {}) or {}
    )
    knowledge_context = str(
        ctx.get("knowledge_context", "")
        or ctx.get("memory", {}).get("knowledge", {}).get("summary", "")
    )
    error_context = str(
        ctx.get("error_context", "")
        or ctx.get("memory", {}).get("errors", {}).get("security_design", "")
    )

    design_context = {
        "architecture": architecture,
        "requirements": requirements,
    }

    logger.info(
        "[SECURITY_DESIGN] Iniciando modelagem e injeção de controles de segurança..."
    )

    try:
        agent = SecurityDesignAgent()

        # Como análises de design estático de segurança consomem inferências pesadas de IA,
        # desviamos para Thread Pool se o método for síncrono para proteger o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.analyze):
            result = await agent.analyze(
                design_context=design_context,
                knowledge_context=knowledge_context,
                error_context=error_context,
            )
        else:
            result = await asyncio.to_thread(
                agent.analyze,
                design_context=design_context,
                knowledge_context=knowledge_context,
                error_context=error_context,
            )

        security_design_report = result.get("security_design_report", {}) or {}
        security_requirements = result.get("security_requirements", []) or []
        total_issues = security_design_report.get("total_issues", 0)

        logger.info(
            "[SECURITY_DESIGN] Modelagem finalizada: %d falhas arquiteturais mitigadas.",
            total_issues,
        )

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx)
        return {
            "output": security_design_report,
            "security_design": security_design_report,
            "security_requirements": security_requirements,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.004
                ),  # Custo de inferência estimado do design
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[SECURITY_DESIGN] Falha crítica no pipeline do Security Design Agent: %s",
            e,
        )

        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": {},
            "security_design": {"total_issues": 0, "error": str(e)},
            "security_requirements": [],
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
