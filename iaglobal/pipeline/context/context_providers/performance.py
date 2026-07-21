# iaglobal/pipeline/context/providers/performance.py
"""
PerformanceContextProvider — provider especializado para performance e eficiência.

Projeta do PerformanceSnapshot:
  - Latency Target (target de latência)
  - Memory Budget (orçamento de memória)
  - CPU Budget (orçamento de CPU)
  - Token Budget (orçamento de tokens para LLM)
  - Cost Budget (orçamento de custo)
  - Known Bottlenecks (gargalos conhecidos)
  - Hot Paths (caminhos críticos)
  - Optimization Priorities (prioridades de otimização)

Este provider NÃO acessa diretamente sistemas de profiling ou monitoramento.
Ele apenas projeta o PerformanceSnapshot já coletado pelo PipelineEngine.

Uso:
    # PipelineEngine coleta métricas → PerformanceSnapshot
    snapshot = PerformanceSnapshot(
        latency_target_ms=100,
        memory_budget_mb=512,
        known_bottlenecks=("IO bound",),
        ...
    )
    exec_ctx = PipelineExecutionContext(performance_snapshot=snapshot)

    # Provider apenas projeta
    provider = provider_registry.get("performance")
    node_ctx = provider.build(exec_ctx, node_name="performance")
"""

from .base import ProjectionProvider, SectionSpec
from ..protocol import PipelineExecutionContext
from ..contextproviderregistry import provider_registry


PerformanceContextProvider = ProjectionProvider(
    requires=(PipelineExecutionContext,),
    sections=(
        SectionSpec(
            "latency_target",
            "Latency Target",
            100,
            "performance_snapshot.latency_target_ms",
        ),
        SectionSpec(
            "memory_budget",
            "Memory Budget",
            95,
            "performance_snapshot.memory_budget_mb",
        ),
        SectionSpec(
            "cpu_budget", "CPU Budget", 90, "performance_snapshot.cpu_budget_percent"
        ),
        SectionSpec(
            "token_budget", "Token Budget", 85, "performance_snapshot.token_budget"
        ),
        SectionSpec(
            "cost_budget", "Cost Budget", 80, "performance_snapshot.cost_budget_usd"
        ),
        SectionSpec(
            "known_bottlenecks",
            "Gargalos Conhecidos",
            75,
            "performance_snapshot.known_bottlenecks",
        ),
        SectionSpec("hot_paths", "Hot Paths", 70, "performance_snapshot.hot_paths"),
        SectionSpec(
            "optimization_priorities",
            "Prioridades de Otimização",
            65,
            "performance_snapshot.optimization_priorities",
        ),
    ),
)

provider_registry.register("performance", PerformanceContextProvider)
