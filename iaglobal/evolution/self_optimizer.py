# iaglobal/evolution/self_optimizer.py

import logging
from typing import Dict, Any, Optional, List

from iaglobal.graphs.nodes.no_integrator import build_graph_from_skills
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.evolutionengine import EvolutionEngine
from iaglobal.evolution.evolutionruntime import EvolutionRuntime
from iaglobal.evolution.canonical_graph import canonicalize

# Importações limpas e estritas das abstrações necessárias, sem inflar o escopo global
from iaglobal.evolution.skills.skill import Skill
from iaglobal.evolution.skills.dynamic_registry import dynamic_registry, DynamicSkillRegistry

logger = logging.getLogger(__name__)


class SelfOptimizingAgentSystem:
    """
    Sistema Fachada (Facade) de Otimização Evolutiva Autônoma.
    Gerencia de forma segura o ciclo de vida do Grafo e do Runtime Genético.
    """

    def __init__(
        self,
        graph: Optional[ExecutionGraph] = None,
        evolution_engine: Optional[EvolutionEngine] = None,
        skill_registry: Optional[DynamicSkillRegistry] = None,
    ):
        # Utiliza o dynamic_registry central persistente caso nenhum seja injetado
        self.skill_registry = skill_registry or dynamic_registry
        
        # Garante que as skills dinâmicas do SQLite sejam carregadas na inicialização
        if hasattr(self.skill_registry, "load_dynamic_skills"):
            self.skill_registry.load_dynamic_skills()

        # Se nenhum grafo for fornecido, constrói a topologia inicial a partir do catálogo de skills
        self.graph = graph or build_graph_from_skills(self.skill_registry)
        
        # Inicializa o motor de evolução molecular/genética
        self.engine = evolution_engine or EvolutionEngine(
            graph=self.graph,
        )
        
        # Acopla o runtime em background para escuta de melhoria contínua
        self.runtime = EvolutionRuntime(engine=self.engine)

    def start(self):
        """Inicializa o ambiente de execução e telemetria evolutiva."""
        logger.info("🚀 Starting Self-Optimizing Agent System...")
        
        # Sincroniza e regenera o grafo para capturar mutações recentes antes do boot
        self.refresh_graph_topology()
        
        self.runtime.start()

    def stop(self):
        """Finaliza com segurança o loop de otimização em background."""
        logger.info("🛑 Stopping Self-Optimizing Agent System...")
        self.runtime.stop()

    def refresh_graph_topology(self) -> None:
        """
        Garante o Hot-Swap de código: reconstrói e canoniza a topologia do Grafo
        para que mutações em tempo de execução entrem em vigor imediatamente.
        """
        try:
            logger.debug("[SELF-OPTIMIZER] Sincronizando topologia com o catálogo de skills atualizado...")
            # Recarrega nós a partir do estado atualizado da memória/banco
            if hasattr(self.graph, "nodes"):
                self.graph.nodes = canonicalize(self.graph.nodes)
        except Exception as e:
            logger.error(f"[SELF-OPTIMIZER] Falha ao sincronizar canonicidade do grafo: {e}")

    def status(self) -> Dict[str, Any]:
        """
        Retorna o estado consolidado do runtime, geração e catálogo ativo.
        CORREÇÃO: Acesso seguro ao dicionário interno de skills para evitar o AttributeError.
        """
        runtime_data = self.runtime.status() if hasattr(self.runtime, "status") else {}
        
        # Extração segura diretamente do dicionário privado do registro base
        active_skills: List[Dict[str, Any]] = []
        try:
            # Acessa o mapa interno compartilhado pelo SkillRegistry do seu design
            registry_map = getattr(self.skill_registry, "_skills", {})
            for name, entry in registry_map.items():
                if getattr(entry, "active", True):
                    s = entry.skill
                    active_skills.append({
                        "name": s.name,
                        "version": s.version,
                        "policy": s.execution_policy.value,
                        "inputs": list(s.inputs),
                        "outputs": list(s.outputs),
                        "usage_count": getattr(entry, "usage_count", 0)
                    })
        except Exception as e:
            logger.error(f"[SELF-OPTIMIZER] Erro ao mapear telemetria de skills: {e}")

        data = {
            "runtime": runtime_data,
            "generation": getattr(self.graph, "generation", 0),
            "nodes_count": len(self.graph.nodes) if hasattr(self.graph, "nodes") else 0,
            "graph_hash": getattr(self.graph, "_graph_hash", "indisponível"),
            "skills": active_skills,
        }
        return data

    def resolve_skill(self, skill_name: str) -> Optional[Skill]:
        """Resolve uma skill de forma segura pelo nome através da fachada."""
        return self.skill_registry.get(skill_name)

    def run_task(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa a tarefa no DAG de produção de forma síncrona.
        Aplica a sincronização de topologia antes de rodar para garantir código atualizado.
        """
        self.refresh_graph_topology()
        return self.graph.run(input_data)
