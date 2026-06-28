# iaglobal/core/orchestrator.py
"""Orchestrator — Core orchestration logic for iaglobal."""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class Orchestrator:
    """Core Orchestrator — Coordinates agents and pipeline execution."""
    
    def __init__(self) -> None:
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
        from iaglobal.pipeline.engine import execute_pipeline
        return await execute_pipeline(ctx)
    
    async def initialize(self) -> None:
        """Initialize orchestrator components."""
        if self.initialized:
            return
        
        logger.info("[Orchestrator] Initializing components...")
        
        # Initialize core components
        from iaglobal.graphs.bandit import BanditPolicy
        from iaglobal.graphs.credit import CreditAssignmentEngine
        
        credit_engine = CreditAssignmentEngine()
        self.bandit = BanditPolicy(credit_engine)
        logger.info("[Orchestrator] Bandit initialized")
        
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
                self.evolution_runtime = EvolutionRuntime()
                self.evolution_runtime.start()
                logger.info("[Orchestrator] Evolution runtime started")
        except Exception as e:
            logger.debug("[Orchestrator] Evolution runtime skip: %s", e)
            self.evolution_runtime = None
        
        self.initialized = True
        logger.info("[Orchestrator] Fully initialized")
    
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
    global orchestrator # Esta linha é crucial
    if orchestrator is None:
        orchestrator = Orchestrator()
    return orchestrator

# Singleton instance
orchestrator: Optional[Orchestrator] = None
