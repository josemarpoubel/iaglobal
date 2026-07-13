# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
EntropyInterceptor — Mediator entre EntropySentinel e o metabolismo do ecossistema.

Traduz detecção silenciosa em ação observável:
  - Se EntropySentinel recomenda apoptose, publica evento no AcetylcholineBus
  - Se entropia está degradando (trend='degrading'), registra alerta epigenético
  - Expõe o estado entrópico completo para o HealthAggregator via get_immune_state()

Padrão: Interceptor (Observer) — nunca modifica o core do EntropySentinel.
"""

from typing import Any, Dict, Optional

from iaglobal.immunity.entropy_sentinel import entropy_sentinel
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.observability.entropy_interceptor")


async def intercept_execution(
    agent_name: str,
    payload: Any,
    execution_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Intercepta execução, passa pelo EntropySentinel e age se necessário.

    Returns: o mesmo dict de record_execution(), enriquecido com 'action_taken'.
    """
    result = entropy_sentinel.record_execution(agent_name, payload, execution_context)
    action = "none"
    if result.get("apoptosis_recommended"):
        await _publish_apoptosis_event(agent_name, result)
        action = "apoptosis_event_published"
    elif result.get("trend") == "degrading" and result.get("entropy_score", 0) > 0.5:
        await _publish_degradation_alert(agent_name, result)
        action = "degradation_alert_published"
    result["action_taken"] = action
    return result


async def _publish_apoptosis_event(
    agent_name: str, entropy_result: Dict[str, Any]
) -> None:
    """Publica evento de apoptose no AcetylcholineBus para o nó no_apoptosis_kill consumir."""
    try:
        from iaglobal.graphs.comms.acetylcholine_bus import bus
        from iaglobal.graphs.comms.agent_mailbox import AgentMessage

        msg = AgentMessage(
            sender="entropy_sentinel",
            recipient="no_apoptosis_kill",
            content={
                "type": "apoptosis_candidate",
                "agent_name": agent_name,
                "entropy_score": entropy_result.get("entropy_score"),
                "chaos_rate": entropy_result.get("chaos_rate"),
                "total_executions": entropy_result.get("total_executions"),
                "trend": entropy_result.get("trend"),
                "action": "evaluate_apoptosis",
            },
            message_type="apoptosis_candidate",
            priority=5,
        )
        bus.emit(msg)
        logger.warning(
            "[ENTROPY_INTERCEPTOR] 🚀 Apoptose publicada para %s (score=%.2f, trend=%s)",
            agent_name,
            entropy_result.get("entropy_score", 0),
            entropy_result.get("trend", "unknown"),
        )
    except Exception as e:
        logger.debug("[ENTROPY_INTERCEPTOR] Falha ao publicar apoptose: %s", e)


async def _publish_degradation_alert(
    agent_name: str, entropy_result: Dict[str, Any]
) -> None:
    """Publica alerta de degradação para o sistema de memória/epigenética."""
    try:
        from iaglobal.graphs.comms.acetylcholine_bus import bus
        from iaglobal.graphs.comms.agent_mailbox import AgentMessage

        msg = AgentMessage(
            sender="entropy_sentinel",
            recipient="epigenetic_registry",
            content={
                "type": "entropy_degradation",
                "agent_name": agent_name,
                "entropy_score": entropy_result.get("entropy_score"),
                "trend": "degrading",
            },
            message_type="entropy_alert",
            priority=3,
        )
        bus.emit(msg)
    except Exception:
        pass


def get_immune_state() -> Dict[str, Any]:
    """Estado entrópico consolidado para o HealthAggregator.

    Chamado pelo GET /health sem criar dependência circular.
    """
    profiles = entropy_sentinel.get_all_profiles()
    total = len(profiles)
    at_risk = 0
    degrading = 0
    for name, p in profiles.items():
        report = entropy_sentinel.get_entropy_report(name)
        if report and report.get("apoptosis_risk"):
            at_risk += 1
        if report and report.get("entropy_trend") == "degrading":
            degrading += 1
    return {
        "total_profiles": total,
        "agents_at_apoptosis_risk": at_risk,
        "agents_degrading": degrading,
        "apoptosis_threshold": entropy_sentinel._ENTROPY_APOPTOSIS_THRESHOLD,
        "min_executions": entropy_sentinel._MIN_EXECUTIONS_FOR_APOPTOSIS,
    }
