"""TaskAgentFactory — cria agentes especialistas dinamicamente baseados na task."""

import copy
import logging
from typing import Dict, List, Optional, Set

from iaglobal.graphs.node import Node
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.task_analyzer import TaskAnalyzer

logger = logging.getLogger(__name__)


class TaskAgentFactory:
    """
    Fábrica de agentes especializados para uma tarefa específica.

    Analisa o prompt da tarefa e cria agentes com:
    - Nome descritivo da especialidade
    - Estratégias relevantes (web_development, form_handling, etc.)
    - Dependências corretas para participar do DAG
    - Model_hint apropriado
    """

    # Skills base que podem ser especializadas
    SKILL_BASE_MAP = {
        "web_specialist": "multi_coder",
        "form_handler": "multi_coder",
        "theming_specialist": "multi_coder",
        "database_modeler": "multi_coder",
        "api_designer": "multi_coder",
        "blockchain_developer": "multi_coder",
        "generalist": "multi_coder",
        "critic_web": "critic",
        "tester_web": "tester",
        "security_reviewer": "critic",
        "ux_reviewer": "critic",
        "architecture_reviewer": "critic",
        "performance_auditor": "critic",
        "gap_analyzer": "critic",
    }

    # Aliases: skill_base dos agentes → node_type real no grafo
    SKILL_ALIASES = {
        "coder": "multi_coder",
    }

    # Dependências por skill base (Pipeline V3)
    DEPENDS_ON_MAP = {
        "multi_coder": ["planner"],
        "critic": ["reviewer"],
        "tester": ["performance_audit"],
    }

    @classmethod
    def create_specialist_agents(cls, task: str, graph: ExecutionGraph) -> List[Node]:
        """
        Cria agentes especialistas para a task e os adiciona ao grafo.
        Retorna a lista de agentes criados.
        """
        analysis = TaskAnalyzer.analyze(task)
        strategies = analysis["strategies"]
        agentes_recomendados = analysis["agentes_recomendados"]
        technologies = analysis["technologies"]
        task_type = analysis["task_type"]

        if not strategies:
            logger.info(f"[TASK_AGENT] Nenhuma estratégia detectada para: {task[:60]}...")
            return []

        logger.info(
            f"[TASK_AGENT] Analisando task: type={task_type} "
            f"| strategies={strategies} | techs={technologies}"
        )

        created = []
        for recomendacao in agentes_recomendados:
            nome = recomendacao["nome"]
            skill_base = recomendacao["skill_base"]
            estrategias = recomendacao["estrategias"]
            descricao = recomendacao["descricao"]

            # Verifica se já existe agente similar
            if cls._agente_ja_existe(graph, nome, estrategias):
                logger.info(f"[TASK_AGENT] Agente '{nome}' já existe — pulando")
                continue

            node = cls._criar_agente(nome, skill_base, estrategias, descricao, task_type)
            if node:
                try:
                    graph.add_node(node)
                    created.append(node)
                    logger.info(
                        f"[TASK_AGENT] ✅ Criado: '{nome}' "
                        f"(skill={skill_base}, strategies={estrategias})"
                    )
                except ValueError as e:
                    logger.warning(f"[TASK_AGENT] '{nome}' não adicionado: {e}")

        logger.info(
            f"[TASK_AGENT] {len(created)} novo(s) agente(s) para task '{task[:40]}...'"
        )
        return created

    @classmethod
    def _agente_ja_existe(cls, graph: ExecutionGraph, nome: str,
                          estrategias: List[str]) -> bool:
        """Verifica se já existe agente com estratégias similares no grafo."""
        estrategias_set = set(estrategias)

        for existing_name, existing_node in graph.nodes.items():
            if existing_name.startswith(f"task_{nome}"):
                return True
            if existing_node.strategy in estrategias_set:
                mapped = cls.SKILL_ALIASES.get(
                    cls.SKILL_BASE_MAP.get(nome, ""),
                    cls.SKILL_BASE_MAP.get(nome, "")
                )
                skill_base_real = cls.SKILL_BASE_MAP.get(nome, "")
                if skill_base_real and existing_node.node_type == skill_base_real:
                    return True
        return False

    @classmethod
    def _criar_agente(cls, nome: str, skill_base: str,
                      estrategias: List[str], descricao: str,
                      task_type: str) -> Optional[Node]:
        """Cria um Node agente especialista."""
        # Resolve alias (ex: "coder" → "multi_coder")
        skill_base_real = cls.SKILL_ALIASES.get(skill_base, skill_base)

        if skill_base_real not in cls.SKILL_BASE_MAP.values() and skill_base_real not in cls.DEPENDS_ON_MAP:
            if skill_base_real not in ("multi_coder", "critic", "tester"):
                logger.warning(f"[TASK_AGENT] skill_base desconhecida: {skill_base} (real: {skill_base_real})")
                return None

        depends_on = cls.DEPENDS_ON_MAP.get(skill_base_real, ["planner"])

        strategy = estrategias[0] if estrategias else task_type

        node_name = f"task_{nome}_{task_type}"

        node = Node(
            name=node_name,
            run=None,
            depends_on=list(depends_on),
            strategy=strategy,
            critical=False,
            node_type=skill_base_real,
        )
        node.seed_id = f"task_seed_{nome}"
        node.mutation_id = f"task_{task_type}"
        node.version = "v1"
        node.model_hint = None

        return node


def create_task_agents(task: str, graph: ExecutionGraph) -> List[Node]:
    """Função de conveniência para criar agentes especialistas."""
    return TaskAgentFactory.create_specialist_agents(task, graph)
