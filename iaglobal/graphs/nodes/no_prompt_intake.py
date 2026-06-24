# iaglobal/graphs/nodes/no_prompt_intake.py

"""
Prompt Intake Node — Portão de largada. Classifica intenções, domínios e tokens.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md com telemetria ativa.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.intent_classifier_agent import IntentClassifierAgent
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)

# Instanciação única do classificador de intenções
_intent_classifier = IntentClassifierAgent()


async def run_prompt_intake(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a triagem e ingestão inicial do prompt de forma assíncrona.
    Mapeia latência, confiança e sucesso de classificação para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "intent_classifier_agent_llm"
    
    raw = ctx.get("raw_prompt") or ctx.get("input", {}).get("task", "")
    if not raw or not isinstance(raw, str):
        raw = str(ctx.get("input", {}).get("task", ""))
        
    if not raw or not raw.strip():
        logger.warning("[PROMPT_INTAKE] Prompt vazio detectado na largada.")
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "Prompt vazio",
            "prompt": {"raw": "", "normalized": "", "tokens": 0, "intents": []},
            "initial_scope": {"phase": "definition"},
            "execution_metrics": {"model": resolved_model, "success": True, "latency": latency_ms, "cost": 0.0}
        }

    normalized = raw.strip()
    logger.info("[PROMPT_INTAKE] Iniciando classificação cognitiva de intenções e escopo...")

    try:
        # Desvia a execução do classificador para Thread Pool se for síncrono para proteger o laço
        if asyncio.iscoroutinefunction(_intent_classifier.classify):
            classification = await _intent_classifier.classify(normalized)
        else:
            classification = await asyncio.to_thread(_intent_classifier.classify, normalized)

        prompt_def = {
            "raw": raw,
            "normalized": normalized,
            "tokens": len(normalized.split()),
            "intents": classification.get("intents", []),
            "entities": classification.get("entities", {}),
            "domain": classification.get("domain", "unknown"),
            "confidence": classification.get("confidence", 0.0),
        }

        logger.info(
            "[PROMPT_INTAKE] Triagem concluída: domínio=%s | intenções=%s | confiança=%.2f",
            prompt_def["domain"], prompt_def["intents"], prompt_def["confidence"],
        )

        memory = ctx.get("memory", {})
        ag_mailbox = memory.get("agentmailbox", {}) or ctx.get("agentmailbox", {})
        bus = ag_mailbox.get("_agent_bus") or ctx.get("_agent_bus")
        inbox = ag_mailbox.get("_mailbox_manager") or ctx.get("_mailbox_manager")

        # Processamento seguro e não-bloqueante da caixa de entrada em thread pool
        if bus is not None and inbox is not None:
            def _consume_inbox():
                mailbox = inbox.get_or_create("prompt_intake")
                return mailbox.process_inbox(max_messages=5)
            
            msgs = await asyncio.to_thread(_consume_inbox)
            if msgs:
                for msg in msgs:
                    logger.info("[PROMPT_INTAKE] Mensagem recebida de %s: type=%s", msg.sender, msg.type)

        # Publicação assíncrona reativa no AcetylcholineBus para alertar o Enhancement Node
        if bus is not None:
            msg = AgentMessage(
                sender="prompt_intake",
                receiver="enhancement",
                type="prompt_ready",
                payload={
                    "domain": prompt_def["domain"],
                    "intents": prompt_def["intents"],
                    "entities": prompt_def["entities"],
                },
            )
            if asyncio.iscoroutinefunction(bus.publish):
                await bus.publish(msg)
            else:
                await asyncio.to_thread(bus.publish, msg)
            logger.info("[PROMPT_INTAKE] Evento 'prompt_ready' despachado com sucesso via barramento.")

        latency_ms = (time.time() - start_time) * 1000.0
        is_success = "intents" in classification

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem desestruturar o ctx na RAM)
        return {
            "output": prompt_def,
            "prompt": prompt_def,
            "initial_scope": {"phase": "definition"},
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.002)  # Custo de inferência estimado para classificação
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[PROMPT_INTAKE] Falha crítica na largada do pipeline (Intake Node): %s", e)
        
        return {
            "output": {},
            "prompt": {"raw": raw, "normalized": normalized, "tokens": 0, "intents": [], "error": str(e)},
            "initial_scope": {"phase": "definition"},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

