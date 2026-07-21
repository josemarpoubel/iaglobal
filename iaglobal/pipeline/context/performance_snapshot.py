# iaglobal/pipeline/context/performance_snapshot.py
"""
PerformanceSnapshot — Agregado imutável de métricas e orçamentos de performance.

Este módulo define o contrato de dados para performance, sem acoplamento
com sistemas de profiling, monitoramento ou BanditPolicy.
A coleta é responsabilidade do PipelineEngine; o provider apenas projeta.

Uso:
    snapshot = PerformanceSnapshot(
        latency_target_ms=100,
        memory_budget_mb=512,
        cpu_budget_percent=25,
        token_budget=4000,
        known_bottlenecks=("IO bound",),
        hot_paths=("geracao_codigo",),
    )
    exec_ctx = ExecutionContext(performance_snapshot=snapshot)
"""

from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass(frozen=True)
class PerformanceSnapshot:
    """
    Snapshot imutável de contexto de performance para execução.

    Atributos:
        latency_target_ms: Target de latência em milissegundos
        memory_budget_mb: Orçamento de memória em MB
        cpu_budget_percent: Orçamento de CPU em porcentagem (0-100)
        token_budget: Orçamento de tokens para LLM
        cost_budget_usd: Orçamento de custo em USD (opcional)
        known_bottlenecks: Gargalos conhecidos (IO bound, CPU bound, etc.)
        hot_paths: Caminhos críticos que exigem otimização
        optimization_priorities: Prioridades de otimização (latência, custo, etc.)

    Campos numéricos são imutáveis e campos de lista são tuplas.
    """

    latency_target_ms: float = 1000.0
    memory_budget_mb: float = 512.0
    cpu_budget_percent: float = 25.0
    token_budget: int = 4000
    cost_budget_usd: Optional[float] = None
    known_bottlenecks: Tuple[str, ...] = ()
    hot_paths: Tuple[str, ...] = ()
    optimization_priorities: Tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Retorna True se todos os campos estiverem nos defaults."""
        return (
            self.latency_target_ms == 1000.0
            and self.memory_budget_mb == 512.0
            and self.cpu_budget_percent == 25.0
            and self.token_budget == 4000
            and self.cost_budget_usd is None
            and not self.known_bottlenecks
            and not self.hot_paths
            and not self.optimization_priorities
        )

    @property
    def total_constraints(self) -> int:
        """Conta total de restrições de performance ativas."""
        count = 4  # latency, memory, cpu, token (sempre presentes)
        if self.cost_budget_usd is not None:
            count += 1
        count += len(self.known_bottlenecks)
        count += len(self.hot_paths)
        count += len(self.optimization_priorities)
        return count
