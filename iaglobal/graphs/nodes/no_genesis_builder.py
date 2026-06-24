# iaglobal/graphs/nodes/no_genesis_builder.py

"""
Genesis Builder Node — Handler assíncrono para executar o genesis_builder de forma segura.
A biblioteca do agente pode expor `resolve` como função síncrona ou assíncrona.
Este handler detecta ambos os casos e executa corretamente sem bloquear o loop.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
import inspect
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_genesis_builder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler que executa o PipelineOrchestrator.resolve de forma segura e não-bloqueante.
    Mapeia latência, custos e sucesso de inicialização para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "genesis_orchestrator_core_llm"
    
    # Lazy import mantido para preservar o ciclo de inicialização limpa do ecossistema
    from iaglobal.agents.multi_agent import PipelineOrchestrator

    logger.info("[GENESIS_BUILDER] Iniciando bootstrap e orquestração de gênese do ecossistema...")
    
    # Coleta os dados de forma resiliente do contexto ou das memórias
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))

    try:
        agent = PipelineOrchestrator()
        resolve_fn = getattr(agent, "resolve")

        # Inspeção rigorosa de assinatura para evitar Thundering Herds na thread do laço
        if inspect.iscoroutinefunction(resolve_fn):
            result = await resolve_fn(task)
        else:
            # Se não for coroutine function, executa em threadpool para blindar o AcetylcholineBus
            result = await asyncio.to_thread(resolve_fn, task)

            # Caso o método síncrono retorne uma coroutine de forma disfarçada (defensivo)
            if asyncio.iscoroutine(result):
                result = await result

        logger.info("[GENESIS_BUILDER] Bootstrap de pipeline multiagente finalizado com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = result is not None

        # Retorno higienizado cumprindo estritamente as Regras 1, 3 e 5 do AGENTS.md
        return {
            "output": result.get("summary", "Gênese do pipeline concluída") if isinstance(result, dict) else str(result or ""),
            "genesis_builder": {
                "output": result
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.01)  # Orquestrações de gênese costumam gastar mais tokens
            }
        }

    except Exception as exc:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[GENESIS_BUILDER] Falha crítica durante a orquestração de gênese: %s", exc)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha na orquestração de gênese",
            "genesis_builder": {"output": None, "error": str(exc)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

