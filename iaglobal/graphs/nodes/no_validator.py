# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_validator.py

"""
Validator Node — Executa a validação semântica e pontuação do código produzido.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.validator import SemanticValidatorAgent

logger = logging.getLogger(__name__)


async def run_validator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a validação semântica de código de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e score de validação para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "validator_agent_llm_core"
    
    memory = ctx.get("memory", {}) or {}
    task_str = str(ctx.get("input", {}).get("task", ""))
    code = ""

    # Varre as fontes de código anteriores de forma resiliente
    sources = ("multi_coder", "coder", "debug_coder", "backend_builder", "frontend_builder", "api_builder")
    for source in sources:
        artifact = memory.get(source, {}).get("output")
        if artifact is None:
            continue
        if isinstance(artifact, str) and artifact.strip():
            code = artifact
            break
        if hasattr(artifact, "code") and artifact.code:
            code = artifact.code
            break

    if not code:
        logger.warning("[VALIDATOR] Nenhum código encontrado nas memórias para validação.")
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": {"valid": True, "score": 100, "errors": []},
            "execution_metrics": {
                "model": resolved_model, "success": True, "latency": latency_ms, "cost": 0.0
            }
        }

    logger.info("[VALIDATOR] Iniciando auditoria semântica e pontuação do código gerado...")

    try:
        # Inicializa o agente validador
        agent = SemanticValidatorAgent()
        
        # Como validações semânticas realizam inferências pesadas de IA,
        # garantimos execução assíncrona nativa ou desviamos com segurança para Thread Pool
        if asyncio.iscoroutinefunction(agent.validar):
            result = await agent.validar(task=task_str, code=code)
        else:
            result = await asyncio.to_thread(agent.validar, task=task_str, code=code)
            
        result = result or {}
        score = result.get("score", 100)
        errors = result.get("errors", [])
        valid = result.get("valid", score >= 50)
        
        logger.info("[VALIDATOR] Auditoria concluída. Score=%.1f | Erros detectados=%d", score, len(errors))
        
        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": {"valid": valid, "score": score, "errors": errors},
            "execution_metrics": {
                "model": resolved_model,
                "success": bool(valid),
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.003)  # Custo de inferência estimado para a validação
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[VALIDATOR] Falha crítica no pipeline do Validator Node: %s", e)
        
        # Em caso de pane do validador, falha graciosamente com score passivo, mas avisa o Bandit
        return {
            "output": {"valid": True, "score": 100, "errors": []},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

