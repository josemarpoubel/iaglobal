"""GovernanceLayer — Contratos formais e limites de autoridade para agentes.

Cada agente tem um contrato que define:
- Inputs obrigatórios e opcionais
- Outputs esperados
- Autoridade (o que PODE e NÃO PODE fazer)
- Constraints de execução

Regra de ouro: Nenhum agente pode ter autonomia completa de decisão.
Decisão final pertence ao CognitiveProxy.
"""

import re
import json
import time
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum

from iaglobal.utils.logger import logger


class Authority(Enum):
    """Níveis de autoridade que um agente pode ter."""
    READ_ONLY = "read_only"           # Apenas leitura
    EVALUATE = "evaluate"             # Pode avaliar/classificar
    SEARCH = "search"                 # Pode buscar informação externa
    GENERATE = "generate"             # Pode gerar conteúdo
    EXECUTE = "execute"               # Pode executar código
    COORDINATE = "coordinate"         # Pode coordenar outros agentes
    DECIDE = "decide"                 # Pode tomar decisão final


@dataclass
class AgentContract:
    """Contrato formal de um agente.

    Define exatamente o que o agente pode e não pode fazer,
    quais inputs espera, quais outputs produz, e quais
    limites de autoridade possui.
    """
    agent_name: str
    description: str

    # Inputs/Outputs
    required_inputs: List[str] = field(default_factory=list)
    optional_inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)

    # Autoridade
    allowed_authorities: List[Authority] = field(default_factory=list)
    forbidden_actions: List[str] = field(default_factory=list)

    # Constraints
    constraints: List[str] = field(default_factory=list)

    # Timeout máximo para execução (segundos)
    timeout_seconds: Optional[int] = None

    # Se pode modificar estado global
    can_modify_state: bool = False

    # Se pode chamar outros agentes
    can_delegate: bool = False

    def validate_input(self, inputs: Dict) -> List[str]:
        """Valida inputs contra o contrato. Retorna lista de erros."""
        errors = []
        for req in self.required_inputs:
            if req not in inputs or inputs[req] is None:
                errors.append(f"[{self.agent_name}] Input obrigatório ausente: {req}")
        return errors

    def validate_authority(self, action: str) -> bool:
        """Verifica se ação está dentro da autoridade do agente."""
        for forbidden in self.forbidden_actions:
            if re.search(forbidden, action, re.IGNORECASE):
                return False
        return True

    def to_dict(self) -> Dict:
        return {
            "agent": self.agent_name,
            "description": self.description,
            "required_inputs": self.required_inputs,
            "outputs": self.outputs,
            "authorities": [a.value for a in self.allowed_authorities],
            "forbidden": self.forbidden_actions,
            "can_modify_state": self.can_modify_state,
            "can_delegate": self.can_delegate,
        }


# =========================================================================
# CONTRATOS PRÉ-DEFINIDOS
# =========================================================================

CONTRACT_CRITIC = AgentContract(
    agent_name="critic",
    description="Avalia qualidade da saída do modelo. Sensor passivo, sem autonomia de decisão.",
    required_inputs=["task", "output"],
    optional_inputs=["prompt"],
    outputs=["score", "issues", "fix_suggestions"],
    allowed_authorities=[Authority.EVALUATE],
    forbidden_actions=[
        r"executar|execute|run",
        r"buscar.*web|search.*web|duckduckgo",
        r"escolher.*modelo|select.*model|route",
        r"reescrever.*prompt|rewrite.*prompt",
        r"substituir.*resultado|replace.*output",
        r"tomar.*decisão.*final|decide.*final",
    ],
    constraints=["Apenas avalia, não executa", "NÃO modifica output"],
    timeout_seconds=30,
    can_modify_state=False,
    can_delegate=False,
)

