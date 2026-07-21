# iaglobal/pipeline/context/resolver.py
"""
DependencyResolver — resolve as dependências de um provider
a partir do ExecutionContext.

Mapeia tipos (MissionContext, RuntimeContext, ...) para os
atributos correspondentes no ExecutionContext via CONTEXT_REGISTRY.
"""

from __future__ import annotations

from typing import Dict, Any

from .protocol import (
    PipelineExecutionContext,
    MissionContext,
    RuntimeContext,
    HistoryContext,
    MemoryContext,
    MetricsContext,
    _CONTEXT_REGISTRY,
)


# Mapa reverso: tipo → caminho (já definido em _CONTEXT_REGISTRY em protocol.py)
# Reexportamos aqui para acesso centralizado
CONTEXT_REGISTRY = _CONTEXT_REGISTRY


class DependencyResolver:
    """
    Resolvedor de dependências para ContextProviders.

    Uso:
        resolver = DependencyResolver()
        deps = resolver.resolve(provider, exec_ctx)
        # deps = {MissionContext: <mission>, RuntimeContext: <runtime>, ...}
    """

    def resolve(
        self,
        provider,
        exec_ctx: PipelineExecutionContext,
    ) -> Dict[type, Any]:
        deps: Dict[type, Any] = {}
        for req_type in getattr(provider, "requires", ()):
            attr_name = CONTEXT_REGISTRY.get(req_type)
            if attr_name and hasattr(exec_ctx, attr_name):
                deps[req_type] = getattr(exec_ctx, attr_name)
        return deps
