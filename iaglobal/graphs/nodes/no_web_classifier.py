# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_web_classifier.py

"""
Web Classifier Node — Classifica e categoriza conteúdos recuperados da web de forma não-bloqueante.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.enhancement_agent import EnhancementAgent

logger = logging.getLogger(__name__)


async def run_web_classifier(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a classificação e enriquecimento de conteúdo web de forma assíncrona.
    Mapeia latência, custo e sucesso cognitivo para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "web_classifier_agent_llm"
    
    logger.info("[WEB_CLASSIFIER] Iniciando classificação cognitiva de conteúdos coletados na internet...")
    
    # Extração resiliente de dados de contexto das etapas anteriores
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))
    intake = ctx.get("intake", {}) or ctx.get("memory", {}).get("prompt_intake", {})

    try:
        # Inicializa o agente especializado em enriquecimento e classificação
        agent = EnhancementAgent()
        
        # Como classificações realizam inferências pesadas de IA,
        # desviamos para Thread Pool se o método for síncrono para proteger o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.enhance):
            result = await agent.enhance(task=task, intake=intake)
        else:
            result = await asyncio.to_thread(agent.enhance, task=task, intake=intake)
            
        logger.info("[WEB_CLASSIFIER] Classificação e categorização concluídas com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result,
            "web_classifier": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.003)  # Custo de inferência estimado para o classificador
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[WEB_CLASSIFIER] Falha crítica no pipeline do Web Classifier Node: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": {},
            "web_classifier": {"error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

