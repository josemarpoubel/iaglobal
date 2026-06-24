# iaglobal/graphs/nodes/no_skill_generator.py

"""
Skill Generator Node — Analisa o ecossistema e gera novas habilidades autônomas.
Totalmente integrado às diretrizes de telemetria e concorrência do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.skill_generator_agent import SkillGeneratorAgent

logger = logging.getLogger(__name__)


async def run_skill_generator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a geração de novas habilidades medindo performance, 
    sucesso e custos para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "skill_generator_agent"
    
    logger.info("[SKILL_GENERATOR] Iniciando varredura e meta-geração de novas skills...")
    
    try:
        # Inicializa o agente gerador
        agent = SkillGeneratorAgent()
        
        # Sendo uma tarefa pesada de geração de código, desvia para Thread Pool se for síncrono
        if asyncio.iscoroutinefunction(agent.analyze_and_generate):
            generated = await agent.analyze_and_generate()
        else:
            generated = await asyncio.to_thread(agent.analyze_and_generate)
            
        count = len(generated) if generated else 0
        logger.info("[SKILL_GENERATOR] Sucesso! %d novas skills mutadas e geradas", count)
        
        latency_ms = (time.time() - start_time) * 1000.0
        
        return {
            "output": generated,
            "generated_skills": generated,
            "skills_generated_count": count,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.02)  # Geração de código consome mais tokens
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[SKILL_GENERATOR] Falha crítica durante a geração de skills: %s", e)
        
        # RETORNA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER!
        return {
            "output": [],
            "generated_skills": [],
            "skills_generated_count": 0,
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.005)  # Custo computado até o momento do crash
            }
        }

