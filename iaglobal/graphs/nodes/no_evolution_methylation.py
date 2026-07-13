# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_evolution_methylation.py

"""
Evolution Methylation Cycle — Valida e promove skills candidatas a production.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md com telemetria ativa.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.metabolism.methylation_cycle import MethylationCycle
from iaglobal.metabolism.homocysteine_pool import homocysteine_pool

logger = logging.getLogger(__name__)

# Instanciação única controlada do ciclo de metilação
_methylation = MethylationCycle()


def _execute_sync_methylation(candidates: list) -> int:
    """Função enclausurada para executar as validações e promoções em disco de forma não-bloqueante."""
    promoted_count = 0
    for candidate in candidates:
        if candidate is not None:
            # Executa o ciclo biológico de metilação estrutural
            if _methylation.run(candidate):
                promoted_count += 1
    return promoted_count


async def run_evolution_methylation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Avalia e promove skills mutadas para produção de forma assíncrona.
    Mapeia latência, candidatos e sucesso operacional para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "methylation_cycle_deterministic_infrastructure"

    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    logger.info(
        "[EVOLUTION_METHYLATION] Iniciando varredura assíncrona por skills candidatas no pool..."
    )

    try:
        # Recupera os candidatos de forma segura desviando para thread se varrer o pool for custoso
        candidates = await asyncio.to_thread(
            homocysteine_pool.get_candidates_for_methylation
        )
        candidates = candidates or []

        if not candidates:
            logger.info(
                "[EVOLUTION_METHYLATION] Nenhuma skill candidata qualificada para avaliação. Ciclo pulado."
            )
            latency_ms = (time.time() - start_time) * 1000.0
            return {
                "output": "Nenhuma skill candidata",
                "evolution_methylation": {"total_candidates": 0, "promoted": 0},
                "execution_metrics": {
                    "model": resolved_model,
                    "success": True,
                    "latency": latency_ms,
                    "cost": 0.0,
                },
            }

        logger.info(
            "[EVOLUTION_METHYLATION] Detectadas %d skills em triagem. Iniciando testes de promoção...",
            len(candidates),
        )

        # DESPACHA TODO O LAÇO DE VALIDAÇÃO E ESCRITA EM DISCO PARA A THREAD POOL ISOLADA
        promoted = await asyncio.to_thread(_execute_sync_methylation, candidates)

        logger.info(
            "[EVOLUTION_METHYLATION] Ciclo concluído com sucesso: %d/%d skills promovidas a production.",
            promoted,
            len(candidates),
        )

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem desestruturar o ctx na RAM)
        return {
            "output": f"{promoted} skills promovidas a production",
            "evolution_methylation": {
                "total_candidates": len(candidates),
                "promoted": promoted,
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0,  # Transações de infraestrutura e persistência locais
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[EVOLUTION_METHYLATION] Falha crítica no pipeline do Methylation Cycle Node: %s",
            e,
        )

        return {
            "output": "0 skills promovidas a production",
            "evolution_methylation": {"total_candidates": 0, "promoted": 0},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
