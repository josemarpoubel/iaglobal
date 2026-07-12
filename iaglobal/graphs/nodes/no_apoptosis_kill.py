# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_apoptosis_kill.py
"""
Nó de Apoptose — Executa morte programada de agentes/_skills com entropia crítica.

Consumidor de eventos do AcetylcholineBus:
  - Escuta mensagens do tipo "apoptosis_candidate"
  - Avalia se apoptose é justificada (threshold, histórico, contexto)
  - Executa apoptose graceful (drain, serialização, desregistro)
  - Notifica OmniMind para registro no ancestry tree

AXIOMAS IMPLEMENTADOS:
- AXIOMA 6 (Apoptose): Morte programada sem cascata de falhas
- AXIOMA 8 (Sinalização): Consome eventos do barramento celular
- LEI DA ORDEM (Holliwell): Elimina caos para manter homeostase

Fluxo:
  EntropySentinel detecta entropia crítica
       ↓
  EntropyInterceptor publica evento no AcetylcholineBus
       ↓
  no_apoptosis_kill consome evento (este nó)
       ↓
  Avalia critérios (threshold, execuções mínimas, trend)
       ↓
  Se justificado: executa apoptose graceful
       ↓
  OmniMind registra no ancestry tree + vacina para linhagem
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from iaglobal.utils.logger import get_logger
from iaglobal.immunity.entropy_sentinel import entropy_sentinel
from iaglobal.obsidian.omnimind import omni_mind

logger = get_logger("iaglobal.apoptosis_kill")


async def run_apoptosis_kill(
    agent_name: str,
    entropy_report: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executa apoptose de um agente/skill com entropia crítica.
    
    Args:
        agent_name: Nome do agente/skill a ser apoptado
        entropy_report: Relatório entrópico (opcional, será buscado se None)
        context: Contexto adicional (ex: execução atual, dependentes)
    
    Returns:
        {
            "apoptosis_executed": bool,
            "reason": str,
            "agent_name": str,
            "entropy_score": float,
            "chaos_rate": float,
            "timestamp": str,
            "ancestry_registered": bool,
        }
    """
    if entropy_report is None:
        entropy_report = entropy_sentinel.get_entropy_report(agent_name)
    
    if not entropy_report:
        logger.warning("[APOPTOSE] Agente %s não encontrado para apoptose", agent_name)
        return {
            "apoptosis_executed": False,
            "reason": "agent_not_found",
            "agent_name": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    # Critérios de apoptose
    apoptosis_recommended = entropy_report.get("apoptosis_risk", False)
    min_executions_met = entropy_report.get("min_executions_met", False)
    entropy_score = entropy_report.get("last_entropy_score", 0)
    chaos_rate = entropy_report.get("chaos_rate", 0)
    trend = entropy_report.get("entropy_trend", "unknown")
    
    # Decisão
    if not apoptosis_recommended:
        logger.info(
            "[APOPTOSE] %s não atende critérios (apoptosis_risk=False, chaos_rate=%.2f)",
            agent_name, chaos_rate
        )
        return {
            "apoptosis_executed": False,
            "reason": "criteria_not_met",
            "agent_name": agent_name,
            "entropy_score": entropy_score,
            "chaos_rate": chaos_rate,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    if not min_executions_met:
        logger.info(
            "[APOPTOSE] %s entropia alta mas execuções insuficientes (%d < %d)",
            agent_name,
            entropy_report.get("total_executions", 0),
            entropy_sentinel._MIN_EXECUTIONS_FOR_APOPTOSIS
        )
        return {
            "apoptosis_executed": False,
            "reason": "insufficient_executions",
            "agent_name": agent_name,
            "entropy_score": entropy_score,
            "chaos_rate": chaos_rate,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    # Executa apoptose
    logger.error(
        "🚨 [APOPTOSE] Executando apoptose de %s | entropy=%.2f | chaos_rate=%.2f | trend=%s",
        agent_name, entropy_score, chaos_rate, trend
    )
    
    # 1. Drain de execuções em andamento (aguarda conclusão)
    await _drain_executions(agent_name)
    
    # 2. Serializa estado para sucessor (se houver)
    state_snapshot = await _serialize_state(agent_name)
    
    # 3. Desregistra do ecossistema (remove de pools, registries)
    await _unregister_agent(agent_name)
    
    # 4. Registra no ancestry tree + vacina para linhagem
    ancestry_registered = await _register_ancestry(
        agent_name, entropy_report, state_snapshot
    )
    
    # 5. Reseta perfil entrópico (pós-apoptose)
    entropy_sentinel.reset_profile(agent_name)
    
    logger.info(
        "✅ [APOPTOSE] %s apoptado com sucesso | ancestry=%s",
        agent_name, ancestry_registered
    )
    
    return {
        "apoptosis_executed": True,
        "reason": "entropy_critical",
        "agent_name": agent_name,
        "entropy_score": round(entropy_score, 3),
        "chaos_rate": round(chaos_rate, 3),
        "trend": trend,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ancestry_registered": ancestry_registered,
        "state_serialized": state_snapshot is not None,
    }


async def _drain_executions(agent_name: str) -> None:
    """Aguarda conclusões de execuções em andamento antes de apoptose."""
    # TODO: Implementar quando houver tracking de execuções ativas
    # Por enquanto, apenas log
    logger.debug("[APOPTOSE] Drain de %s (no-op por enquanto)", agent_name)
    await asyncio.sleep(0.1)  # Small delay para permitir conclusões pendentes


async def _serialize_state(agent_name: str) -> Optional[Dict[str, Any]]:
    """Serializa estado do agente para sucessor."""
    # TODO: Implementar serialização de estado (skills, memória, configurações)
    logger.debug("[APOPTOSE] Serialização de %s (no-op por enquanto)", agent_name)
    return None


async def _unregister_agent(agent_name: str) -> None:
    """Desregistra agente de pools e registries."""
    # TODO: Implementar desregistro (SkillRegistry, AgentPool, etc.)
    logger.debug("[APOPTOSE] Desregistro de %s (no-op por enquanto)", agent_name)


async def _register_ancestry(
    agent_name: str,
    entropy_report: Dict[str, Any],
    state_snapshot: Optional[Dict[str, Any]],
) -> bool:
    """Registra apoptose no ancestry tree via OmniMind."""
    try:
        omni_mind.emit_signal(
            signal_type="APOPTOSE_EXECUTADA",
            payload={
                "agent_name": agent_name,
                "entropy_score": entropy_report.get("last_entropy_score"),
                "chaos_rate": entropy_report.get("chaos_rate"),
                "trend": entropy_report.get("entropy_trend"),
                "total_executions": entropy_report.get("total_executions"),
                "chaotic_executions": entropy_report.get("chaotic_executions"),
            },
        )
        return True
    except Exception as e:
        logger.error("[APOPTOSE] Falha ao registrar ancestry: %s", e)
        return False


# ==============================================================================
# CONSUMIDOR DE EVENTOS DO BUS
# ==============================================================================

async def start_apoptosis_listener():
    """Inicia listener de eventos de apoptose no AcetylcholineBus."""
    from iaglobal.graphs.communication.acetylcholine_bus import bus
    
    async def on_apoptosis_event(message):
        """Handler para eventos apoptosis_candidate."""
        if message.message_type != "apoptosis_candidate":
            return
        
        content = message.content
        agent_name = content.get("agent_name")
        
        if not agent_name:
            logger.warning("[APOPTOSE] Evento sem agent_name: %s", content)
            return
        
        logger.info(
            "[APOPTOSE] Evento recebido para %s | score=%.2f | trend=%s",
            agent_name,
            content.get("entropy_score", 0),
            content.get("trend", "unknown"),
        )
        
        # Executa apoptose
        result = await run_apoptosis_kill(agent_name, context=content)
        
        # Publica resultado no bus (opcional, para outros nós consumirem)
        if result.get("apoptosis_executed"):
            from iaglobal.graphs.communication.agent_mailbox import AgentMessage
            bus.emit(AgentMessage(
                sender="no_apoptosis_kill",
                recipient="immune_orchestrator",
                content={
                    "type": "apoptosis_completed",
                    "agent_name": agent_name,
                    "reason": result.get("reason"),
                },
                message_type="apoptosis_completed",
            ))
    
    # Subscreve no canal de apoptose
    bus.subscribe("apoptosis_candidate", on_apoptosis_event)
    logger.info("[APOPTOSE] Listener iniciado no AcetylcholineBus")


# Inicialização automática quando o módulo é importado
# (em produção, isso seria chamado pelo Orchestrator no boot)
try:
    loop = asyncio.get_running_loop()
    loop.create_task(start_apoptosis_listener())
except RuntimeError:
    # Sem event loop rodando (ex: teste unitário)
    pass