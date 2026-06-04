"""RunFnFactory — Gera run_fn (callables) para skills dinâmicas.

Suporta dois tipos de template:
- 'llm': Usa uma LLM com prompt template para executar a skill
- 'deterministic': Usa uma função Python pré-definida

Skills dinâmicas geradas pelo SkillGeneratorAgent usam
este factory para obter run_fn registráveis.
"""

import re
from typing import Dict, Any, Optional, Callable
from iaglobal.utils.logger import logger


def make_dynamic_run_fn(skill_name: str, template_type: str,
                        template_prompt: str) -> Optional[Callable]:
    """Cria run_fn para uma skill dinâmica baseada no template."""
    if template_type == "llm":
        return _make_llm_run_fn(skill_name, template_prompt)
    elif template_type == "deterministic":
        return _make_deterministic_run_fn(skill_name, template_prompt)
    else:
        logger.warning(f"[RUN-FN] Tipo desconhecido: {template_type}")
        return None


def _make_llm_run_fn(skill_name: str, template_prompt: str) -> Callable:
    """Cria run_fn que invoca LLM com prompt template."""
    def run_fn(ctx: Dict) -> Dict:
        task = ctx.get("task", "")
        prompt = template_prompt.replace("{task}", task)
        try:
            from iaglobal.providers.provider_router import route_generate
            result = route_generate(
                model="auto",
                prompt=prompt,
                task_type=skill_name,
            )
            return {"output": result, "success": True}
        except Exception as e:
            logger.warning(f"[RUN-FN:{skill_name}] LLM fallback: {e}")
            try:
                from iaglobal.execution.executor import blackjack_executar_local
                result = blackjack_executar_local("qwen2.5:0.5b", prompt)
                return {"output": result, "success": True}
            except Exception as e2:
                return {"output": f"Erro: {e2}", "success": False, "error": str(e2)}
    return run_fn


def _make_deterministic_run_fn(skill_name: str, template_prompt: str) -> Callable:
    """Cria run_fn determinística baseada em template Python simples."""
    def run_fn(ctx: Dict) -> Dict:
        try:
            task = ctx.get("task", "")
            ns = {"ctx": ctx, "task": task, "result": {}}
            exec(template_prompt, ns)
            output = ns.get("result", task)
            return {"output": output, "success": True}
        except Exception as e:
            return {"output": f"Erro: {e}", "success": False, "error": str(e)}
    return run_fn


def make_summary_run_fn() -> Callable:
    """Run_fn template para skills de sumarização."""
    prompt = (
        "Resuma o seguinte conteúdo de forma clara e objetiva:\n\n{task}"
    )
    return _make_llm_run_fn("summary", prompt)


def make_analysis_run_fn() -> Callable:
    """Run_fn template para skills de análise."""
    prompt = (
        "Analise o seguinte conteúdo, identificando padrões, "
        "problemas e sugestões de melhoria:\n\n{task}"
    )
    return _make_llm_run_fn("analysis", prompt)


def make_classification_run_fn() -> Callable:
    """Run_fn template para skills de classificação."""
    prompt = (
        "Classifique o conteúdo abaixo em categorias. "
        "Retorne apenas as categorias separadas por vírgula:\n\n{task}"
    )
    return _make_llm_run_fn("classification", prompt)


TEMPLATE_REGISTRY = {
    "summary": make_summary_run_fn,
    "analysis": make_analysis_run_fn,
    "classification": make_classification_run_fn,
}
