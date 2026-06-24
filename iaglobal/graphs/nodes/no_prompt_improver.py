# iaglobal/graphs/nodes/no_prompt_improver.py

"""
Prompt Improver — Ativa o PromptImprover de 5 estágios na pipeline.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md com telemetria ativa.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.prompt_improver import PromptImprover, PromptMode

logger = logging.getLogger(__name__)

# Instanciação única do motor de melhoria de prompts
_improver = PromptImprover()


async def run_prompt_improver(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a otimização de prompt em 5 estágios de forma assíncrona e não-bloqueante.
    Mapeia latência, restrições e custos para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "prompt_improver_agent_llm"
    
    memory = ctx.get("memory", {})
    raw_prompt = ""

    # Extração resiliente do prompt bruto de etapas anteriores
    prompt_data = memory.get("prompt_intake", {})
    if isinstance(prompt_data, dict):
        raw_prompt = prompt_data.get("prompt", {}).get("normalized", "") or prompt_data.get("output", "")
    if not raw_prompt:
        raw_prompt = memory.get("enhancement", {}).get("output", "")

    task = str(ctx.get("input", {}).get("task", ""))
    if not raw_prompt:
        raw_prompt = task
        
    if not raw_prompt or len(raw_prompt) < 5:
        logger.warning("[PROMPT_IMPROVER] Prompt muito curto ou ausente. Repassando task original.")
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": task,
            "improved_prompt": task,
            "execution_metrics": {
                "model": resolved_model, "success": True, "latency": latency_ms, "cost": 0.0
            }
        }

    knowledge_data = memory.get("knowledge", {})
    knowledge_context = knowledge_data.get("summary", "") if isinstance(knowledge_data, dict) else ""

    logger.info("[PROMPT_IMPROVER] Ativando motor de otimização de 5 estágios de forma não-bloqueante...")

    try:
        # Como o processo de 5 estágios realiza análises massivas de strings/LLM de forma síncrona,
        # desviamos a execução inteira para uma thread pool isolada, protegendo o laço de eventos
        def _execute_improver():
            return _improver.improve_with_report(
                raw_prompt=raw_prompt,
                domain="",
                knowledge_context=knowledge_context,
                mode=PromptMode.FULL,
            )

        improved, report = await asyncio.to_thread(_execute_improver)
        
        mode_val = report.mode.value if hasattr(report.mode, 'value') else report.mode
        detected_domains = [d for d, _ in report.detected_domains] if hasattr(report, 'detected_domains') else []
        constraints = report.constraints_applied if hasattr(report, 'constraints_applied') else 0
        
        logger.info(
            "[PROMPT_IMPROVER] Sucesso! %d→%d chars | mod=%s | domínios=%s | restrições=%d",
            report.original_length if hasattr(report, 'original_length') else len(raw_prompt),
            report.final_length if hasattr(report, 'final_length') else len(improved),
            mode_val,
            detected_domains,
            constraints,
        )
        
        latency_ms = (time.time() - start_time) * 1000.0
        report_dict = report.to_dict() if hasattr(report, 'to_dict') else {}

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx)
        return {
            "output": improved,
            "improved_prompt": improved,
            "prompt_improver_report": report_dict,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.004)  # Custo estimado de inferência dos 5 estágios
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.warning("[PROMPT_IMPROVER] Falha no motor de otimização: %s. Utilizando prompt bruto.", e)
        
        # Reporta a falha de comportamento do modelo para o Bandit Policy aprender
        return {
            "output": raw_prompt,
            "improved_prompt": raw_prompt,
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

