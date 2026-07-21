# iaglobal/pipeline/context/memory_snapshot.py
"""
MemorySnapshot — Agregado imutável de memórias relevantes para execução.

Este módulo define o contrato de dados para memória contextual, sem acoplamento
com infraestrutura (STM/LTM/Obsidian/Cache). A coleta é responsabilidade do
PipelineEngine/MemoryManager; o provider apenas projeta.

Uso:
    snapshot = MemorySnapshot(
        recent_decisions=("decisão1", "decisão2"),
        successful_patterns=("pattern1",),
        similar_projects=("projeto1",),
        semantic_hits=("hit1",),
        cached_artifacts=("artifact1",),
    )
    exec_ctx = ExecutionContext(mission=..., memory_snapshot=snapshot)
"""

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class MemorySnapshot:
    """
    Snapshot imutável de memórias relevantes para um contexto de execução.

    Atributos:
        recent_decisions: Decisões arquiteturais recentes (últimas execuções)
        successful_patterns: Padrões de implementação que funcionaram bem
        similar_projects: Projetos similares já executados
        semantic_hits: Resultados de busca semântica (RAG/vector)
        cached_artifacts: Artefatos em cache (código, testes, docs)
        failure_lessons: Lições aprendidas de falhas anteriores
        obsidian_notes: Notas do vault Obsidian (opcional, pode ser vazio)

    Todos os campos são tuplas (imutáveis) para garantir que o snapshot
    não seja modificado após criação.
    """

    recent_decisions: Tuple[str, ...] = ()
    successful_patterns: Tuple[str, ...] = ()
    similar_projects: Tuple[str, ...] = ()
    semantic_hits: Tuple[str, ...] = ()
    cached_artifacts: Tuple[str, ...] = ()
    failure_lessons: Tuple[str, ...] = ()
    obsidian_notes: Tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Retorna True se nenhum campo tiver conteúdo."""
        return all(
            not field
            for field in (
                self.recent_decisions,
                self.successful_patterns,
                self.similar_projects,
                self.semantic_hits,
                self.cached_artifacts,
                self.failure_lessons,
                self.obsidian_notes,
            )
        )

    @property
    def total_items(self) -> int:
        """Conta total de itens em todos os campos."""
        return sum(
            len(field)
            for field in (
                self.recent_decisions,
                self.successful_patterns,
                self.similar_projects,
                self.semantic_hits,
                self.cached_artifacts,
                self.failure_lessons,
                self.obsidian_notes,
            )
        )
