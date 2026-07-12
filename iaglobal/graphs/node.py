# iaglobal/graphs/node.py

import time
import math
import secrets
import hashlib
from dataclasses import dataclass, field
from typing import Callable, Optional, List




@dataclass
class LineageEntry:
    """A single lineage event in a node's evolutionary history."""
    generation: int
    event_type: str  # "seed", "mutation", "crossover"
    parent_name: str = ""
    parent_fitness: float = 0.0
    strategy: str = ""
    fitness_delta: float = 0.0
    timestamp: float = 0.0
    lineage_id: str = ""
    lineage_marker: str = ""


def compute_node_id(
    node_type: str,
    seed_id: str = "",
    mutation_id: str = "",
    version: str = "v1",
    name: str = "",
) -> str:
    """
    Gera ID determinístico SHA3-512 para o node.
    Inclui o nome do nó para garantir unicidade mesmo quando
    node_type + seed + mutation são idênticos (ex: core vs EVO seed).
    """
    raw = f"{node_type}::{seed_id}::{mutation_id}::{version}::{name}"
    return hashlib.sha3_512(raw.encode()).hexdigest()


@dataclass
class Node:
    """
    🧠 Node Cognitivo

    Representa um ponto de execução no DAG, com métricas de evolução, 
    estratégia e suporte a modelo local/online.

    Agora com identidade global determinística (node_id) que previne
    duplicação lógica no grafo.
    """

    # Identidade
    name: str
    run: Callable
    depends_on: list[str] = field(default_factory=list)

    # 🆔 Node Identity (determinístico — previne duplicação)
    node_type: str = "general"
    seed_id: str = ""
    mutation_id: str = ""
    version: str = "v1"

    # 🧬 EVOLUTION GENES
    strategy: str = "general"
    model_hint: Optional[str] = None
    model_type: str = "local"  # "local" ou "online"
    mutation_rate: float = 0.1  # default, pode ser ajustado por estratégia

    # 🛡️ Sanity Barrier
    critical: bool = False  # Se True, falha deste nó aborta nós dependentes

    # 📊 STATS
    success_count: int = 0
    fail_count: int = 0
    executions: int = 0
    total_latency: float = 0.0
    last_error: Optional[str] = None
    last_execution_ts: Optional[float] = None

    # Exploration / Decay
    exploration_factor: float = 0.1
    decay_factor: float = 0.99

    # Histórico detalhado de execuções (para evolução e análise)
    metrics: list[dict] = field(default_factory=list)

    # 🧬 LINEAGE (evolutionary history)
    lineage: list["LineageEntry"] = field(default_factory=list)

    # Metadados da skill de origem (compat builder)
    metadata: dict = field(default_factory=dict)

    # Lock de execução (anti race condition)
    _lock: bool = False

    def acquire(self) -> bool:
        """Try to acquire execution lock. Returns True if successful."""
        if self._lock:
            return False
        self._lock = True
        return True

    def release(self) -> None:
        """Release execution lock."""
        self._lock = False

    # -----------------------------
    # RECORD EXECUTION
    # -----------------------------
    def record(self, success: bool, latency: float, error: Optional[str] = None):
        self.executions += 1
        self.total_latency += latency
        self.last_execution_ts = time.time()
        self.last_error = error if not success else None

        if success:
            self.success_count += 1
        else:
            self.fail_count += 1

        # Adiciona ao histórico detalhado
        self.metrics.append({
            "success": success,
            "latency": latency,
            "error": error,
            "timestamp": self.last_execution_ts
        })

        # Decay de métricas antigas para evitar overfitting
        if len(self.metrics) > 100:
            self.metrics = self.metrics[-50:]

    # -----------------------------
    # DERIVED METRICS (SAFE)
    # -----------------------------
    # -----------------------------
    # NODE IDENTITY (determinístico)
    # -----------------------------
    @property
    def node_id(self) -> str:
        # 🧬 VALIDAÇÃO PELO TRIBUNAL DE GÊNESIS ANTES DO NASCIMENTO
        from iaglobal.genesis.verifygenesis import VerifyGenesis
        tribunal = VerifyGenesis()
        if not tribunal.verify_frozen_authority():
            raise RuntimeError("🚨 [TRIBUNAL] Blueprint violado. Nó não autorizado a nascer.")
        
        # Usa node_type se explícito, senão fallback para name (único)
        effective_type = self.node_type if self.node_type != "general" else self.name
        # seed_id vazio = usa name (único por grafo)
        effective_seed = self.seed_id if self.seed_id else self.name
        return compute_node_id(
            node_type=effective_type,
            seed_id=effective_seed,
            mutation_id=self.mutation_id,
            version=self.version,
            name=self.name,
        )

    @property
    def current_lineage_marker(self) -> str:
        """Retorna o marcador hereditário de linhagem."""
        return self.lineage[-1].lineage_marker if self.lineage else ""

    @property
    def success_rate(self) -> float:
        return self.success_count / self.executions if self.executions > 0 else 0.5

    @property
    def avg_latency(self) -> float:
        return self.total_latency / self.executions if self.executions > 0 else 1.0

    # -----------------------------
    # FITNESS
    # -----------------------------
    def fitness(self) -> float:
        latency_score = 1 / (1 + math.log(self.avg_latency + 1.1))
        stability = 1 / (1 + self.fail_count)
        exploration = self.exploration_factor * (secrets.randbelow(100) / 100 - 0.5)

        return (
            self.success_rate * 0.65 +
            latency_score * 0.25 +
            stability * 0.10 +
            exploration
        )


