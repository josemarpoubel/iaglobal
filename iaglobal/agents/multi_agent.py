# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/agents/multi_agent.py
"""
Multi-Agent Orchestrator - Geração 9: Delegação via Grafo.

Este módulo agora é apenas uma interface de compatibilidade.
A orquestração real ocorre no nível do grafo (graph builder + topology),
onde cada fase é um nó independente com dependências explícitas:

  planner → task_breakdown → execution_plan
  coder → multi_coder → code_executor
  critic → tester → debugger → validator → fix_validator → debug_coder
  reflexion → evaluator → gap_analyzer → skill_generator → sandbox_validator

O multi_agent NÃO deve instanciar ou chamar agentes diretamente.
Ele recebe a tarefa via prompt do orquestrador e devolve o contexto
para que o grafo decida quais nós executar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from iaglobal.models.task import Task
from iaglobal.utils.logger import logger


@dataclass
class MultiAgentConfig:
    """Configuração passiva para delegação via grafo."""
    task: str
    context: str = ""
    plan: Dict[str, Any] = None
    subtasks: list = None
    
    def __post_init__(self):
        if self.plan is None:
            self.plan = {}
        if self.subtasks is None:
            self.subtasks = []


def build_multi_agent_prompt(task: str, context: str = "", plan: Dict = None) -> str:
    """
    Constrói o prompt estruturado para delegação via grafo.
    
    Este prompt será consumido pelos nós downstream (planner, coder, etc.)
    através do contexto compartilhado do grafo.
    """
    parts = [
        "[MULTI_AGENT DELEGATION]",
        f"Tarefa principal: {task}",
    ]
    
    if context:
        parts.append(f"\n[CONTEXTO]:\n{context}")
    
    if plan:
        parts.append(f"\n[PLANO]:\n{plan}")
    
    parts.append("\n[INSTRUÇÃO]")
    parts.append("Execute as fases do pipeline via grafo:")
    parts.append("1. planner → task_breakdown → execution_plan")
    parts.append("2. coder → multi_coder → code_executor") 
    parts.append("3. critic → tester → debugger → validator → fix_validator → debug_coder")
    parts.append("4. reflexion → evaluator → gap_analyzer → skill_generator → sandbox_validator")
    parts.append("Retorne o código final consolidado.")
    
    return "\n".join(parts)


def run_multi_agent_delegation(task: Union[str, Task], context: str = "", plan: Dict = None) -> MultiAgentConfig:
    """
    Ponto de entrada para delegação via grafo.
    
    NÃO executa agentes diretamente. Apenas prepara o contexto
    para que o grafo execute as fases na ordem correta.
    """
    task_str = str(task)
    
    logger.info("[MULTI_AGENT] Delegando para grafo: %s", task_str[:80])
    
    prompt = build_multi_agent_prompt(task_str, context, plan)
    
    return MultiAgentConfig(
        task=task_str,
        context=context,
        plan=plan or {},
        subtasks=[]
    )


# ─── API de compatibilidade (wrappers legados) ─────────────────────────────

def debug(code: str, error: str, task: Union[str, Task]) -> str:
    """Compatibilidade: delega para nó 'debugger' via grafo."""
    logger.warning("[MULTI_AGENT] debug() chamado - deve usar nó 'debugger' no grafo")
    return f"[DELEGATE_TO_GRAPH] debugger task={task} error={error}"


def reflect(code: str, result: dict, task: Union[str, Task]) -> str:
    """Compatibilidade: delega para nó 'reflexion' via grafo."""
    logger.warning("[MULTI_AGENT] reflect() chamado - deve usar nó 'reflexion' no grafo")
    return f"[DELEGATE_TO_GRAPH] reflexion task={task}"


# Classe legada para compatibilidade com imports existentes
class PipelineOrchestrator:
    """
    DEPRECATED: Use graph-based orchestration instead.
    
    Mantido apenas para compatibilidade com código legado.
    Não instância mais AgentPool nem executa fases internas.
    """
    
    def __init__(self, **kwargs):
        logger.warning("[MULTI_AGENT] PipelineOrchestrator instanciado - use graph-based orchestration")
    
    def resolve(self, task: Union[str, Task], max_iters: int = 3) -> str:
        task_str = str(task)
        logger.info("[MULTI_AGENT] PipelineOrchestrator.resolve() delegando para grafo: %s", task_str[:80])
        return f"[DELEGATE_TO_GRAPH] task={task_str}"


def _default_orchestrator() -> PipelineOrchestrator:
    """Factory de compatibilidade."""
    return PipelineOrchestrator()


class Multi_Agent(PipelineOrchestrator):
    """Alias legado para compatibilidade."""
    pass


def resolver(task: Union[str, Task], max_iters: int = 3) -> str:
    """Compatibilidade: delega para PipelineOrchestrator (que delega para grafo)."""
    logger.warning("[MULTI_AGENT] resolver() chamado - delegando para grafo")
    return _default_orchestrator().resolve(task, max_iters)


__all__ = [
    "MultiAgentConfig",
    "build_multi_agent_prompt", 
    "run_multi_agent_delegation",
    "debug", 
    "reflect",
    "resolver",
    "PipelineOrchestrator",
    "Multi_Agent",
    "_default_orchestrator",
]