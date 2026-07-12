# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/evolution/metabolism/transsulfuration_cycle.py

"""TranssulfurationCycle — converte erros recorrentes em guardrails/safety skills.

Padrão async-first do projeto:
  - `run()` agora é `async def` (era `def` síncrono, bloqueava o event loop
    em qualquer I/O real dentro de `query_relevant_errors` ou
    `route_to_guardrail`).
  - Chamadores devem migrar de `cycle.run(candidate)` para
    `await cycle.run(candidate)`.
  - `_run_maybe_async()` cobre com segurança os dois cenários possíveis para
    as dependências externas (`query_relevant_errors`, `route_to_guardrail`):
    caso já sejam `async def`, são aguardadas diretamente; caso ainda sejam
    funções síncronas legadas, rodam em thread pool via `asyncio.to_thread`.
    Isso evita o risco de envolver uma função já-async em `to_thread`
    (o que faria o corpo da coroutine nunca ser de fato executado/aguardado).
"""

import asyncio
import logging

from iaglobal.evolution.metabolism.homocysteine_pool import CandidateSkill, homocysteine_pool
from iaglobal.memory.memory_error import query_relevant_errors
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal")

GUARDRAIL_FREQUENCY_THRESHOLD = 3


async def _run_maybe_async(func, *args, **kwargs):
    """Chama `func` (síncrona ou assíncrona) sem bloquear o event loop.

    - Se `func` é `async def`, aguarda diretamente.
    - Se `func` é síncrona, roda em thread pool (`asyncio.to_thread`),
      cobrindo também o caso raro de retornar uma coroutine (ex: wrapper,
      `functools.partial` sobre um método async).
    """
    if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)

    result = await asyncio.to_thread(func, *args, **kwargs)
    if asyncio.iscoroutine(result):
        return await result
    return result


class TranssulfurationCycle:
    """Ciclo de Transulfuração — erros recorrentes viram proteção.

    Homocisteína → Cistationina → Cisteína: subprodutos tóxicos (erros
    recorrentes) são desviados do fluxo normal e convertidos em guardrails
    (glutationa) antes de se acumularem e degradarem o sistema.
    """

    def __init__(self, frequency_threshold: int = GUARDRAIL_FREQUENCY_THRESHOLD):
        self.frequency_threshold = frequency_threshold

    async def run(self, candidate: CandidateSkill) -> bool:
        """Avalia se `candidate` deve ser promovido a guardrail.

        Retorna True se o erro associado é frequente o bastante (>= threshold)
        e a promoção a guardrail foi bem-sucedida; False caso contrário.
        """
        logger.info(
            "[TRANSSULFURATION] Avaliando '%s' para rota de proteção",
            candidate.skill.name,
        )

        try:
            errors = await _run_maybe_async(
                query_relevant_errors, candidate.source_gap or candidate.skill.name, top_k=5
            )
            max_freq = max((e.get("count", 1) for e in errors), default=0)
        except Exception as e:
            logger.warning("[TRANSSULFURATION] Erro ao consultar memória de falhas: %s", e)
            max_freq = 0

        if max_freq >= self.frequency_threshold:
            success = await _run_maybe_async(homocysteine_pool.route_to_guardrail, candidate)
            if success:
                logger.info(
                    "[TRANSSULFURATION] '%s' → GUARDRAIL (freq=%d ≥ threshold=%d) ✓",
                    candidate.skill.name, max_freq, self.frequency_threshold,
                )
            else:
                logger.warning(
                    "[TRANSSULFURATION] '%s' atingiu threshold (freq=%d) mas route_to_guardrail falhou",
                    candidate.skill.name, max_freq,
                )
            return success

        logger.info(
            "[TRANSSULFURATION] '%s' frequência insuficiente (max=%d < %d) — mantendo",
            candidate.skill.name, max_freq, self.frequency_threshold,
        )
        return False
