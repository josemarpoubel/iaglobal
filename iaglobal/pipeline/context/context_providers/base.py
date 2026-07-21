# iaglobal/pipeline/context/providers/base.py
"""
ProjectionProvider — provider declarativo baseado em projeções.

Em vez de escrever código Python para cada provider, define-se
quais seções projetar do PipelineExecutionContext via SectionSpec.

Exemplo:
    PlannerProvider = ProjectionProvider(
        requires=(MissionContext,),
        sections=[
            SectionSpec("objective", "Objetivo", 100, "mission.objective"),
            SectionSpec("domain", "Domínio", 90, "mission.domain"),
            SectionSpec("entities", "Entidades", 70, "mission.entities"),
        ],
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from ..protocol import (
    ContextProvider,
    PipelineExecutionContext,
    MissionContext,
    NodeContext,
    NodeSection,
    TokenBudget,
)
from ..contextproviderregistry import provider_registry


@dataclass(frozen=True)
class SectionSpec:
    """Especificação declarativa de uma seção de contexto."""

    section_id: str
    title: str
    priority: int
    source: str  ##### dot-path no PipelineExecutionContext, ex: "mission.entities"
    budget_key: str = ""  ##### qual chave do TokenBudget usar (default = section_id)


def _resolve_dot_path(obj: Any, path: str) -> Any:
    """Resolve 'mission.entities' → ctx.mission.entities."""
    parts = path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return None
    return current


class ProjectionProvider:
    """
    Provider declarativo: projeta campos do PipelineExecutionContext em NodeSections.

    Uso:
        PlannerProvider = ProjectionProvider(
            requires=(MissionContext,),
            sections=[
                SectionSpec("objective", "Objetivo", 100, "mission.objective"),
            ],
        )
    """

    def __init__(
        self,
        requires: Tuple[Type, ...] = (),
        sections: Tuple[SectionSpec, ...] = (),
    ):
        self._requires = requires
        self._sections = sections

    @property
    def requires(self) -> Tuple[Type, ...]:
        return self._requires

    @property
    def sections(self) -> Tuple[SectionSpec, ...]:
        return self._sections

    def build(
        self,
        ctx: PipelineExecutionContext,
        node_name: str = "",
        budget: Optional[TokenBudget] = None,
    ) -> NodeContext:
        b = budget or TokenBudget()
        result: List[NodeSection] = []

        for spec in self._sections:
            raw = _resolve_dot_path(ctx, spec.source)
            if raw is None:
                continue

            # Normaliza para tupla
            if isinstance(raw, (list, tuple)):
                content = tuple(raw)
            else:
                content = (raw,)

            if not content:
                continue

            # Trunca pelo orçamento da seção
            budget_key = spec.budget_key or spec.section_id
            max_tokens = b.for_section(budget_key)
            budget_chars = max_tokens * 4  ##### chars ≈ tokens × 4

            truncated: List[Any] = []
            char_count = 0
            for item in content:
                item_str = str(item)
                if char_count + len(item_str) > budget_chars:
                    break
                truncated.append(item)
                char_count += len(item_str) + 2

            result.append(
                NodeSection(
                    id=spec.section_id,
                    title=spec.title,
                    priority=spec.priority,
                    content=tuple(truncated),
                )
            )

        return NodeContext(
            node_name=node_name,
            sections=tuple(result),
            budget=b,
        )


def register_projection_provider(
    node_name: str,
    requires: Tuple[Type, ...] = (MissionContext,),
    sections: Tuple[Tuple[str, str, int, str], ...] = (),
):
    """
    Helper para registrar ProjectionProvider com mínimo boilerplate.

    Uso:
        DependencyContextProvider = register_projection_provider(
            "dependency",
            sections=(
                ("objective", "Objetivo", 100, "mission.objective"),
                ("domain", "Domínio", 90, "mission.domain"),
            ),
        )

    Args:
        node_name: Nome do nó no grafo (ex: "coder", "dependency")
        requires: Tupla de tipos de contexto requeridos (default: MissionContext)
        sections: Tupla de (section_id, title, priority, source_path)

    Returns:
        Instância de ProjectionProvider já registrada no ProviderRegistry
    """
    requires = requires or (MissionContext,)
    section_specs = tuple(
        SectionSpec(section_id=sec[0], title=sec[1], priority=sec[2], source=sec[3])
        for sec in sections
    )

    provider = ProjectionProvider(requires=requires, sections=section_specs)
    provider_registry.register(node_name, provider)
    return provider


class EnrichmentProvider:
    """
    Base para providers que enriquecem o contexto com dados externos.

    Diferente do ProjectionProvider (apenas projeta dados existentes),
    o EnrichmentProvider consulta fontes externas (STM, LTM, Obsidian,
    Vector Store, Cache, RAG) e produz novo contexto.

    Uso futuro:
        class MemoryEnrichmentProvider(EnrichmentProvider):
            def enrich(self, ctx: PipelineExecutionContext) -> MemorySnapshot:
                # Consulta STM, LTM, Obsidian, etc.
                return MemorySnapshot(...)

    O método `build()` chama `enrich()` e depois projeta o resultado.
    """

    requires: Tuple[Type, ...] = (PipelineExecutionContext,)

    def enrich(self, ctx: PipelineExecutionContext) -> Any:
        """
        Consulta fontes externas e retorna snapshot enriquecido.

        Deve ser implementado por subclasses.
        """
        raise NotImplementedError

    def build(
        self,
        ctx: PipelineExecutionContext,
        node_name: str = "",
        budget: Optional[TokenBudget] = None,
    ) -> NodeContext:
        """
        Template method: enrich → project → NodeContext.

        Subclasses podem sobrescrever para customizar projeção.
        """
        enriched = self.enrich(ctx)
        # Subclasses implementam projeção do enriched para NodeContext
        raise NotImplementedError
