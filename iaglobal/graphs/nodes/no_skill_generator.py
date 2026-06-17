from typing import Dict, Any
import logging

from iaglobal.agents.skill_generator_agent import SkillGeneratorAgent

logger = logging.getLogger(__name__)


async def run_skill_generator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    try:
        agent = SkillGeneratorAgent()
        generated = agent.analyze_and_generate()
        count = len(generated)
        logger.info("[SKILL_GENERATOR] Generated %d new skills", count)
        return {
            **ctx,
            "output": generated,
            "generated_skills": generated,
            "skills_generated_count": count,
        }
    except Exception as e:
        logger.exception("[SKILL_GENERATOR] Failed: %s", e)
        return {**ctx, "output": [], "generated_skills": [], "skills_generated_count": 0}
