# iaglobal/core/orchestrator.py
"""Orchestrator — Core orchestration logic for iaglobal."""

import os
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

import iaglobal._paths as paths

logger = logging.getLogger(__name__)


class Orchestrator:
    """Core Orchestrator — Coordinates agents and pipeline execution.

    Each organism has its own Orchestrator instance with isolated
    organism_id, data_root, and component instances (Bandit, Pipeline, etc.).
    """
    
    _default_instance: Optional['Orchestrator'] = None
    
    def __init__(self, organism_id: str = "default", data_root: Path | None = None) -> None:
        if getattr(self, '_skip_init', False):
            return
        self._skip_init = True
        self.organism_id = organism_id
        self.data_root = data_root or paths.DATA_ROOT
        self.initialized = False
        self.pipeline = None
        self.cpu_affinity = None
        self.evolution_runtime = None
        from iaglobal.evolution.execution_registry import registry as execution_registry
        self.execution_registry = execution_registry
        logger.info("[Orchestrator:%s] Initialized (data_root=%s)", organism_id, self.data_root)
    
    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if not self.initialized:
            await self.initialize()
        if not self.pipeline:
            raise RuntimeError("Pipeline não inicializada")
        task = ctx.get("task") or ctx.get("input", {}).get("task") or ""
        if not task:
            raise RuntimeError("Contexto sem task")
        result = await self.pipeline.execute(
            task,
            metadata=ctx.get("metadata"),
            force=ctx.get("force", False),
        )
        if hasattr(result, "response"):
            return {"response": result.response, "success": result.success, "script_path": result.script_path}
        return {"response": result.get("response") if isinstance(result, dict) else str(result), "success": result.get("success") if isinstance(result, dict) else False}
    
    async def initialize(self) -> None:
        if self.initialized:
            return
        
        logger.info("[Orchestrator:%s] Initializing components...", self.organism_id)
        
        from iaglobal.graphs.credit import CreditAssignmentEngine
        from iaglobal.graphs.bandit import _get_bandit
        
        credit_engine = CreditAssignmentEngine()
        self.bandit = _get_bandit()
        self.bandit.credit_engine = credit_engine
        logger.info("[Orchestrator:%s] Bandit initialized", self.organism_id)
        
        try:
            from iaglobal.pipeline.engine import PipelineEngine
            self.pipeline = PipelineEngine(self)
            logger.info("[Orchestrator:%s] Pipeline initialized", self.organism_id)
        except Exception as e:
            logger.error("[Orchestrator:%s] Pipeline init failed: %s", self.organism_id, e)
            raise
        
        try:
            from iaglobal.execution.cpu_affinity import CpuAffinityManager
            self.cpu_affinity = CpuAffinityManager()
            logger.info("[Orchestrator:%s] CPU affinity initialized", self.organism_id)
        except Exception as e:
            logger.debug("[Orchestrator:%s] CPU affinity skip: %s", self.organism_id, e)
            self.cpu_affinity = None
        
        try:
            if os.environ.get("EVOLUTION_AUTO") == "1":
                from iaglobal.evolution.evolutionruntime import EvolutionRuntime
                from iaglobal.evolution.evolutionengine import EvolutionEngine
                from iaglobal.graphs.graph_builder_v2 import GraphBuilder
                
                self.evolution_runtime = EvolutionRuntime()
                _graph_builder = GraphBuilder()
                _evolution_graph = _graph_builder.build()
                self.evolution_runtime.evolver = EvolutionEngine(_evolution_graph)
                self.evolution_runtime.start()
                logger.info("[Orchestrator:%s] Evolution runtime started", self.organism_id)
        except Exception as e:
            logger.debug("[Orchestrator:%s] Evolution runtime skip: %s", self.organism_id, e)
            self.evolution_runtime = None
        
        self.initialized = True
        
        # Projeto Synapse — inicializa MailboxManager
        from iaglobal.graphs.communication.agent_mailbox import mailbox_manager
        self.mailbox_manager = mailbox_manager
        
        # Bind dinâmico de agentes ao MailboxManager (exemplo)
        self._bind_agents_to_mailboxes()
        
        from iaglobal.core.graceful_shutdown import graceful_shutdown
        from iaglobal.providers.async_http import close_all_sessions
        graceful_shutdown.add_async_callback(close_all_sessions)
        
        logger.info("[Orchestrator:%s] Fully initialized", self.organism_id)
    
    def _bind_agents_to_mailboxes(self):
        """
        Bind dinâmico de agentes ao MailboxManager.
        
        Lei da Obediência: registra compliance antes de bind.
        """
        from iaglobal.obsidian.compliance import compliance_checker
        
        # Exemplo de bind — na prática, isso varre todos os agentes registrados
        try:
            from iaglobal.agents.coder_agent import CoderAgent
            coder = CoderAgent()
            self.mailbox_manager.register_compliance("CoderAgent", approved=True)
            self.mailbox_manager.bind_executor("CoderAgent", coder.generate)
            logger.info("[SYNAPSE] CoderAgent bindado ao MailboxManager")
        except Exception as e:
            logger.debug("[SYNAPSE] Falha ao bindar CoderAgent: %s", e)
        
        try:
            from iaglobal.agents.planner_agent import PlannerAgent
            planner = PlannerAgent()
            self.mailbox_manager.register_compliance("PlannerAgent", approved=True)
            self.mailbox_manager.bind_executor("PlannerAgent", planner.criar_plano_execucao)
            logger.info("[SYNAPSE] PlannerAgent bindado ao MailboxManager")
        except Exception as e:
            logger.debug("[SYNAPSE] Falha ao bindar PlannerAgent: %s", e)
    
    async def start_heartbeat_loop(self, sleep_interval: float = 0.5):
        """
        Inicia loop de heartbeat em background.
        
        Projeto Synapse: mantém sistema reativo — agentes processam mensagens
        conforme chegam, sem orquestração sequencial rígida.
        
        Uso: asyncio.create_task(orchestrator.start_heartbeat_loop())
        """
        logger.info("[SYNAPSE] Iniciando heartbeat loop (interval=%.2fs)", sleep_interval)
        await self.mailbox_manager.run_heartbeat_loop(
            ctx={"orchestrator": self},
            sleep_interval=sleep_interval,
            max_iterations=None  # loop infinito
        )
    
    async def dispatch_to_agent(self, agent_name: str, task: Dict[str, Any]):
        """
        Dispatch de tarefa para agente específico via mailbox.
        
        Projeto Synapse: comunicação ativa — agente processa automaticamente.
        """
        self.mailbox_manager.route_message({
            "type": "task",
            "receiver": agent_name,
            "sender": "orchestrator",
            "payload": task,
        })
        logger.info("[SYNAPSE] Tarefa dispatchada para %s", agent_name)
    
    def run(self, task: str, force: bool = False) -> Dict[str, Any]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            fut = asyncio.run_coroutine_threadsafe(self.async_run_graph_task(task, force=force), loop)
            return fut.result(timeout=int(os.environ.get("RUNNER_TASK_TIMEOUT", "300")))
        except RuntimeError:
            return asyncio.run(self.async_run_graph_task(task, force=force))

    async def async_run_graph_task(self, task: str, force: bool = False, chosen_model: Optional[str] = None, parallel: bool = True) -> Dict[str, Any]:
        from iaglobal.graphs.execution_graph import ExecutionGraph
        from iaglobal.graphs.graph_builder_v2 import GraphBuilder
        
        builder = GraphBuilder()
        graph = builder.build()
        
        ctx = {
            "input": {"task": task},
            "memory": {},
            "force": force,
            "chosen_model": chosen_model,
            "parallel": parallel,
        }
        result = await graph.async_run(ctx)
        return result
    
    async def shutdown(self) -> None:
        logger.info("[Orchestrator:%s] Shutting down...", self.organism_id)
        if self.evolution_runtime:
            try:
                self.evolution_runtime.stop()
            except Exception as e:
                logger.debug("[Orchestrator:%s] Evolution stop error: %s", self.organism_id, e)
        self.initialized = False


def get_orchestrator() -> Orchestrator:
    """Get or create the default orchestrator instance."""
    if Orchestrator._default_instance is None:
        Orchestrator._default_instance = Orchestrator()
    return Orchestrator._default_instance


Orchestrator._default_instance: Optional[Orchestrator] = None
