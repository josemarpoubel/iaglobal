# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Etapa 7 do ADR-0004 — Bandit feedback loop.

Fecha o terceiro arco da causalidade:

    CAPABILITY_DECISION (id=evt_dec)
        ↓
    [execução da tecnologia]
        ↓
    CAPABILITY_RESULT  (decision_event_id=evt_dec, success, quality_score)
        ↓
    BanditFeedbackObserver
        ↓
    bandit.update_reward(technology, quality, ivm=1.0 if success else 0.0)

O Bandit aprende, ao longo de várias execuções, quais tecnologias
funcionam melhor para cada capability/situação. Causal join explícito:
o resultado carrega a referência ao predecessor (``decision_event_id``)
via EventId, não por tempo.

---

## Recompensa

A função de recompensa é definida **por revisão arquitetural**:

    reward = quality_score       se success
    reward = 0.0                  se failure (sem sinal, evita reforçar ruído)

A fórmula ``reward = 1.0 - quality`` para failure foi explicitamente
**rejeitada** porque produz inversão: uma execução fracassada de
*baixa* qualidade viraria "alta recompensa" (1.0 - 0.1 = 0.9),
reforçando justamente os piores resultados. Foi discutida e descartada
na revisão arquitetural antes da Etapa 7 — ver ADR-0004 § "Consequências"
e este docstring para o raciocínio completo.

Tradeoff documentado: bandit estável em falhas, acumula valor em
sucessos. Otimista por design — exploração via epsilon-greedy cobre
o lado de falhas.

---

## Idempotência

O observer **não** deduplica. Replay de eventos (via EventStore ou
similar)creditaria o Bandit múltiplas vezes para o mesmo resultado
real. Esse é o estado atual da arquitetura: a fila é FIFO puro.

Futuro: o EventStore precisará filtrar duplicatas com base em
``Event.id`` (cujas referências já estão imutáveis em
``CapabilityResultEvent.id``).

---

## Contrato tipado

Internamente, o bus serializa (e desserializa) o evento para dict.
O observer **reconstrói** o dataclass ``CapabilityResultEvent``
nesse round-trip porque a alternativa seria ``event.data.get("...")``
— chaves literais em dicts, exatamente o anti-padrão que o ADR-0004
combate (vide § "Consequences" e revisão arquitetural).

O custo do round-trip é desprezível (15 campos, dataclass pequeno)
e a defesa de contrato vale a pena.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from iaglobal.events.event_id import EventId
from iaglobal.events.event_types import EventType
from iaglobal.events.result_event import CapabilityResultEvent
from iaglobal.models.event_bus import bus

if TYPE_CHECKING:
    from iaglobal.graphs.bandit import BanditPolicy

logger = logging.getLogger(__name__)


class BanditFeedbackObserver:
    """Subscreve ``CAPABILITY_RESULT`` e credita o Bandit com base no
    desfecho. Causal join: cada resultado carrega o
    ``decision_event_id`` do seu predecessor, mas o observer não
    precisa dele — ``selected_technology`` é a arm Bandit.

    Auto-wiring acontece em :func:`iaglobal.graphs.bandit._get_bandit`
    quando o singleton é instanciado pela primeira vez. Em testes
    sem singleton, basta instanciar diretamente:

        bandit = BanditPolicy()
        BanditFeedbackObserver(bandit)
    """

    def __init__(self, bandit: "BanditPolicy") -> None:
        self._bandit = bandit
        bus.subscribe(EventType.CAPABILITY_RESULT, self._on_result)

    def _on_result(self, event) -> None:
        payload = getattr(event, "data", None)
        if not isinstance(payload, dict):
            return

        # Constrói o dataclass tipado a partir do dict — força o
        # consumer a usar o contrato (campos/atributos com tipos),
        # não chaves literais de dicionário.
        try:
            result = self._reconstruct(payload)
        except Exception as exc:  # noqa: BLE001 — silencioso no hot path
            logger.debug("[BANDIT_FEEDBACK] incapaz de reconstruir result: %s", exc)
            return

        # Sem tecnologia: caminho legacy fallback; sem arm para creditar.
        if result.selected_technology is None:
            return

        # Recompensa documentada: success proporcional à qualidade;
        # failure zero (ver docstring do módulo para a fórmula rejeitada).
        reward = float(result.quality_score) if result.success else 0.0
        ivm = 1.0 if result.success else 0.0

        self._bandit.update_reward(
            arm=result.selected_technology,
            reward=reward,
            ivm=ivm,
        )

    @staticmethod
    def _reconstruct(payload: dict) -> CapabilityResultEvent:
        """Reconstrói o CapabilityResultEvent a partir do payload.

        Implementei como ``@staticmethod`` para que o caminho de
        bootstrap seja auditável (sem estado oculto da instância).
        Falhas de parsing caem silenciosamente no caller — o bus pode
        emitir dicts degradados e o observer não deve explodir.
        """
        return CapabilityResultEvent(
            id=EventId(payload["id"]),
            event_type=payload["event_type"],
            mission_id=payload["mission_id"],
            created_at=datetime.fromisoformat(payload["created_at"]),
            decision_event_id=EventId(payload["decision_event_id"]),
            capability=payload["capability"],
            selected_technology=payload.get("selected_technology"),
            success=bool(payload.get("success", False)),
            artifact_kind=payload.get("artifact_kind", "unknown"),
            validation_status=payload.get("validation_status", "unknown"),
            quality_score=float(payload.get("quality_score") or 0.0),
            repair_count=int(payload.get("repair_count") or 0),
            latency_ms=float(payload.get("latency_ms") or 0.0),
            provider=payload.get("provider"),
            evidence=payload.get("evidence") or {},
        )
