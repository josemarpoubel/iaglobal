# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# /iaglobal/agents/orchestrator_agent.py

"""OrchestratorAgent — Roteia a pipeline com base em intents e requisitos extraídos."""

from typing import List, Dict, Any, TypedDict, Optional, Set
from iaglobal.utils.logger import logger
from iaglobal.agents.agent_base import AgentBase


# --- 1. Contrato de Dados Rígido ---
class RoutingResult(TypedDict):
    next_phase: str
    active_nodes: List[str]
    domains_detected: List[str]


# --- 2. Configuração Modular (Fim da repetição) ---
_BASE_NODES = ["pm", "requirements", "domain_analysis"]

_DOMAIN_SPECIFIC_NODES = {
    "web": ["architect", "system_design", "api_design", "frontend_builder"],
    "api": ["architect", "system_design", "api_design"],
    "ia": ["architect", "system_design", "api_design", "database_design"],
    "dados": ["architect", "system_design", "database_design"],
    "banco": ["database_design"],
    "automacao": ["architect"],
    "mobile": ["architect", "api_design"],
    "seguranca": ["security_design", "threat_modeling"],
    "cli": [],
    "financeiro": ["architect", "database_design"],
    "devops": [],
    "falha": ["failure_analysis"],
    "teste": [
        "test_design",
        "qa_validation",
    ],  # Adicionado para cobrir o intent_classifier
}

# --- 3. Mapeamento de Requisitos Não-Funcionais (O "Pulo do Gato") ---
# Permite que o orquestrador adicione nós de segurança/performance mesmo que o domínio seja "web"
_NFR_NODE_MAP = {
    "seguranca": "security_design",
    "performance": "performance_testing",
    "escalabilidade": "system_design",
}

# --- 4. Ordem de Precedência dos Nós (Garante execução correta no DAG) ---
_NODE_PRIORITY = [
    "pm",
    "requirements",
    "domain_analysis",
    "architect",
    "system_design",
    "api_design",
    "database_design",
    "frontend_builder",
    "security_design",
    "threat_modeling",
    "failure_analysis",
    "test_design",
    "qa_validation",
    "performance_testing",
]


class OrchestratorAgent(AgentBase):
    def __init__(self):
        super().__init__(agent_name="orchestrator_agent")

    def _call_llm(self, *args, **kwargs):
        raise NotImplementedError(
            "OrchestratorAgent nao executa LLM. "
            "Seu papel e roteamento deterministico puro via route(). "
            "Chamar _call_llm viola PSC e a Le da Obediencia."
        )

    def route(
        self,
        enhancement: Optional[Dict[str, Any]] = None,
        requirements: Optional[Dict[str, Any]] = None,
    ) -> RoutingResult:
        # 1. Validação de entrada robusta (Imune a tipos errados vindos de outros agentes)
        if not enhancement or not isinstance(enhancement, dict):
            enhancement = {}
        if not requirements or not isinstance(requirements, dict):
            requirements = {}

        # Extração segura de fases
        scope = enhancement.get("scope") or {}
        if not isinstance(scope, dict):
            scope = {}

        phases = scope.get("phases", ["definition"])
        next_phase = phases[0] if isinstance(phases, list) and phases else "definition"

        intents = enhancement.get("intents_detected", [])
        if not isinstance(intents, list):
            intents = []

        # 2. Roteamento Multi-Intent (Agrega nós de TODOS os intents, não só do primeiro)
        active_nodes: Set[str] = set(_BASE_NODES)
        domains_detected = []

        for intent in intents:
            if intent in _DOMAIN_SPECIFIC_NODES:
                domains_detected.append(intent)
                active_nodes.update(_DOMAIN_SPECIFIC_NODES[intent])
            elif intent != "unknown":
                logger.debug(
                    "Intent '%s' não possui mapeamento específico de nós.", intent
                )

        # 3. Roteamento Baseado em Requisitos (Enriquecimento Dinâmico)
        # Se o PMAgent detectou "Garantir seguranca", adicionamos os nós de segurança!
        non_functional_reqs = requirements.get("non_functional", [])
        if isinstance(non_functional_reqs, list):
            for req in non_functional_reqs:
                req_lower = req.lower()
                for nfr_key, node_name in _NFR_NODE_MAP.items():
                    if nfr_key in req_lower:
                        active_nodes.add(node_name)
                        logger.info(
                            "[ORCHESTRATOR] Nó '%s' injetado via requisito não-funcional: %s",
                            node_name,
                            req,
                        )

        # 4. Ordenação Determinística (Crucial para Pipelines/DAGs)
        # Garante que "pm" rode antes de "architect", que rode antes de "api_design", etc.
        final_nodes = [n for n in _NODE_PRIORITY if n in active_nodes]

        # Adiciona eventuali nós não listados na prioridade no final (fallback seguro)
        for n in sorted(active_nodes):
            if n not in final_nodes:
                final_nodes.append(n)

        logger.info(
            "[ORCHESTRATOR] next_phase=%s | domains=%s | active_nodes=%d (%s)",
            next_phase,
            domains_detected or ["unknown"],
            len(final_nodes),
            final_nodes,
        )

        return {
            "next_phase": next_phase,
            "active_nodes": final_nodes,
            "domains_detected": domains_detected,
        }
