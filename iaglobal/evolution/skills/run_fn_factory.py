# iaglobal/evolution/skills/run_fn_factory.py

import asyncio
from typing import Dict, Any, Optional, Callable

from iaglobal.utils.logger import logger
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.bandit import BanditPolicy

# 🔒 CACHE DE BANDITS ASSÍNCRONO
# Evita deadlocks no Event Loop do asyncio

_bandit_registry: Dict[str, BanditPolicy] = {}
_registry_lock = asyncio.Lock()

async def _get_or_create_bandit(skill_name: str) -> BanditPolicy:
    """Recupera ou instancia a política Bandit de forma assíncrona e segura."""
    async with _registry_lock:
        if skill_name not in _bandit_registry:
            # Em um cenário real, você injetaria o engine de crédito aqui se necessário
            # ou usaria o engine global configurado pelo Bootstrap
            _bandit_registry[skill_name] = BanditPolicy(
                credit=CreditAssignmentEngine(), 
                actions=["creative", "precise", "balanced"]
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
    # A engine é injetada ou instanciada tardiamente
    engine = credit or CreditAssignmentEngine()

    if template_type == "llm":
        # Retorna a função que já utiliza o Bandit assíncrono internamente
        return _make_llm_run_fn(skill_name, template_prompt, engine)
    
    elif template_type == "deterministic":
        return _make_deterministic_run_fn(skill_name, template_prompt)
    
    else:
        logger.warning(f"[RUN-FN] Tipo de template desconhecido: {template_type}")
        return None

# --- Nota de Implementação ---
# Para que o seu sistema pare de emitir 'SEM run_fn', certifique-se de que 
# ao registrar a skill no seu Registry, você faça:
# skill_instance.run_fn = make_dynamic_run_fn(...)

import re
import asyncio
from typing import Dict, Any, Callable

# IMPORTANTE: Certifique-se de que o bandit e o credit 
# possuam métodos async se forem realizar I/O ou DB access
from iaglobal.utils.logger import logger

def _make_llm_run_fn(
    skill_name: str, 
    template_prompt: str, 
    credit: 'CreditAssignmentEngine'
) -> Callable:
    """
    Cria run_fn ASSÍNCRONA que invoca a LLM utilizando políticas 
    de Bandit persistentes e thread-safe (async-safe).
    """
    # Recupera a instância global persistente via helper assíncrono
    # Nota: Em um fluxo async, a recuperação deve ser feita antes 
    # ou via um getter que suporte async.
    bandit = _get_or_create_bandit(skill_name)
    
    # 🔒 LOCK ASSÍNCRONO: Não bloqueia a thread, apenas esta corrotina
    execution_lock = asyncio.Lock()

    async def run_fn(ctx: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Sincroniza a seleção e atualização do Bandit via lock assíncrono
            async with execution_lock:
                # Se select_action for um cálculo de memória pura, não precisa de await
                strategy = bandit.select_action(context=skill_name)
            
            # Formatação dinâmica do prompt
            prompt = template_prompt
            try:
                prompt = template_prompt.format(**ctx)
            except KeyError:
                for match in re.findall(r"\{([A-Za-z0-9_]+)\}", template_prompt):
                    prompt = prompt.replace(f"{{{match}}}", str(ctx.get(match, "")))

            logger.info(f"[RUN-FN-LLM] Executando skill '{skill_name}' (estratégia={strategy})")
            
            # --- Invocação real do modelo (Exemplo assíncrono) ---
            # llm_output = await async_route_generate(prompt, strategy)
            llm_output = f"<output>Resultado processado pela estratégia {strategy}</output>"
            # -----------------------------------------------------

            # Limpeza do output
            clean_output = llm_output
            if "<output>" in llm_output:
                match = re.search(r"<output>(.*?)</output>", llm_output, re.DOTALL)
                if match:
                    clean_output = match.group(1).strip()
            
            clean_output = re.sub(r"```[a-zA-Z]*\n", "", clean_output).replace("```", "").strip()

            # Atualização de crédito e bandit
            reward = 1.0 if clean_output else 0.0
            credit.assign_credit(agent_name=skill_name, amount=reward)
            
            async with execution_lock:
                bandit.update(action=strategy, reward=reward)

            return {"output": clean_output, "success": True, "strategy_used": strategy}

        except Exception as e:
            logger.error(f"[RUN-FN-LLM] Falha catastrófica na skill '{skill_name}': {e}")
            credit.assign_credit(agent_name=skill_name, amount=-1.0)
            return {"output": "", "success": False, "error": str(e), "strategy_used": "failed"}

    return run_fn

import asyncio
import copy
import re
from typing import Dict, Any, Callable

from iaglobal.utils.logger import logger

def _make_deterministic_run_fn(skill_name: str, template_prompt: str) -> Callable:
    """
    Cria run_fn assíncrona e determinística para scripts interpretados,
    com mitigação de segurança via Sandbox isolada.
    """
    
    # 🛡️ PROTEÇÃO ADICIONAL: Bloqueio estático rigoroso
    prohibited = ["__subclasses__", "__globals__", "__import__", "eval", "os.", "sys."]
    if any(p in template_prompt for p in prohibited):
        logger.error(f"[RUN-FN-SANITY] Tentativa de quebra de Sandbox detectada na skill '{skill_name}'!")
        async def fail_fn(ctx: Dict[str, Any]):
            return {"output": "Erro: Código rejeitado pela Sandbox.", "success": False}
        return fail_fn

    async def run_fn(ctx: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Função de execução real para rodar em thread separada
            def sync_exec():
                task = ctx.get("task", "")
                safe_builtins = {
                    "abs": abs, "len": len, "str": str, "int": int, "float": float, 
                    "dict": dict, "list": list, "set": set, "tuple": tuple, "range": range,
                    "min": min, "max": max, "sum": sum, "bool": bool
                }
                
                initial_result = {"output": "", "success": True}
                ns = {
                    "__builtins__": safe_builtins,
                    "ctx": copy.deepcopy(ctx), 
                    "task": task, 
                    "result": initial_result
                }
                
                # Executa isoladamente
                exec(template_prompt, ns)
                return ns.get("result", {})

            # 🚀 ISOLAMENTO: Executa o código em uma thread dedicada para não travar o loop
            executed_result = await asyncio.to_thread(sync_exec)
            
            # Validação do contrato
            if not isinstance(executed_result, dict):
                output = str(executed_result)
                success = True
            else:
                output = executed_result.get("output", ctx.get("task", ""))
                success = executed_result.get("success", True)
            
            return {
                "output": output, 
                "success": success,
                "strategy_used": "deterministic"
            }
            
        except Exception as e:
            logger.error(f"[RUN-FN-DET] Erro de execução na skill '{skill_name}': {e}")
            return {
                "output": f"Erro de Runtime: {e}", 
                "success": False, 
                "error": str(e),
                "strategy_used": "deterministic"
            }
            
    return run_fn

# --- Funções Fábrica de Atalho Pré-Definidas ---

# iaglobal/evolution/skills/run_fn_factory.py

def make_summary_run_fn() -> Callable:
    """
    Cria uma função de atalho para sumarização.
    Retorna uma corrotina pronta para ser executada via await.
    """
    prompt = "Resuma o seguinte conteúdo de forma clara e objetiva:\n\n{task}"
    return _make_llm_run_fn("summary", prompt, _default_credit)


def make_analysis_run_fn() -> Callable:
    """
    Cria uma função de atalho para análise crítica.
    Retorna uma corrotina pronta para ser executada via await.
    """
    prompt = "Analise o seguinte conteúdo, identificando padrões, problemas e sugestões de melhoria:\n\n{task}"
    return _make_llm_run_fn("analysis", prompt, _default_credit)


def make_classification_run_fn() -> Callable:
    """
    Cria uma função de atalho para classificação de dados.
    Retorna uma corrotina pronta para ser executada via await.
    """
    prompt = "Classifique o conteúdo abaixo em categorias. Retorne apenas as categorias separadas por vírgula:\n\n{task}"
    return _make_llm_run_fn("classification", prompt, _default_credit)
