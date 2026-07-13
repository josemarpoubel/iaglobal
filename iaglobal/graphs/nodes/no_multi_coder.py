# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_multi_coder.py

"""
Multi-Coder Node — Gera backend, frontend e database de forma paralela e assíncrona.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.multi_coder_agent import MultiCoderAgent

logger = logging.getLogger(__name__)

# Instanciação lazy e controlada do agente multicoder
_agent: MultiCoderAgent = None


def _get_agent() -> MultiCoderAgent:
    global _agent
    if _agent is None:
        _agent = MultiCoderAgent()
    return _agent


async def run_multi_coder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a geração de código multicamadas de forma assíncrona e não-bloqueante.
    Mapeia latência acumulada, custos e falhas parciais para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "multi_coder_agent_llm_parallel"

    memory = ctx.get("memory", {})
    prompt_builder_data = memory.get("prompt_builder", {}) or {}

    built_prompt = prompt_builder_data.get(
        "built_prompt", ""
    ) or prompt_builder_data.get("output", "")
    if not built_prompt:
        built_prompt = str(ctx.get("input", {}).get("task", ""))

    if not built_prompt or len(built_prompt) < 10:
        logger.warning(
            "[MULTI_CODER] Prompt muito curto ou vazio. Repassando coder output legado."
        )
        coder_out = memory.get("coder", {}).get("output", "")
        latency_ms = (time.time() - start_time) * 1000.0

        return {
            "output": coder_out,
            "multi_coder": {"status": "passthrough"},
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }

    logger.info(
        "[MULTI_CODER] Ativando geração paralela para backend, frontend e database..."
    )

    try:
        agent = _get_agent()

        # Garante a execução assíncrona nativa ou desvia com segurança para Thread Pool se o método for síncrono
        if asyncio.iscoroutinefunction(agent.generate):
            result = await agent.generate(built_prompt)
        else:
            result = await asyncio.to_thread(agent.generate, built_prompt)

        # Trata falhas de runtime do próprio objeto de resultado retornado
        status = getattr(result, "status", "unknown")
        failures = getattr(result, "failures", 0)
        total_chars = getattr(result, "total_chars", 0)
        parts = getattr(result, "parts", {}) or {}

        logger.info(
            "[MULTI_CODER] Ciclo finalizado. Status=%s | Falhas parciais=%d/3 | %d caracteres totais",
            status,
            failures,
            total_chars,
        )

        # Formata o agregado final de códigos estruturados
        multi_output = (
            "\n\n".join(f"# === {k.upper()} ===\n{v}" for k, v in parts.items() if v)
            if any(parts.values())
            else ""
        )

        # Portão de segurança: se houver falhas em todas as camadas ou output vazio, marca sucesso como False
        is_success = bool(multi_output and failures < 3)
        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": multi_output,
            "multi_coder": {
                "status": status,
                "parts": parts,
                "total_chars": total_chars,
                "failures": failures,
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.030)
                * (
                    3 - failures
                ),  # Ajusta o custo dinamicamente pelo número de camadas geradas
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[MULTI_CODER] Falha crítica no pipeline do Multi-Coder Agent: %s", e
        )

        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "",
            "multi_coder": {
                "status": "failed",
                "parts": {},
                "total_chars": 0,
                "failures": 3,
                "error": str(e),
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
