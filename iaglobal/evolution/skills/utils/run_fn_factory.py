# iaglobal/evolution/skills/run_fn_factory.py

import re
import random
from typing import Dict, Any, Callable, Optional

from iaglobal.utils.logger import logger
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.telemetry import ExecutionEvent  # type: ignore
from iaglobal.security.ast_gateway import ASTGateway

# Gateway singleton para AST parsing
_ast_gateway = ASTGateway()

_STRATEGIES = ["creative", "precise", "balanced"]


def make_dynamic_run_fn(
    skill_name: str,
    template_type: str,
    template_prompt: str,
    credit: Optional[CreditAssignmentEngine] = None,
) -> Optional[Callable]:
    """
    Cria run_fn para uma skill dinâmica baseada no template.

    O fluxo de geracao LLM passa pelo portao unico do CriticAgent
    (arbitrar_geracao), que respeita PSC/Lei da Obediencia.
    O BanditPolicy orquestra a selecao de modelo e telemetria IVM.
    """
    engine = credit or CreditAssignmentEngine()

    if template_type == "llm":
        return _make_llm_run_fn(skill_name, template_prompt, engine)
    elif template_type == "deterministic":
        return _make_deterministic_run_fn(skill_name, template_prompt)
    else:
        logger.warning(f"[RUN-FN] Tipo de template desconhecido: {template_type}")
        return None


def _make_llm_run_fn(
    skill_name: str, template_prompt: str, credit: "CreditAssignmentEngine"
) -> Callable:
    """
    Cria run_fn ASSÍNCRONA que invoca o LLM exclusivamente via
    arbitrar_geracao() do CriticAgent — SEM BanditPolicy local.
    """

    async def run_fn(ctx: Dict[str, Any]) -> Dict[str, Any]:
        strategy = random.choice(_STRATEGIES)

        prompt = template_prompt
        if template_prompt:
            try:
                prompt = template_prompt.format(**ctx)
            except KeyError:
                for match in re.findall(r"\{([A-Za-z0-9_]+)\}", template_prompt):
                    prompt = prompt.replace(f"{{{match}}}", str(ctx.get(match, "")))
        else:
            prompt = str(ctx.get("task") or ctx.get("code") or "")

        logger.info(
            "[RUN-FN-LLM] Executando skill '%s' (estrategia=%s)", skill_name, strategy
        )

        llm_output = ""
        try:
            from iaglobal.agents.critic_agent import _get_critic
            import os

            is_shadow = os.environ.get("ARBITER_MODE", "enforce") == "shadow"
            if is_shadow:
                await _get_critic().arbitrar_geracao(
                    node_id=skill_name,
                    prompt=prompt,
                    task_type="general",
                )
                from iaglobal.providers.provider_router import async_route_generate

                llm_output = await async_route_generate(
                    model=None, prompt=prompt, task_type="general", node_id=skill_name
                )
            else:
                llm_output = await _get_critic().arbitrar_geracao(
                    node_id=skill_name,
                    prompt=prompt,
                    task_type="general",
                )
        except Exception as e:
            logger.warning(
                "[RUN-FN-LLM] Falha ao gerar via LLM para %s: %s", skill_name, e
            )

        clean_output = llm_output or ""
        if "<output>" in clean_output:
            match = re.search(r"<output>(.*?)</output>", clean_output, re.DOTALL)
            if match:
                clean_output = match.group(1).strip()

        clean_output = (
            re.sub(r"```[a-zA-Z]*\n", "", clean_output).replace("```", "").strip()
        )

        success = bool(clean_output)
        event = ExecutionEvent(
            node=skill_name,
            model="dynamic/llm",
            strategy=strategy,
            latency=0.0,
            success=success,
            reward=1.0 if clean_output else -1.0,
        )
        credit.record(event=event)

        if not success:
            return {
                "output": "",
                "success": False,
                "error": "LLM nao retornou output valido",
                "strategy_used": strategy,
                "model_used": "dynamic/llm",
            }

        return {
            "output": clean_output,
            "success": True,
            "strategy_used": strategy,
            "model_used": "dynamic/llm",
        }

    return run_fn


def _make_deterministic_run_fn(skill_name: str, template_prompt: str) -> Callable:
    """
    Cria run_fn assíncrona e determinística para scripts interpretados.

    O template_prompt é processado como:
    1. Substitui placeholders {key} pelos valores do contexto
    2. Se for uma expressão lambda, avalia com eval seguro
    3. Caso contrário, retorna o template processado como string

    Segurança: apenas builtins limitados (dict, list, str, int, float, bool, len, sum, min, max, sorted, reversed, enumerate, zip, range, map, filter, any, all, isinstance, hasattr, getattr, setattr, type)
    """
    import ast

    _SAFE_BUILTINS = {
        "dict": dict,
        "list": list,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "len": len,
        "sum": sum,
        "min": min,
        "max": max,
        "sorted": sorted,
        "reversed": reversed,
        "enumerate": enumerate,
        "zip": zip,
        "range": range,
        "map": map,
        "filter": filter,
        "any": any,
        "all": all,
        "isinstance": isinstance,
        "type": type,
    }

    async def run_fn(ctx: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not template_prompt:
                return {
                    "output": "",
                    "success": True,
                    "strategy_used": "deterministic_empty",
                }

            processed = template_prompt
            for key, value in ctx.items():
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        placeholder = "{" + key + "." + subkey + "}"
                        if placeholder in processed:
                            processed = processed.replace(placeholder, str(subvalue))
                placeholder = "{" + key + "}"
                if placeholder in processed:
                    processed = processed.replace(placeholder, str(value))

            result = None

            # Tenta avaliar como expressão Python segura
            stripped = processed.strip()
            if stripped.startswith("lambda") or (
                "(" in stripped and ")" in stripped and ":" in stripped
            ):
                try:
                    result = _ast_gateway.parse(stripped, mode="eval")
                    if not result.valid or not result.tree:
                        raise SyntaxError("Invalid expression")
                    tree = result.tree
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call) and isinstance(
                            node.func, ast.Name
                        ):
                            if node.func.id not in _SAFE_BUILTINS:
                                raise ValueError(
                                    f"Função não permitida: {node.func.id}"
                                )
                    code = compile(tree, "<string>", "eval")
                    eval_ctx = {**_SAFE_BUILTINS, **ctx}
                    result = eval(code, {"__builtins__": {}}, eval_ctx)
                except (SyntaxError, ValueError, NameError, TypeError):
                    result = processed
            else:
                result = processed

            return {
                "output": str(result) if result is not None else "",
                "success": True,
                "strategy_used": "deterministic",
            }
        except Exception as e:
            logger.error(f"[DETERMINISTIC-RUN] Falha na skill '{skill_name}': {e}")
            return {
                "output": "",
                "success": False,
                "error": str(e),
                "strategy_used": "deterministic_failed",
            }

    return run_fn
