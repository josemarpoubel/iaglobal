# iaglobal/evolution/self_optimizer.py

import logging
from typing import Dict, Any, Optional

from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.evolutionengine import EvolutionEngine
from iaglobal.evolution.evolutionruntime import EvolutionRuntime
from iaglobal.evolution.canonical_graph import canonicalize
from iaglobal.evolution.skills import (
    SkillRegistry,
    SkillExecutor,
    VersionManager,
    Skill,
    SKILL_PLANNER, SKILL_CODER,
    SKILL_TESTER, SKILL_DEBUGGER,
    SKILL_ARCHITECT,
    SKILL_SEARCH,
    SKILL_SEMANTIC_VALIDATOR,
    SKILL_REVIEWER,
    SKILL_DOCUMENTATION, SKILL_DEPENDENCY,
    SKILL_REQUIREMENTS, SKILL_PRODUCT_MANAGER,
    SKILL_PROMPT_INTAKE, SKILL_RISK_ANALYSIS,
    SKILL_RELEASE, SKILL_METRICS, SKILL_OPTIMIZATION,
    SKILL_KNOWLEDGE,
    SKILL_ENHANCEMENT,
    SKILL_ORCHESTRATOR,
    SKILL_SECURITY_DESIGN,
    SKILL_PERFORMANCE_DESIGN,
    SKILL_SECURITY_AUDIT,
    SKILL_PERFORMANCE_AUDIT,
    SKILL_RESULT_AGENT,
)

logger = logging.getLogger(__name__)

# =======================================================
# SELF-OPTIMIZING SYSTEM
# =======================================================

class SelfOptimizingAgentSystem:
    """
    Sistema que integra:
    - DAG Execution (ExecutionGraph) com Canonicalization
    - Skill Abstraction Layer (skills versionadas)
    - Evolução autônoma de nodes (EvolutionEngine)
    - Runtime resiliente (EvolutionRuntime)
    """

    def __init__(self, interval: int = 60, orchestrator: Any = None):
        # 0️⃣ Skill system (abstração sobre nodes)
        self.skill_registry = SkillRegistry()
        self.skill_executor = SkillExecutor(self.skill_registry)
        self.version_manager = VersionManager()
        self._register_default_skills()

        # 1️⃣ DAG cognitivo (construído a partir de skills)
        if orchestrator is not None:
            from iaglobal.graphs.builder import build_graph_from_skills
            self.graph = build_graph_from_skills(orchestrator, self.skill_registry)
        else:
            self.graph = ExecutionGraph()

        # 2️⃣ Engine de evolução
        self.engine = EvolutionEngine(self.graph)

        # 3️⃣ Runtime background
        self.runtime = EvolutionRuntime(
            evolver=self.engine,
            interval=interval,
            auto_restart=True,
            daemon=True
        )

    # ---------------------------------------------------
    # SKILL BOOTSTRAP
    # ---------------------------------------------------

    def _register_default_skills(self):
        """Registra skills padrão do sistema."""
        default_skills = [
            SKILL_PLANNER, SKILL_CODER,
            SKILL_TESTER, SKILL_DEBUGGER,
            SKILL_ARCHITECT,
            SKILL_SEARCH,
            SKILL_SEMANTIC_VALIDATOR,
            SKILL_REVIEWER,
            SKILL_DOCUMENTATION, SKILL_DEPENDENCY,
            SKILL_REQUIREMENTS, SKILL_PRODUCT_MANAGER,
            SKILL_PROMPT_INTAKE, SKILL_RISK_ANALYSIS,
            SKILL_RELEASE, SKILL_METRICS, SKILL_OPTIMIZATION,
            SKILL_KNOWLEDGE,
            SKILL_ENHANCEMENT,
            SKILL_ORCHESTRATOR,
            SKILL_SECURITY_DESIGN,
            SKILL_PERFORMANCE_DESIGN,
            SKILL_SECURITY_AUDIT,
            SKILL_PERFORMANCE_AUDIT,
            SKILL_RESULT_AGENT,
        ]
        logger.info("🎯 registrando habilidades do sistema ...")
        for skill in default_skills:
            self.skill_registry.register_or_update(skill)
            self.version_manager.register_version(
                skill,
                changelog=f"Registro inicial da skill {skill.name}",
            )
            logger.info("🎯 habilidade '%s' registrada (v%s)", skill.name, skill.version)
        logger.info("🎯 %d habilidades disponíveis!", len(default_skills))

    # ---------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------

    def start(self):
        """Start evolution runtime"""
        logger.info("🚀 Starting Self-Optimizing Agent System...")
        # Canonicaliza o grafo antes de iniciar
        self.graph.nodes = canonicalize(self.graph.nodes)
        self.runtime.start()

    def stop(self):
        """Stop evolution runtime"""
        logger.info("🛑 Stopping Self-Optimizing Agent System...")
        self.runtime.stop()

    def status(self) -> Dict[str, Any]:
        """Retorna estado do runtime + geração + nodes + skills"""
        data = self.runtime.status()
        data.update({
            "generation": self.graph.generation,
            "nodes_count": len(self.graph.nodes),
            "graph_hash": self.graph._graph_hash if hasattr(self.graph, '_graph_hash') else "",
            "skills": [
                {
                    "name": s.name,
                    "version": s.version,
                    "policy": s.execution_policy.value,
                    "inputs": s.inputs,
                    "outputs": s.outputs,
                }
                for s in self.skill_registry.list_skills()
            ],
        })
        return data

    def resolve_skill(self, skill_name: str) -> Optional[Skill]:
        """Resolve uma skill pelo nome."""
        return self.skill_registry.get(skill_name)

    def run_task(self, input_data: Dict[str, Any]):
        """
        Executa o DAG normalmente.
        Todas as métricas ficam disponíveis para evolução.
        """
        return self.graph.run(input_data)
