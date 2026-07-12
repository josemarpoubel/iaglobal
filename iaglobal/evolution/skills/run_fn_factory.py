# iaglobal/evolution/skills/run_fn_factory.py

import asyncio
import copy
import re
from typing import Dict, Any, Callable, Optional

from iaglobal.utils.logger import logger
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.telemetry import ExecutionEvent # type: ignore
from iaglobal.graphs.bandit import BanditPolicy # type: ignore

# 🔒 CACHE DE BANDITS ASSÍNCRONO
# Evita deadlocks no Event Loop do asyncio
_bandit_registry: Dict[str, BanditPolicy] = {}
_registry_lock = asyncio.Lock()

async def _get_or_create_bandit(skill_name: str) -> BanditPolicy:
    """Recupera ou instancia a política Bandit de forma assíncrona e segura."""
    async with _registry_lock:
        if skill_name not in _bandit_registry:
            _bandit_registry[skill_name] = BanditPolicy(
                credit=CreditAssignmentEngine()
            )
        return _bandit_registry[skill_name]

def make_dynamic_run_fn(
    skill_name: str,
    template_type: str,
    template_prompt: str,
    credit: Optional[CreditAssignmentEngine] = None
) -> Optional[Callable]:
    """
    Cria run_fn para uma skill dinâmica baseada no template.
    Nota: A execução final da run_fn deve ser tratada como corrotina (await).
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
    skill_name: str,
    template_prompt: str,
    credit: 'CreditAssignmentEngine'
) -> Callable:
    """
    Cria run_fn ASSÍNCRONA que invoca a LLM utilizando políticas 
    de Bandit persistentes e thread-safe (async-safe).
    """
    import random

    execution_lock = asyncio.Lock()
    _strategy_registry: Dict[str, list] = {}

    async def _get_strategies(name: str) -> list:
        if name not in _strategy_registry:
            _strategy_registry[name] = ["creative", "precise", "balanced"]
        return _strategy_registry[name]

    async def run_fn(ctx: Dict[str, Any]) -> Dict[str, Any]:
        try:
            bandit = await _get_or_create_bandit(skill_name)
            strategies = await _get_strategies(skill_name)
            strategy = random.choice(strategies)

            prompt = template_prompt
            if template_prompt:
                try:
                    prompt = template_prompt.format(**ctx)
                except KeyError:
                    for match in re.findall(r"\{([A-Za-z0-9_]+)\}", template_prompt):
                        prompt = prompt.replace(f"{{{match}}}", str(ctx.get(match, "")))
            else:
                prompt = str(ctx.get("task") or ctx.get("code") or "")

            logger.info(f"[RUN-FN-LLM] Executando skill '{skill_name}' (estratégia={strategy})")

            llm_output = ""
            try:
                from iaglobal.providers.provider_router import async_route_generate
                llm_output = await async_route_generate(
                    model=None, prompt=prompt, task_type="general", node_id="skill_executor"
                )
            except Exception as e:
                logger.warning("[RUN-FN-LLM] Falha ao gerar via LLM para %s: %s", skill_name, e)

            clean_output = llm_output or ""
            if "<output>" in clean_output:
                match = re.search(r"<output>(.*?)</output>", clean_output, re.DOTALL)
                if match:
                    clean_output = match.group(1).strip()

            clean_output = re.sub(r"```[a-zA-Z]*\n", "", clean_output).replace("```", "").strip()

            reward = 1.0 if clean_output else 0.0
            event = ExecutionEvent(
                node=skill_name,
                model="dynamic/llm",
                strategy=strategy,
                latency=0.0,
                success=bool(clean_output),
                reward=reward if clean_output else -1.0,
            )
            credit.record(event=event)

            async with execution_lock:
                if hasattr(bandit, 'update') and callable(bandit.update):
                    bandit.update(action=strategy, reward=reward)

            if not clean_output:
                return {"output": "", "success": False, "error": "LLM não retornou output válido", "strategy_used": strategy, "model_used": "dynamic/llm"}

            return {"output": clean_output, "success": True, "strategy_used": strategy, "model_used": "dynamic/llm"}

        except Exception as e:
            logger.error(f"[RUN-FN-LLM] Falha catastrófica na skill '{skill_name}': {e}")
            event = ExecutionEvent(
                node=skill_name,
                model="dynamic/llm",
                strategy="failed",
                latency=0.0,
                success=False,
                reward=-1.0
            )
            credit.record(event=event)
            return {"output": "", "success": False, "error": str(e), "strategy_used": "failed"}

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
        "dict": dict, "list": list, "str": str, "int": int,
        "float": float, "bool": bool, "len": len, "sum": sum,
        "min": min, "max": max, "sorted": sorted, "reversed": reversed,
        "enumerate": enumerate, "zip": zip, "range": range,
        "map": map, "filter": filter, "any": any, "all": all,
        "isinstance": isinstance, "type": type,
    }
    
    async def run_fn(ctx: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not template_prompt:
                return {"output": "", "success": True, "strategy_used": "deterministic_empty"}
            
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
            if stripped.startswith("lambda") or ("(" in stripped and ")" in stripped and ":" in stripped):
                try:
                    tree = ast.parse(stripped, mode="eval")
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                            if node.func.id not in _SAFE_BUILTINS:
                                raise ValueError(f"Função não permitida: {node.func.id}")
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
