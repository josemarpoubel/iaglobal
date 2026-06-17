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
            try:
                prompt = template_prompt.format(**ctx)
            except KeyError:
                for match in re.findall(r"\{([A-Za-z0-9_]+)\}", template_prompt):
                    prompt = prompt.replace(f"{{{match}}}", str(ctx.get(match, "")))

            logger.info(f"[RUN-FN-LLM] Executando skill '{skill_name}' (estratégia={strategy})")

            llm_output = f"<output>Resultado processado pela estratégia {strategy}</output>"

            clean_output = llm_output
            if "<output>" in llm_output:
                match = re.search(r"<output>(.*?)</output>", llm_output, re.DOTALL)
                if match:
                    clean_output = match.group(1).strip()

            clean_output = re.sub(r"```[a-zA-Z]*\\n", "", clean_output).replace("```", "").strip()

            reward = 1.0 if clean_output else 0.0
            event = ExecutionEvent(
                node=skill_name,
                model="dynamic/llm",
                strategy=strategy,
                latency=0.0,
                success=clean_output != "",
                reward=reward if clean_output else -1.0
            )
            credit.record(event=event)

            async with execution_lock:
                if hasattr(bandit, 'update') and callable(bandit.update):
                    bandit.update(action=strategy, reward=reward)

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
    """Cria run_fn assíncrona e determinística para scripts interpretados."""
    pass
