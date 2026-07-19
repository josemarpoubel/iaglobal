# iaglobal/graphs/recovery.py
"""
RecoveryPolicy — Fase 3: Resiliência do pipeline DAG.

Ativado quando execution_graph.py captura MissingContextError.
Decide se o(s) upstream(s) responsável(is) podem ser re-executados
(RESCHEDULE) ou se o ramo deve ser abortado (ABORT).

Circuit breaker embutido: max_attempts_per_node + backoff exponencial.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Set

from iaglobal.utils.logger import get_logger

if TYPE_CHECKING:
    from iaglobal.graphs.node import Node

logger = get_logger("iaglobal")


class RecoveryDecision(str, Enum):
    RESCHEDULE = "RESCHEDULE"
    ABORT = "ABORT"


@dataclass(frozen=True)
class RecoveryConfig:
    max_attempts_per_node: int = 2
    backoff_base_seconds: float = 0.5
    backoff_multiplier: float = 2.0
    key_to_node_map: Dict[str, str] = field(default_factory=dict)


@dataclass
class RecoveryResult:
    decision: RecoveryDecision
    node_id: str
    upstream_ids: List[str]
    attempt_number: int
    reason: str
    elapsed_ms: float


class RecoveryPolicy:
    """
    Gerencia retry de nós que falharam por MissingContextError.
    Cada nó tem orçamento finito de tentativas — sem retry storm.
    """

    def __init__(self, config: Optional[RecoveryConfig] = None):
        self._config = config or RecoveryConfig()
        self._attempt_counts: Dict[str, int] = {}

    async def handle_missing_context(
        self,
        node_id: str,
        missing: List[str],
        execution_state: Optional[Dict[str, object]] = None,
    ) -> RecoveryResult:
        start = time.monotonic()
        upstream_ids = [
            self._config.key_to_node_map.get(k, k) for k in missing
        ]
        attempt_number = self._attempt_counts.get(node_id, 0) + 1

        if attempt_number <= self._config.max_attempts_per_node:
            result = await self._reschedule(
                node_id, upstream_ids, attempt_number, start
            )
        else:
            reason = (
                f"orçamento de recuperação excedido "
                f"({attempt_number-1}/{self._config.max_attempts_per_node})"
            )
            result = await self._abort(node_id, reason, start)

        self._attempt_counts[node_id] = attempt_number
        return result

    async def _reschedule(
        self,
        node_id: str,
        upstream_ids: List[str],
        attempt_number: int,
        start: float,
    ) -> RecoveryResult:
        backoff = self._config.backoff_base_seconds * (
            self._config.backoff_multiplier ** (attempt_number - 1)
        )
        logger.warning(
            "[RecoveryPolicy] %s: contexto ausente, reagendando "
            "upstream=%s (tentativa %d/%d, backoff=%.2fs)",
            node_id,
            upstream_ids,
            attempt_number,
            self._config.max_attempts_per_node,
            backoff,
        )
        await asyncio.sleep(backoff)
        return RecoveryResult(
            decision=RecoveryDecision.RESCHEDULE,
            node_id=node_id,
            upstream_ids=upstream_ids,
            attempt_number=attempt_number,
            reason="upstream reagendado",
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    async def _abort(
        self, node_id: str, reason: str, start: float
    ) -> RecoveryResult:
        logger.error(
            "[RecoveryPolicy] %s: abortando ramo — %s", node_id, reason
        )
        return RecoveryResult(
            decision=RecoveryDecision.ABORT,
            node_id=node_id,
            upstream_ids=[],
            attempt_number=self._attempt_counts.get(node_id, 0) + 1,
            reason=reason,
            elapsed_ms=(time.monotonic() - start) * 1000,
        )
