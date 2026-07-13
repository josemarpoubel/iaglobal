# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Architecture Validator Node — Valida a conformidade arquitetural e semântica do código gerado.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.semantic_validator import SemanticValidatorAgent

logger = logging.getLogger(__name__)


async def run_architecture_validator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a validação arquitetural de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso analítico para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "architecture_validator_agent_llm"

    logger.info(
        "[ARCH_VALIDATOR] Iniciando validação semântica e estrutural da arquitetura..."
    )

    # Coleta os dados de entrada de forma resiliente
    coder_data = ctx.get("coder") or ctx.get("memory", {}).get("coder", {})
    code = (
        coder_data.get("output", "")
        if isinstance(coder_data, dict)
        else str(coder_data or "")
    )
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))

    try:
        # Inicializa o agente validador semântico
        agent = SemanticValidatorAgent()

        # Garante a execução assíncrona nativa ou desvia com segurança para Thread Pool
        if asyncio.iscoroutinefunction(agent.validate_async):
            result = await agent.validate_async(code=code, task=task)
        else:
            result = await asyncio.to_thread(agent.validate_async, code=code, task=task)

        # Extrai os dados no formato legado ou dicionário bruto de forma segura
        result_dict = (
            result.to_legacy_dict()
            if hasattr(result, "to_legacy_dict")
            else dict(result)
        )

        logger.info(
            "[ARCH_VALIDATOR] Validação concluída. Estrutura de código auditada com sucesso."
        )

        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result_dict, dict)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result_dict.get("summary", "Validação de arquitetura finalizada"),
            "architecture_validator": result_dict,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.003
                ),  # Custo de inferência estimado do validador
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[ARCH_VALIDATOR] Falha crítica no pipeline do Architecture Validator: %s",
            e,
        )

        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de validação arquitetural",
            "architecture_validator": {"valid": False, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
