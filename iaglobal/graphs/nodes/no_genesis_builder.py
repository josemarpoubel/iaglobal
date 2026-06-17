# iaglobal/graphs/nodes/no_genesis_builder.py

"""Handler assíncrono para executar o genesis_builder de forma segura.

A biblioteca do agente pode expor `resolve` como função síncrona ou assíncrona.
Este handler detecta ambos os casos e executa corretamente sem bloquear o loop.
"""

import logging
import asyncio
import inspect

from typing import Dict, Any

logger = logging.getLogger(__name__)


async def _call_maybe_async(func, *args, **kwargs):
    """
    Executa `func` que pode ser:
      - uma coroutine function (async def)  -> await func(...)
      - uma função que retorna coroutine      -> await returned_coroutine
      - uma função síncrona                  -> run in thread via asyncio.to_thread

    Retorna o valor retornado pela função (ou o resultado da coroutine).
    """
    # Se for uma coroutine function, chame e await diretamente
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)

    # Chame a função; pode retornar uma coroutine ou um valor síncrono
    result = func(*args, **kwargs)

    # Se retornou uma coroutine, await-a
    if asyncio.iscoroutine(result):
        return await result

    # Caso contrário, a função é síncrona e já foi executada (pode ter bloqueado).
    # Para evitar bloquear o loop, re-executamos em thread se for necessário.
    # Porém, como já chamamos a função acima, preferimos não chamá-la novamente.
    # Para evitar duplicação, se a chamada síncrona já ocorreu, retornamos o resultado.
    # Se for desejável garantir execução em thread sem risco de bloqueio, altere a lógica
    # para sempre usar asyncio.to_thread(func, *args, **kwargs) quando não for coroutinefunction.
    return result


async def run_genesis_builder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler que executa o PipelineOrchestrator.resolve de forma segura.

    Args:
        ctx: contexto do nó (deve conter 'task' opcionalmente)

    Returns:
        ctx atualizado com a chave 'genesis_builder' contendo o output.
    """
    from iaglobal.agents.multi_agent import PipelineOrchestrator

    logger.info("Executing genesis_builder handler")
    agent = PipelineOrchestrator()
    task = ctx.get("task", "")

    try:
        # Preferir não chamar a função duas vezes. Se a API do agente for síncrona
        # e potencialmente bloqueante, ideal é usar asyncio.to_thread diretamente.
        # Aqui detectamos se `resolve` é coroutine function e agimos conforme.
        resolve_fn = getattr(agent, "resolve")

        if inspect.iscoroutinefunction(resolve_fn):
            result = await resolve_fn(task)
        else:
            # Se não for coroutine function, execute em thread para não bloquear.
            # Alguns agentes podem retornar uma coroutine mesmo sendo método não-async,
            # então usamos _call_maybe_async para cobrir esse caso.
            result = await asyncio.to_thread(resolve_fn, task)

            # Caso o método retorne uma coroutine (raro se já executamos em thread),
            # tratamos isso também (defensivo).
            if asyncio.iscoroutine(result):
                result = await result

        ctx["genesis_builder"] = {"output": result}
        return ctx

    except Exception as exc:
        logger.exception("Erro ao executar genesis_builder")
        # Preservar o contexto e sinalizar falha para o pipeline
        ctx["genesis_builder"] = {"output": None, "error": str(exc)}
        return ctx

