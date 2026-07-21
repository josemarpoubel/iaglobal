# iaglobal/pipeline/context/providers/memory.py
"""
MemoryContextProvider — provider especializado para memória contextual.

Projeta do MemorySnapshot:
  - Recent Decisions (decisões arquiteturais recentes)
  - Successful Patterns (padrões que funcionaram)
  - Similar Projects (projetos similares)
  - Semantic Hits (resultados de busca semântica)
  - Cached Artifacts (artefatos em cache)
  - Failure Lessons (lições de falhas)
  - Obsidian Notes (notas do vault, opcional)

Este provider NÃO acessa diretamente STM/LTM/Obsidian.
Ele apenas projeta o MemorySnapshot já coletado pelo PipelineEngine.

Uso:
    # PipelineEngine coleta memórias → MemorySnapshot
    snapshot = MemorySnapshot(
        recent_decisions=("decisão1",),
        successful_patterns=("pattern1",),
        ...
    )
    exec_ctx = PipelineExecutionContext(memory_snapshot=snapshot)

    # Provider apenas projeta
    provider = provider_registry.get("memory")
    node_ctx = provider.build(exec_ctx, node_name="coder")
"""

from .base import ProjectionProvider, SectionSpec
from ..protocol import PipelineExecutionContext
from ..contextproviderregistry import provider_registry


MemoryContextProvider = ProjectionProvider(
    requires=(
        PipelineExecutionContext,
    ),  # Requer PipelineExecutionContext completo para acessar memory_snapshot
    sections=(
        SectionSpec(
            "recent_decisions",
            "Decisões Recentes",
            100,
            "memory_snapshot.recent_decisions",
        ),
        SectionSpec(
            "successful_patterns",
            "Padrões Bem-Sucedidos",
            90,
            "memory_snapshot.successful_patterns",
        ),
        SectionSpec(
            "similar_projects",
            "Projetos Similares",
            80,
            "memory_snapshot.similar_projects",
        ),
        SectionSpec(
            "semantic_hits", "Busca Semântica", 70, "memory_snapshot.semantic_hits"
        ),
        SectionSpec(
            "cached_artifacts",
            "Artefatos em Cache",
            60,
            "memory_snapshot.cached_artifacts",
        ),
        SectionSpec(
            "failure_lessons", "Lições de Falhas", 50, "memory_snapshot.failure_lessons"
        ),
        SectionSpec("obsidian_notes", "Obsidian", 40, "memory_snapshot.obsidian_notes"),
    ),
)

provider_registry.register("memory", MemoryContextProvider)
