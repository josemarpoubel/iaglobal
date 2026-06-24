# iaglobal/graphs/nodes/_search_wikipedia.py

"""
Wikipedia search helper — shared between consolidated and standalone nodes.
Otimizado com checagem dinâmica de assinatura (Async-First) e isolamento de falhas de rede.
"""
import logging
import asyncio
import inspect

# Importa a função base original de busca da Wikipédia
from ._search_shared import wikipedia_search

logger = logging.getLogger(__name__)


async def _wikipedia_async(query: str) -> str:
    """
    Executa a busca na Wikipédia de forma assíncrona e não-bloqueante.
    Detecta dinamicamente a natureza da função base e previne travamentos do laço.
    """
    if not query or not query.strip():
        return ""

    try:
        # 1. Se a função importada for nativamente assíncrona, executa direto
        if inspect.iscoroutinefunction(wikipedia_search):
            result = await wikipedia_search(query)
        else:
            # 2. Se for síncrona, desvia para Thread Pool blindando a thread analítica principal
            result = await asyncio.to_thread(wikipedia_search, query)
            
        return str(result) if result else ""

    except asyncio.TimeoutError:
        logger.debug("[WIKIPEDIA] Timeout atingido ao tentar consultar a API da Wikipédia.")
        return ""
    except Exception as e:
        logger.debug("[WIKIPEDIA] Falha controlada na requisição de rede: %s", e)
        return ""

