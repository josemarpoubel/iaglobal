# iaglobal/pipeline/plan_executor.py
"""
PlanExecutor — interpreta um CapabilityPlan prescritivo step-by-step.

Cada step é resolvido pelo resolvedor correspondente:
  template   → ToolLibrary
  skill      → SkillRegistry
  tool       → ToolLibrary / execução direta
  knowledge  → KnowledgeBase / FAQ lookup
  search     → SearchAgent / busca web
  llm        → CriticAgent.arbitrar_geracao (último recurso)

O output acumulado (artifact) é passado adiante como contexto para steps
posteriores, permitindo que templates alimentem skills, que alimentem LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from iaglobal.pipeline.capability_resolver import CapabilityPlan, PlanStep
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.pipeline.plan_executor")


@dataclass
class ArtifactDescriptor:
    code: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    steps_executed: List[str] = field(default_factory=list)


class PlanExecutor:
    """Interpreta um CapabilityPlan e produz um ArtifactDescriptor."""

    def __init__(self) -> None:
        self._assembled = ""

    async def execute(
        self, plan: CapabilityPlan, ctx: Optional[Dict[str, Any]] = None
    ) -> ArtifactDescriptor:
        if plan.is_empty():
            logger.info("[PLAN] Plano vazio — sem steps para executar")
            return ArtifactDescriptor()

        ctx = ctx or {}
        task = ctx.get("task", "")
        artifact = ArtifactDescriptor()
        accumulated: Dict[str, Any] = {}

        logger.info(
            "[PLAN] Executando plano para %s (%d steps)",
            plan.artifact,
            len(plan.steps),
        )

        for step in plan.steps:
            logger.debug("[PLAN] Step: %s %s", step.kind, step.name)
            result = await self._resolve_step(step, task, accumulated)
            if result is not None:
                accumulated[step.name] = result
                artifact.steps_executed.append(f"{step.kind}:{step.name}")
                if isinstance(result, str) and len(result) > len(artifact.code):
                    artifact.code = result

        artifact.metadata["plan_artifact"] = plan.artifact
        artifact.metadata["steps_total"] = len(plan.steps)
        artifact.metadata["steps_resolved"] = len(artifact.steps_executed)
        logger.info(
            "[PLAN] Concluído: %d/%d steps resolvidos, %d chars",
            len(artifact.steps_executed),
            len(plan.steps),
            len(artifact.code),
        )
        return artifact

    async def _resolve_step(
        self, step: PlanStep, task: str, accumulated: Dict[str, Any]
    ) -> Optional[str]:
        resolvers = {
            "template": self._resolve_template,
            "skill": self._resolve_skill,
            "tool": self._resolve_tool,
            "knowledge": self._resolve_knowledge,
            "search": self._resolve_search,
            "llm": self._resolve_llm,
        }
        resolver = resolvers.get(step.kind)
        if resolver is None:
            logger.warning("[PLAN] Step kind desconhecido: %s", step.kind)
            return None
        return await resolver(step, task, accumulated)

    async def _resolve_template(
        self, step: PlanStep, task: str, accumulated: Dict[str, Any]
    ) -> Optional[str]:
        try:
            from iaglobal.tools.library import ToolLibrary

            lib = ToolLibrary()
            template = lib.get(step.name)
            if template:
                code = (
                    getattr(template, "code", "")
                    or getattr(template, "template", "")
                    or ""
                )
                logger.info(
                    "[PLAN] Template '%s' carregado (%d chars)", step.name, len(code)
                )
                return code
            logger.info("[PLAN] Template '%s' não encontrado na ToolLibrary", step.name)
        except Exception as e:
            logger.debug("[PLAN] Template '%s' erro: %s", step.name, e)
        return None

    async def _resolve_skill(
        self, step: PlanStep, task: str, accumulated: Dict[str, Any]
    ) -> Optional[str]:
        try:
            from iaglobal.evolution.skills.native.skill_registry import skill_registry

            skill = skill_registry.get(step.name)
            if skill and hasattr(skill, "execute"):
                ctx = {"task": task, **accumulated}
                result = (
                    await skill.execute(ctx)
                    if hasattr(skill.execute, "__await__")
                    else skill.execute(ctx)
                )
                code = ""
                if isinstance(result, dict):
                    code = result.get("code", result.get("output", ""))
                elif isinstance(result, str):
                    code = result
                if code:
                    logger.info(
                        "[PLAN] Skill '%s' executada (%d chars)", step.name, len(code)
                    )
                    return code
            logger.info("[PLAN] Skill '%s' não encontrada ou vazia", step.name)
        except Exception as e:
            logger.debug("[PLAN] Skill '%s' erro: %s", step.name, e)
        return None

    async def _resolve_tool(
        self, step: PlanStep, task: str, accumulated: Dict[str, Any]
    ) -> Optional[str]:
        try:
            from iaglobal.tools.library import ToolLibrary

            lib = ToolLibrary()
            tool = lib.get(step.name)
            if tool and hasattr(tool, "fn"):
                ctx = {"task": task, **accumulated}
                result = tool.fn(ctx) if callable(tool.fn) else tool.fn
                code = str(result) if result else ""
                if code:
                    logger.info(
                        "[PLAN] Tool '%s' executada (%d chars)", step.name, len(code)
                    )
                    return code
            logger.info("[PLAN] Tool '%s' não encontrada", step.name)
        except Exception as e:
            logger.debug("[PLAN] Tool '%s' erro: %s", step.name, e)
        return None

    async def _resolve_knowledge(
        self, step: PlanStep, task: str, accumulated: Dict[str, Any]
    ) -> Optional[str]:
        try:
            from iaglobal._paths import KNOWLEDGE_FILE
            import json

            if KNOWLEDGE_FILE.exists():
                data = json.loads(KNOWLEDGE_FILE.read_text(encoding="utf-8"))
                entries = data if isinstance(data, list) else data.get("entries", [])
                relevant = [
                    e
                    for e in entries
                    if any(w in str(e).lower() for w in task.lower().split()[:5])
                ]
                if relevant:
                    text = "\n\n".join(str(e) for e in relevant[:3])
                    logger.info(
                        "[PLAN] Knowledge: %d entradas relevantes", len(relevant)
                    )
                    return text
            logger.debug("[PLAN] Knowledge: sem entradas relevantes")
        except Exception as e:
            logger.debug("[PLAN] Knowledge erro: %s", e)
        return None

    async def _resolve_search(
        self, step: PlanStep, task: str, accumulated: Dict[str, Any]
    ) -> Optional[str]:
        try:
            from iaglobal.tools.web_brain import WebBrain

            brain = WebBrain()
            results = await brain.search_text(task, max_results=3)
            if results:
                text = str(results)
                logger.info("[PLAN] Search: %d chars recuperados", len(text))
                return text
        except Exception as e:
            logger.debug("[PLAN] Search erro: %s", e)
        return None

    async def _resolve_llm(
        self, step: PlanStep, task: str, accumulated: Dict[str, Any]
    ) -> Optional[str]:
        try:
            from iaglobal.agents.critic_agent import _get_critic

            context_str = "\n\n".join(
                f"[{k}]\n{v[:2000]}"
                for k, v in accumulated.items()
                if isinstance(v, str) and v
            )
            prompt = task
            if context_str:
                prompt = f"{task}\n\n[CONTEXTO RESOLVIDO]\n{context_str}"

            response = await _get_critic().arbitrar_geracao(
                node_id=f"plan_executor.{step.name}",
                prompt=prompt,
                task_type=step.name,
            )
            if response:
                logger.info(
                    "[PLAN] LLM step '%s' gerou %d chars", step.name, len(response)
                )
                return str(response)
        except Exception as e:
            logger.debug("[PLAN] LLM step '%s' erro: %s", step.name, e)
        return None
