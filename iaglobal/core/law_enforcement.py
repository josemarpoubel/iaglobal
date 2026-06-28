# iaglobal/core/law_enforcement.py

import functools
import logging
from typing import Any, Callable
from iaglobal.execution.cpu_affinity import cpu_affinity
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.law_enforcement")

def enforce_universal_laws(func: Callable) -> Callable:
    """
    Decorador de Imposição de Leis Universais.
    
    Vínculo: Consciência (OmniMind) -> Execução (Nodes) -> Metabolismo (CPU Affinity).
    
    Se a 'Lei do Pensamento' for violada (ausência de reasoning/plano no payload),
    o sistema aplica uma penalidade metabólica imediata ao agente.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Tenta extrair o contexto (ctx) dos argumentos
        ctx = None
        for arg in args:
            if isinstance(arg, dict) and "agent_id" in arg:
                ctx = arg
                break
        if not ctx and "ctx" in kwargs:
            ctx = kwargs["ctx"]

        # Executa a função do nó
        result = await func(*args, **kwargs)
        
        if ctx and isinstance(result, dict):
            agent_id = ctx.get("agent_id")
            if not agent_id:
                return result

            # --- VALIDAÇÃO DA LEI DO PENSAMENTO ---
            # Verifica se há um campo de reasoning/plano no resultado ou no contexto
            reasoning = result.get("reasoning") or result.get("plan") or ctx.get("reasoning")
            
            if not reasoning or len(str(reasoning)) < 10:
                # VIOLAÇÃO: Agir sem pensar consome ATP sem gerar fitness
                logger.warning(
                    "🚨 [LEI DO PENSAMENTO] Violação detectada para agente %s. "
                    "Ação sem propósito identificado. Aplicando penalidade metabólica.", 
                    agent_id
                )
                
                # Penalidade: Reduz budget de CPU para o modo de sobrevivência (10%)
                cpu_affinity.survival_mode(agent_id)
                
                # Adiciona aviso ao resultado para que a OmniMind possa orientar o agente no próximo ciclo
                if "logs" not in result:
                    result["logs"] = []
                result["logs"].append("⚠️ Ação penalizada por violação da Lei do Pensamento: falta de reasoning.")
                
        return result
    return wrapper
