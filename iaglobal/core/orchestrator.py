# iaglobal/core/orchestrator.py
"""Orchestrator — Core orchestration logic for iaglobal."""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class Orchestrator:
    """Core Orchestrator — Coordinates agents and pipeline execution."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        # Skip re-initialization for singleton
        if getattr(self, '_skip_init', False):
            return
        self._skip_init = True
        self.initialized = False
        self.pipeline = None  # Pipeline engine
        self.cpu_affinity = None
        self.evolution_runtime = None
        from iaglobal.evolution.execution_registry import registry as execution_registry
        self.execution_registry = execution_registry
        logger.info("[Orchestrator] Initialized")
    
    async def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute pipeline with given context.
        
        Args:
            ctx: Execution context with task, memory, etc.
            
        Returns:
            Dict with results and metrics
        """
        if not self.initialized:
            await self.initialize()
        
        # Delegate to pipeline engine
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
        """Initialize orchestrator components."""
        if self.initialized:
            return
        
        logger.info("[Orchestrator] Initializing components...")
        
        # Initialize core components
        from iaglobal.graphs.credit import CreditAssignmentEngine
        from iaglobal.graphs.bandit import _get_bandit
        
        credit_engine = CreditAssignmentEngine()
        self.bandit = _get_bandit()  # Usa singleton global
        self.bandit.credit_engine = credit_engine  # Injeta credit engine no singleton
        logger.info("[Orchestrator] Bandit initialized (singleton global)")
        
        # Initialize pipeline
        try:
            from iaglobal.pipeline.engine import PipelineEngine
            self.pipeline = PipelineEngine(self)  # Passa self como orchestrator
            logger.info("[Orchestrator] Pipeline initialized")
        except Exception as e:
            logger.error("[Orchestrator] Pipeline init failed: %s", e)
            logger.exception("[Orchestrator] Pipeline init failed")
            raise
        
        # Initialize CPU affinity
        try:
            from iaglobal.execution.cpu_affinity import CpuAffinityManager
            self.cpu_affinity = CpuAffinityManager()
            logger.info("[Orchestrator] CPU affinity initialized")
        except Exception as e:
            logger.debug("[Orchestrator] CPU affinity skip: %s", e)
            self.cpu_affinity = None
        
        # Initialize evolution runtime (optional)
        try:
            import os
            if os.environ.get("EVOLUTION_AUTO") == "1":
                from iaglobal.evolution.evolutionruntime import EvolutionRuntime
                from iaglobal.evolution.evolutionengine import EvolutionEngine
                from iaglobal.graphs.graph_builder_v2 import GraphBuilder
                
                self.evolution_runtime = EvolutionRuntime()
                # Wire evolver — graph built on-demand inside evolve_async
                _graph_builder = GraphBuilder()
                _evolution_graph = _graph_builder.build()
                self.evolution_runtime.evolver = EvolutionEngine(_evolution_graph)
                self.evolution_runtime.start()
                logger.info("[Orchestrator] Evolution runtime started with evolver wired")
        except Exception as e:
            logger.debug("[Orchestrator] Evolution runtime skip: %s", e)
            self.evolution_runtime = None
        
        self.initialized = True
        logger.info("[Orchestrator] Fully initialized")
    
    def run(self, task: str, force: bool = False) -> Dict[str, Any]:
        """Synchronous wrapper for run_graph_task."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # Already inside an event loop — create a new task
            fut = asyncio.run_coroutine_threadsafe(self.async_run_graph_task(task, force=force), loop)
            return fut.result(timeout=int(os.environ.get("RUNNER_TASK_TIMEOUT", "300")))
        except RuntimeError:
            # No running loop — simple wrapper
            return asyncio.run(self.async_run_graph_task(task, force=force))

    async def async_run_graph_task(self, task: str, force: bool = False, chosen_model: Optional[str] = None, parallel: bool = True) -> Dict[str, Any]:
        """
        Run graph task asynchronously.
        
        Args:
            task: Task description
            force: Force execution even if cached
            chosen_model: Model to use for LLM calls
            parallel: Run nodes in parallel
            
        Returns:
            Dict with graph execution results
        """
        from iaglobal.graphs.execution_graph import ExecutionGraph
        from iaglobal.graphs.graph_builder_v2 import GraphBuilder
        
        # Build graph
        builder = GraphBuilder()
        graph = builder.build()
        
        # Execute graph
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
        """Graceful shutdown."""
        logger.info("[Orchestrator] Shutting down...")
        
        # Stop evolution runtime if running
        if self.evolution_runtime:
            try:
                self.evolution_runtime.stop()
            except Exception as e:
                logger.debug("[Orchestrator] Evolution stop error: %s", e)
        
        self.initialized = False

def get_orchestrator() -> Orchestrator:
    """Get or create orchestrator instance."""
    global orchestrator
    if orchestrator is None:
        orchestrator = Orchestrator()
    return orchestrator

# Singleton instance
orchestrator: Optional[Orchestrator] = None