CONTRACT_PLANNER = AgentContract(
    agent_name="planner",
    description="Gera plano de execução estruturado. Pode planejar, NÃO pode executar código.",
    required_inputs=["task"],
    optional_inputs=["context", "architecture"],
    outputs=["plan", "tasks", "dependencies"],
    allowed_authorities=[Authority.GENERATE, Authority.EVALUATE],
    forbidden_actions=[
        r"executar.*código|execute.*code|run.*code",
        r"gerar.*código.*final|generate.*final.*code",
        r"escolher.*modelo|select.*model",
        r"buscar.*web|search.*web",
    ],
    constraints=["Apenas planejamento", "Não executa código", "Não escolhe modelos"],
    timeout_seconds=60,
    can_modify_state=False,
    can_delegate=False,
)

CONTRACT_SEARCH = AgentContract(
    agent_name="search",
    description="Busca informação na web. Pode buscar, NÃO pode modificar contexto ou executar código.",
    required_inputs=["query"],
    optional_inputs=["max_results", "source"],
    outputs=["results", "snippets", "urls"],
    allowed_authorities=[Authority.SEARCH],
    forbidden_actions=[
        r"executar.*código|execute.*code",
        r"modificar.*contexto|modify.*context",
        r"tomar.*decisão|decide",
        r"gerar.*código|generate.*code",
        r"avaliar.*qualidade|evaluate.*quality",
    ],
    constraints=["Apenas busca web", "Não modifica memória", "Não executa código"],
    timeout_seconds=30,
    can_modify_state=False,
    can_delegate=False,
)

CONTRACT_MULTI_AGENT = AgentContract(
    agent_name="multi_agent",
    description="Coordenador multi-agente. Coordena execução, NÃO toma decisão final sozinho.",
    required_inputs=["task"],
    optional_inputs=["context", "max_iters"],
    outputs=["result", "artifacts"],
    allowed_authorities=[Authority.COORDINATE, Authority.GENERATE],
    forbidden_actions=[
        r"tomar.*decisão.*final.*sozinho|decide.*final.*alone",
        r"ignorar.*proxy|bypass.*proxy",
        r"substituir.*cognitive.*proxy|replace.*proxy",
    ],
    constraints=["Coordena agentes", "Decisão final pertence ao Proxy", "Reporta ao Proxy"],
    timeout_seconds=120,
    can_modify_state=True,
    can_delegate=True,
)

CONTRACT_CODER = AgentContract(
    agent_name="coder",
    description="Gera código a partir de especificação. Gera código, NÃO executa sem sandbox.",
    required_inputs=["task"],
    optional_inputs=["plan", "context"],
    outputs=["code"],
    allowed_authorities=[Authority.GENERATE],
    forbidden_actions=[
        r"executar.*sem.*sandbox|execute.*without.*sandbox",
        r"escolher.*modelo|select.*model",
        r"buscar.*web|search.*web",
        r"tomar.*decisão.*arquitetural|architectural.*decision",
    ],
    constraints=["Gera código apenas", "Não executa fora do sandbox", "Não decide arquitetura"],
    timeout_seconds=60,
    can_modify_state=False,
    can_delegate=False,
)

CONTRACT_DEBUGGER = AgentContract(
    agent_name="debugger",
    description="Corrige código com base em erros. Corrige, NÃO reescreve completamente.",
    required_inputs=["code", "error"],
    optional_inputs=["task"],
    outputs=["fixed_code"],
    allowed_authorities=[Authority.GENERATE, Authority.EXECUTE],
    forbidden_actions=[
        r"reescrever.*código.*completo|rewrite.*entire.*code",
        r"ignorar.*erro.*original|ignore.*original.*error",
        r"escolher.*modelo|select.*model",
    ],
    constraints=["Corrige código existente", "Preserva estrutura original", "Não escolhe modelos"],
    timeout_seconds=60,
    can_modify_state=False,
    can_delegate=False,
)

CONTRACT_TESTER = AgentContract(
    agent_name="tester",
    description="Gera e executa testes. Testa, NÃO modifica código fonte.",
    required_inputs=["code"],
    optional_inputs=["task"],
    outputs=["tests", "results"],
    allowed_authorities=[Authority.EXECUTE, Authority.EVALUATE],
    forbidden_actions=[
        r"modificar.*código.*fonte|modify.*source.*code",
        r"escolher.*modelo|select.*model",
        r"gerar.*código.*produção|generate.*production.*code",
    ],
    constraints=["Executa apenas em sandbox", "Não modifica código fonte", "Não escolhe modelos"],
    timeout_seconds=60,
    can_modify_state=False,
    can_delegate=False,
)


