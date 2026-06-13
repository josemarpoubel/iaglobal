"""
Validador de Linhagem Gênesis para o sistema auto-evolutivo.
Usa SHA3-512 para gerar IDs e validar que agentes pertecem a mesma família.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Optional


# ==============================================================================
# GÊNESIS (fonte de verdade da família)
# ==============================================================================

GENESIS_SEED = "Mavis-josemarpoubel-2026-06-13-18:30:00-autoevolutivo"
GENESIS_ID = hashlib.sha3_512(GENESIS_SEED.encode("utf-8")).hexdigest()
GENESIS_POLICIES = ["LGPD-compliant", "no-external-calls-without-audit",
                    "budget-guarded", "lineage-validated"]
GENESIS_LICENSE = "MIT"

# arquivo txt de auditoria (append-only)
LINEAGE_LOG = Path(__file__).parent / "lineage_audit.txt"


# ==============================================================================
# GERAÇÃO DE IDENTIDADE
# ==============================================================================

def make_agent_id(role: str, version: str = "v1", generation: int = 1) -> str:
    """Gera ID único de agente a partir do gênesis + papel + versão."""
    raw = f"{GENESIS_ID}:{role}:{version}:gen{generation}"
    return hashlib.sha3_512(raw.encode("utf-8")).hexdigest()


def make_lineage_hash(genesis_id: str, parent_id: str, agent_id: str,
                      timestamp: str, payload: str) -> str:
    """Gera hash de linhagem completo para auditoria."""
    raw = f"{genesis_id}|{parent_id}|{agent_id}|{timestamp}|{payload}"
    return hashlib.sha3_512(raw.encode("utf-8")).hexdigest()


def make_generation_id(parent_agent_id: str, generation: int) -> str:
    """Gera ID de nova geração a partir de um agente pai."""
    raw = f"{GENESIS_ID}:{parent_agent_id}:gen{generation}"
    return hashlib.sha3_512(raw.encode("utf-8")).hexdigest()


# ==============================================================================
# VALIDAÇÃO
# ==============================================================================

class LineageViolationError(Exception):
    """Erro lançado quando um agente tenta chamar outro de familia diferente."""
    pass


class Agent:
    """Representa um agente com identidade gênesis-validada."""

    def __init__(self, role: str, version: str = "v1", generation: int = 1,
                 parent_id: Optional[str] = None):
        self.role = role
        self.version = version
        self.generation = generation
        self.genesis_id = GENESIS_ID
        self.agent_id = make_agent_id(role, version, generation)
        self.parent_id = parent_id or GENESIS_ID
        self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def call(self, other: "Agent", payload: str = "") -> str:
        """Chama outro agente. Valida linhagem antes."""
        self._validate_lineage(other)
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        lineage = make_lineage_hash(
            self.genesis_id, self.agent_id, other.agent_id, timestamp, payload
        )
        self._audit(f"CALL: {self.role} -> {other.role} | lineage={lineage[:16]}")
        return lineage

    def _validate_lineage(self, other: "Agent") -> None:
        """Bloqueia chamadas cross-family."""
        if self.genesis_id != other.genesis_id:
            raise LineageViolationError(
                f"Cross-family call blocked: {self.role}({self.genesis_id[:8]}) "
                f"-> {other.role}({other.genesis_id[:8]})"
            )

    def _audit(self, event: str) -> None:
        """Registra evento no log append-only."""
        with LINEAGE_LOG.open("a", encoding="utf-8") as f:
            f.write(f"[{self.created_at}] {self.agent_id[:16]} {event}\n")

    def to_dict(self) -> dict:
        return {
            "genesis_id": self.genesis_id,
            "agent_id": self.agent_id,
            "role": self.role,
            "version": self.version,
            "generation": self.generation,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
        }


# ==============================================================================
# REGISTRO DE TODOS OS AGENTES DA PIPELINE
# ==============================================================================

def build_agent_registry() -> dict:
    """Cria registro de todos os agentes definidos na pipeline."""
    roles = [
        ("genesis", "v1"),
        ("prompt_intake", "v1"),
        ("enhancement", "v1"),
        ("budget_guard", "v1"),
        ("orchestrator", "v1"),
        ("pm", "v1"),
        ("requirements", "v1"),
        ("domain_analysis", "v1"),
        ("research", "v1"),
        ("business_rules", "v1"),
        ("compliance_check", "v1"),
        ("technology_selection", "v1"),
        ("architect", "v1"),
        ("system_design", "v1"),
        ("api_design", "v1"),
        ("data_design", "v1"),
        ("performance_design", "v1"),
        ("design_reconciler", "v1"),
        ("architecture_validator", "v1"),
        ("execution_plan", "v1"),
        ("frontend_builder", "v1"),
        ("backend_builder", "v1"),
        ("database_builder", "v1"),
        ("integration", "v1"),
        ("test_generator", "v1"),
        ("security_review", "v1"),
        ("semantic_validator", "v1"),
        ("debugger_healing", "v1"),
        ("fix_validator", "v1"),
        ("documentation", "v1"),
        ("deploy", "v1"),
        ("telemetry", "v1"),
        ("feedback_loop", "v1"),
    ]
    registry = {}
    for role, version in roles:
        agent = Agent(role=role, version=version)
        registry[role] = agent.to_dict()
    return registry


# ==============================================================================
# DEMO / SELF-TEST
# ==============================================================================

def demo():
    """Demonstra o uso do validador."""
    print(f"GÊNESIS: {GENESIS_ID}\n")

    # 1. Cria agentes
    orchestrator = Agent(role="orchestrator", version="v1")
    pm = Agent(role="pm", version="v1")
    architect = Agent(role="architect", version="v1")

    print(f"ORCHESTRATOR_ID: {orchestrator.agent_id[:32]}...")
    print(f"PM_ID:           {pm.agent_id[:32]}...")
    print(f"ARCHITECT_ID:    {architect.agent_id[:32]}...\n")

    # 2. Chamada válida (mesma família)
    print("→ Chamada válida (mesmo gênesis):")
    lineage = orchestrator.call(pm, payload="enhanced_prompt.json")
    print(f"  Lineage hash: {lineage[:32]}...\n")

    # 3. Tentativa de cross-family (deve falhar)
    print("→ Tentativa de cross-family (deve BLOQUEAR):")
    impostor = Agent.__new__(Agent)  # agente "paralelo" sem gênesis
    impostor.genesis_id = "genesis_ESTRANHO_123"
    impostor.role = "impostor"
    impostor.agent_id = "impostor_id"
    impostor._validate_lineage = lambda other: None  # bypass local

    # cria um agente "forasteiro" de propósito
    class ForeignAgent:
        def __init__(self):
            self.genesis_id = "genesis_ESTRANHO_999"
            self.role = "spy"
            self.agent_id = "spy_id"

    try:
        orchestrator.call(ForeignAgent(), payload="roubo de dados")
    except LineageViolationError as e:
        print(f"  ✓ BLOQUEADO: {e}\n")

    # 4. Geração de novo agente (evolução)
    print("→ Evolução (gera nova geração a partir do architect):")
    architect_v2 = Agent(role="architect", version="v2", generation=2,
                         parent_id=architect.agent_id)
    print(f"  PARENT: {architect_v2.parent_id[:32]}...")
    print(f"  CHILD:  {architect_v2.agent_id[:32]}...\n")

    # 5. Registro completo
    print("→ Salvando registro completo da pipeline...")
    registry = build_agent_registry()
    registry_path = Path(__file__).parent / "agent_registry.json"
    with registry_path.open("w", encoding="utf-8") as f:
        json.dump({
            "genesis": {
                "id": GENESIS_ID,
                "seed": GENESIS_SEED,
                "policies": GENESIS_POLICIES,
                "license": GENESIS_LICENSE,
            },
            "agents": registry,
        }, f, indent=2, ensure_ascii=False)
    print(f"  Salvo em: {registry_path}")
    print(f"  Total de agentes registrados: {len(registry)}")


if __name__ == "__main__":
    demo()
