# iaglobal/evolution/task_agent_factory.py

import copy
import logging
from typing import Dict, List, Optional, Set, Any

from iaglobal.graphs.node import Node
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.task_analyzer import TaskAnalyzer

logger = logging.getLogger(__name__)


class TaskAgentFactory:
    """
    Fábrica de agentes especializados para uma tarefa específica.
    Sincronizada dinamicamente com o ecossistema de Skills e livre de dependências órfãs.
    """

    # RESOLUÇÃO DO BUG 1 & 2: Mapeamento centralizado usando os identificadores reais das skills nativas
    SKILL_ALIASES = {
        "multi_coder": "coder",
        "web_specialist": "coder",
        "generalist": "coder",
        "critic": "critic",
        "security_reviewer": "security",
        "performance_auditor": "performance",
        "architecture_reviewer": "critic"
    }

    @classmethod
    def inject_specialists(cls, graph: ExecutionGraph, prompt: str, task_type: str = "default") -> bool:
        """
        Analisa o prompt, deriva os agentes necessários e injeta-os de forma segura no grafo.
        """
        try:
            analysis = TaskAnalyzer.analyze(prompt)
            strategies = analysis.get("strategies", set())
            
            # Obtém a lista de agentes especialistas do Analyzer
            agentes_specs = TaskAnalyzer.derive_agents(strategies)
            if not agentes_specs:
                return False

            logger.info(f"[TASK_AGENT] Injetando {len(agentes_specs)} especialistas para o cenário '{task_type}'")
            
            # Coleta os nós existentes para calcular dependências dinâmicas reais e evitar nós órfãos
            existing_node_names = set(graph.get_all_node_names()) if hasattr(graph, "get_all_node_names") else set()
            if not existing_node_names and hasattr(graph, "nodes"):
                existing_node_names = set(graph.nodes.keys())

            nodes_injetados = 0
            for spec in agentes_specs:
                nome = spec["nome"]
                skill_base = spec["skill_base"]
                estrategias = spec.get("estrategias", [task_type])
                descricao = spec.get("descricao", "")

                node = cls._criar_agente(nome, skill_base, estrategias, descricao, task_type, existing_node_names)
                if node:
                    graph.add_node(node)
                    # Registra o novo nó no mapa local para que especialistas subsequentes possam depender dele
                    existing_node_names.add(node.name)
                    nodes_injetados += 1

            return nodes_injetados > 0

        except Exception as e:
            logger.critical(f"[TASK_AGENT] Falha crítica na injeção de topologia dinêmica: {e}", exc_info=True)
            raise RuntimeError(f"Erro fatal na montagem topológica do grafo: {e}")

    @classmethod
    def _criar_agente(
        cls, 
        nome: str, 
        skill_base: str,
        estrategias: List[str], 
        descricao: str,
        task_type: str,
        existing_nodes: Set[str]
    ) -> Optional[Node]:
        """
        Cria um Node agente especialista amarrado ao contrato executável da Skill real.
        """
        # LAZY IMPORT para evitar dependência circular na inicialização do módulo
        from iaglobal.evolution.skills.skill import SKILL_CODER, SKILL_CRITIC
        from iaglobal.evolution.skills.dynamic_registry import dynamic_registry

        # Resolve o nome unificado da skill
        skill_name_real = cls.SKILL_ALIASES.get(skill_base, skill_base)
        
        # Tenta recuperar a Skill real do registro para herdar o comportamento executável
        skill_obj = dynamic_registry.get(skill_name_real)
        
        # Fallback de segurança se a skill não estiver registrada no banco ou memória
        if not skill_obj:
            logger.warning(f"[TASK_AGENT] Skill base '{skill_name_real}' não encontrada no registry. Usando CODER como fallback.")
            skill_obj = SKILL_CODER

        # 🔄 CÁLCULO DE DEPENDÊNCIA DINÂMICA (Fim do Bug das Dependências Órfãs)
        # O nó vai depender do 'planner' se ele existir; caso contrário, roda em paralelo na raiz
        depends_on = []
        if "planner" in existing_nodes:
            depends_on.append("planner")
            
        # Se for um revisor/crítico e houver algum desenvolvedor/coder injetado no grafo, depende dele
        if skill_name_real in ["critic", "security", "performance"]:
            coders_ativos = [n for n in existing_nodes if "developer" in n or "coder" in n or "generalist" in n]
            if coders_ativos:
                # Depende do último codificador adicionado
                depends_on = [coders_ativos[-1]]

        strategy = estrategias[0] if estrategias else task_type
        node_name = f"task_{nome}_{task_type}"

        # Criação do nó integrado com a engine de Skills reais do ecossistema
        node = Node(
            name=node_name,
            run=skill_obj.execute if hasattr(skill_obj, "execute") else skill_obj.run_fn, # Vincula a execução real!
            depends_on=depends_on,
            strategy=strategy,
            critical=False,
            node_type=skill_name_real,
        )
        
        # Metadados de linhagem evolutiva
        node.seed_id = f"task_seed_{nome}"
        node.mutation_id = f"task_{task_type}"
        node.version = skill_obj.version
        node.model_hint = None
        
        # Injeta metadados adicionais de contrato para o SkillExecutor processar sem falhas
        if not hasattr(node, "metadata") or node.metadata is None:
            node.metadata = {}
        node.metadata.update({
            "description": descricao,
            "inputs": list(skill_obj.inputs),
            "outputs": list(skill_obj.outputs),
            "dynamic_specialist": True
        })

        return node


def create_task_specialists(graph: ExecutionGraph, prompt: str, task_type: str = "default") -> bool:
    """Função atalho exposta para o barramento orquestrador do ecossistema."""
    return TaskAgentFactory.inject_specialists(graph, prompt, task_type)