# =========================================================================
# GOVERNANCE LAYER
# =========================================================================

class GovernanceLayer:
    """Camada de governança que valida contratos e aplica limites de autoridade."""

    def __init__(self, contracts: Optional[Dict[str, AgentContract]] = None):
        self.contracts: Dict[str, AgentContract] = {}
        if contracts:
            for c in contracts:
                self.contracts[c.agent_name] = c

        # Registra contratos padrão
        self._register_defaults()

    def _register_defaults(self):
        defaults = [
            CONTRACT_CRITIC, CONTRACT_PLANNER, CONTRACT_SEARCH,
            CONTRACT_MULTI_AGENT, CONTRACT_CODER, CONTRACT_DEBUGGER, CONTRACT_TESTER,
        ]
        for c in defaults:
            if c.agent_name not in self.contracts:
                self.contracts[c.agent_name] = c

    def register_contract(self, contract: AgentContract):
        """Registra ou atualiza contrato de um agente."""
        self.contracts[contract.agent_name] = contract
        logger.info(f"[GOVERNANCE] Contrato registrado: {contract.agent_name}")

    def get_contract(self, agent_name: str) -> Optional[AgentContract]:
        """Retorna contrato de um agente."""
        return self.contracts.get(agent_name)

    def validate_call(self, agent_name: str, inputs: Dict,
                      action: Optional[str] = None) -> Dict:
        """Valida chamada a um agente contra seu contrato.

        Returns:
            Dict com {"valid": bool, "errors": [str]}
        """
        contract = self.contracts.get(agent_name)
        if not contract:
            logger.warning(f"[GOVERNANCE] Agente '{agent_name}' sem contrato registrado")
            return {"valid": True, "errors": [], "contract_missing": True}

        errors = []

        # Valida inputs obrigatórios
        input_errors = contract.validate_input(inputs)
        errors.extend(input_errors)

        # Valida autoridade
        if action:
            if not contract.validate_authority(action):
                errors.append(
                    f"[{agent_name}] Ação '{action[:60]}' viola contrato: "
                    f"proibido para este agente"
                )

        if errors:
            logger.warning(f"[GOVERNANCE] Violação de contrato: {'; '.join(errors)}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "contract": contract.to_dict(),
        }

    def enforce_timeout(self, agent_name: str) -> Optional[int]:
        """Retorna timeout configurado para o agente."""
        contract = self.contracts.get(agent_name)
        return contract.timeout_seconds if contract else None

    def list_contracts(self) -> List[Dict]:
        """Lista todos os contratos registrados."""
        return [
            c.to_dict() for c in sorted(self.contracts.values(), key=lambda x: x.agent_name)
        ]

    def check_violations(self, agent_name: str, action: str) -> List[str]:
        """Verifica se uma ação específica viola o contrato."""
        contract = self.contracts.get(agent_name)
        if not contract:
            return []

        violations = []
        for forbidden in contract.forbidden_actions:
            if re.search(forbidden, action, re.IGNORECASE):
                violations.append(f"Ação viola '{forbidden}'")
        return violations

    def get_authority_summary(self, agent_name: str) -> Dict:
        """Resumo legível da autoridade de um agente."""
        contract = self.contracts.get(agent_name)
        if not contract:
            return {"agent": agent_name, "status": "sem contrato"}

        return {
            "agent": agent_name,
            "description": contract.description,
            "pode": [a.value for a in contract.allowed_authorities],
            "nao_pode": contract.forbidden_actions[:5],
            "inputs_obrigatorios": contract.required_inputs,
            "outputs": contract.outputs,
            "timeout": contract.timeout_seconds,
        }


# Instância global
governance = GovernanceLayer()
