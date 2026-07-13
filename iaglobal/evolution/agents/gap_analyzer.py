# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""GapAnalyzer — detecta especialistas faltando para a tarefa atual."""

import logging
from typing import Dict, List, Set

from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.task_analyzer import TaskAnalyzer

logger = logging.getLogger(__name__)


class GapAnalyzer:
    """
    Analisa o ecossistema de agentes existentes e identifica lacunas
    para a tarefa atual.

    Inspirado na sugestão do leiame.md: "Que especialista está faltando?"
    """

    # Mapa: especialidade → palavras-chave que disparam sua necessidade
    SPECIALTY_TRIGGERS: Dict[str, Set[str]] = {
        "security_specialist": {
            "login",
            "autenticacao",
            "authentication",
            "senha",
            "password",
            "api",
            "payment",
            "pagamento",
            "formulario",
            "form",
            "jwt",
            "oauth",
            "token",
            "csrf",
            "xss",
            "sql injection",
        },
        "ux_reviewer": {
            "ux",
            "user experience",
            "acessibilidade",
            "accessibility",
            "mobile",
            "responsivo",
            "responsive",
            "fluxo",
            "flow",
            "usabilidade",
            "usability",
            "clareza",
            "clear",
        },
        "architecture_reviewer": {
            "arquitetura",
            "architecture",
            "escalabilidade",
            "scalability",
            "acoplamento",
            "coupling",
            "design pattern",
            "solid",
            "microservicos",
            "microservices",
            "clean architecture",
        },
        "performance_auditor": {
            "performance",
            "performance",
            "otimizacao",
            "optimization",
            "cache",
            "lazy loading",
            "slow",
            "lento",
            "carregamento",
        },
    }

    # Especialidades que sempre devem existir para certos task_types
    MANDATORY_FOR_TYPE: Dict[str, List[str]] = {
        "web": ["security_specialist", "ux_reviewer", "architecture_reviewer"],
        "api": ["security_specialist", "architecture_reviewer"],
        "auth": ["security_specialist"],
        "blockchain": ["security_specialist", "architecture_reviewer"],
    }

    @classmethod
    def detect_gaps(cls, task: str, graph: ExecutionGraph) -> List[Dict]:
        """
        Detecta especialistas faltando e retorna recomendações de criação.

        Retorna lista de dicts:
            { "nome": ..., "descricao": ..., "skill_base": ..., "estrategias": [...], "prioridade": "alta"|"media" }
        """
        analysis = TaskAnalyzer.analyze(task)
        strategies = analysis["strategies"]
        task_type = analysis["task_type"]
        task_lower = task.lower()

        gaps = []

        # 1. Checa especialidades obrigatórias por tipo de tarefa
        mandatory = cls.MANDATORY_FOR_TYPE.get(task_type, [])
        for specialty in mandatory:
            if not cls._specialty_exists(graph, specialty):
                gaps.append(
                    cls._build_recommendation(
                        specialty, task_type, strategies, prioridade="alta"
                    )
                )

        # 2. Checa especialidades baseadas em palavras-chave
        for specialty, triggers in cls.SPECIALTY_TRIGGERS.items():
            if specialty in mandatory:
                continue  # já foi verificado acima
            if any(trigger in task_lower for trigger in triggers):
                if not cls._specialty_exists(graph, specialty):
                    gaps.append(
                        cls._build_recommendation(
                            specialty, task_type, strategies, prioridade="media"
                        )
                    )

        if gaps:
            logger.info(
                "[GAP] %d lacuna(s) detectada(s) para task type=%s: %s",
                len(gaps),
                task_type,
                [g["nome"] for g in gaps],
            )

        return gaps

    @classmethod
    def _specialty_exists(cls, graph: ExecutionGraph, specialty_name: str) -> bool:
        """Verifica se já existe um agente com essa especialidade."""
        for existing_name in graph.nodes:
            if specialty_name in existing_name:
                return True
            node = graph.nodes[existing_name]
            if node.node_type and specialty_name in node.node_type:
                return True
            if node.seed_id and specialty_name in node.seed_id:
                return True
        return False

    @classmethod
    def _build_recommendation(
        cls,
        specialty: str,
        task_type: str,
        strategies: Set[str],
        prioridade: str = "media",
    ) -> Dict:
        """Constrói recomendação para criação de agente."""
        descriptions = {
            "security_specialist": "Revisa SQL Injection, XSS, CSRF, autenticação, autorização e vazamento de dados",
            "ux_reviewer": "Analisa fluxo do usuário, clareza dos formulários, acessibilidade e experiência mobile",
            "architecture_reviewer": "Avalia acoplamento, separação de responsabilidades, escalabilidade e padrões de projeto",
            "performance_auditor": "Audita performance, otimização de consultas, cache e carregamento",
        }

        skill_map = {
            "security_specialist": "critic",
            "ux_reviewer": "critic",
            "architecture_reviewer": "critic",
            "performance_auditor": "critic",
        }

        estrategias = [f"{specialty}"]
        if strategies:
            estrategias = list(strategies) + estrategias

        return {
            "nome": specialty,
            "descricao": descriptions.get(specialty, f"Especialista em {specialty}"),
            "skill_base": skill_map.get(specialty, "critic"),
            "estrategias": estrategias[:3],
            "prioridade": prioridade,
        }
