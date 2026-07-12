# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Orchestrator Pump Node — Garante recarga prévia de SAMe antes de ciclos evolutivos.

Filosofia:
  O `EvoAgent` depende de um orçamento metabólico mínimo (SAMe >= INHIBIT_THRESHOLD)
  para expressar mutações não-críticas. Se o nível inicial for baixo, o sistema inibe
  transformações importantes antes mesmo de iniciar, causando estagnação evolutiva.

  Este nó age como um *pré-condicionador*: inspeciona o pool SAMe antes da etapa
  de evolução e aplica `recharge()` se necessário. Também aciona deep flush no
  `memory_cleaner` quando disponível, removendo ruído que desequilibraria o IVM.

Integração:
  - Entrada: nenhuma dependência obrigatória; opera no contexto global do sistema.
  - Saída: `execution_metrics` com latência/custo/sucesso e `samed_pump_report`.
  - Side-effect: atualiza `SAMePool` e, opcionalmente, chama `memory_cleaner.deep_flush()`.
"""
import time
import asyncio
from typing import Any, Dict, Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.graphs.nodes.orchestrator_pump")

# Limiar configurável por ambiente
PUMP_THRESHOLD = int(__import__("os").environ.get("SAME_PUMP_THRESHOLD", "20"))
PUMP_TARGET = int(__import__("os").environ.get("SAME_PUMP_TARGET", "30"))
RECHARGE_AMOUNT = int(__import__("os").environ.get("SAME_RECHARGE_AMOUNT", "10"))


async def _deep_flush_memory() -> None:
    """
    Tenta executar deep flush no MemoryCleaner, se disponível.
    Não falha o fluxo se o módulo não existir; apenas registra o evento.
    """
    try:
        from iaglobal.graphs.nodes.no_memory_cleaner import run_memory_cleaner
        flush_ctx: Dict[str, Any] = {
            "memory": {},
            "input": {"task": "deep_flush"},
        }
        result = await run_memory_cleaner(flush_ctx)
        cleaned = result.get("memory_clean", {}) if isinstance(result, dict) else {}
        logger.info(
            "[ORCHESTRATOR_PUMP] Deep flush executado | removed=%d",
            cleaned.get("removed", 0) if isinstance(cleaned, dict) else -1,
        )
    except Exception as e:
        logger.debug("[ORCHESTRATOR_PUMP] Deep flush indisponível: %s", e)


async def run_orchestrator_pump(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pré-condiciona o SAMe para evitar bloqueios evolutivos prematuras.

    Args:
        ctx: contexto de execução do grafo.

    Returns:
        Dict contendo:
            - output: relatório textual da operação.
            - samed_pump_report: detalhamento da recarga aplicada.
            - execution_metrics: latência/custo/sucesso para telemetria.
    """
    start = time.time()
    resolved_model = "orchestrator_pump"

    pumped = False
    previous_balance: Optional[int] = None
    current_balance: Optional[int] = None
    agent_name = "orchestrator"

    try:
        from iaglobal.evolution.same_engine import same_pool, INHIBIT_THRESHOLD

        account = same_pool.get_account(agent_name)
        previous_balance = account.balance
        current_balance = previous_balance

        if previous_balance < PUMP_THRESHOLD:
            needed = max(0, PUMP_TARGET - previous_balance)
            same_pool.recharge(agent_name, amount=max(needed, RECHARGE_AMOUNT))
            pumped = True
            current_balance = same_pool.balance(agent_name)

            logger.warning(
                "[ORCHESTRATOR_PUMP] SAMe baixo detectado | agent=%s | before=%d | after=%d | threshold=%d",
                agent_name,
                previous_balance,
                current_balance,
                PUMP_THRESHOLD,
            )

            # Limpeza profilática de memória para reduzir ruído
            await _deep_flush_memory()
        else:
            logger.info(
                "[ORCHESTRATOR_PUMP] SAMe suficiente | agent=%s | balance=%d | threshold=%d",
                agent_name,
                previous_balance,
                PUMP_THRESHOLD,
            )
    except Exception as e:
        logger.warning("[ORCHESTRATOR_PUMP] Falha na verificação/recarga de SAMe: %s", e)

    latency = (time.time() - start) * 1000.0
    success = True

    report = {
        "agent": agent_name,
        "pumped": pumped,
        "previous_balance": previous_balance,
        "current_balance": current_balance,
        "threshold": PUMP_THRESHOLD,
        "target": PUMP_TARGET,
    }

    logger.info(
        "[ORCHESTRATOR_PUMP] Finalizado | pumped=%s | latency=%.2fms",
        pumped,
        latency,
    )

    status = "RECARREGADO" if pumped else "OK"
    output = (
        f"[ORCHESTRATOR_PUMP] SAMe={status} | balance={previous_balance}->{current_balance} "
        f"| threshold={PUMP_THRESHOLD} | target={PUMP_TARGET} | agent={agent_name} "
        f"| lat={latency:.1f}ms"
    )
    return {
        "output": output,
        "samed_pump_report": report,
        "execution_metrics": {
            "model": resolved_model,
            "success": success,
            "latency": latency,
            "cost": 0.0,
        },
    }
