# iaglobal/pipeline/context/contextproviderregistry.py
"""
Registry singleton de ContextProviders por nome de nó.

Uso:
    @register_provider("planner")
    class PlannerContextProvider:
        ...

    provider = context_provider_registry.get("planner")
    node_ctx = context_provider_registry.resolve("planner", exec_ctx)
"""

from __future__ import annotations

import warnings
from typing import Dict, Optional, Type

from iaglobal.pipeline.context.protocol import (
    PipelineExecutionContext,
    ContextProvider,
    NodeContext,
)


class ContextProviderRegistry:
    """Registry de ContextProviders por nó do pipeline.

    Singleton que gerencia providers de contexto para cada nó do grafo.
    Suporta lazy import: ao chamar get("coder"), tenta importar
    iaglobal.pipeline.context.context_providers.coder automaticamente.
    """

    _instance: Optional[ContextProviderRegistry] = None
    _providers: Dict[str, ContextProvider] = {}
    _PROVIDER_MODULE = "iaglobal.pipeline.context.context_providers.{name}"

    def __new__(cls) -> ContextProviderRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, node_name: str, provider: ContextProvider) -> None:
        self._providers[node_name] = provider

    def get(self, node_name: str) -> Optional[ContextProvider]:
        if node_name not in self._providers:
            self._try_lazy_import(node_name)
        return self._providers.get(node_name)

    def resolve(
        self, node_name: str, exec_ctx: PipelineExecutionContext
    ) -> Optional[NodeContext]:
        provider = self.get(node_name)
        if provider is None:
            return None
        return provider.build(exec_ctx, node_name=node_name)

    @staticmethod
    def _try_lazy_import(node_name: str) -> None:
        module_path = ContextProviderRegistry._PROVIDER_MODULE.format(
            name=node_name.replace("-", "_")
        )
        try:
            import importlib

            importlib.import_module(module_path)
        except ImportError:
            pass


class ProviderRegistry(ContextProviderRegistry):
    """
    Alias de compatibilidade temporária.

    DEPRECATED: Use ContextProviderRegistry diretamente.
    Será removido quando não houver consumidores ativos.

    Attributes:
        __deprecated__: True (para ferramentas de análise estática)
        __replacement__: "ContextProviderRegistry"
    """

    __deprecated__ = True
    __replacement__ = "ContextProviderRegistry"

    def __new__(cls, *args, **kwargs):
        warnings.warn(
            "ProviderRegistry is deprecated; use ContextProviderRegistry",
            DeprecationWarning,
            stacklevel=2,
        )
        return super().__new__(cls)


context_provider_registry = ContextProviderRegistry()

provider_registry = context_provider_registry
"""
Alias de compatibilidade temporária.

DEPRECATED: Use context_provider_registry diretamente.
"""

__all__ = [
    "ContextProviderRegistry",
    "context_provider_registry",
    # Deprecated
    "ProviderRegistry",
    "provider_registry",
    "register_provider",
]


def register_provider(node_name: str):
    """Decorador que registra automaticamente um ContextProvider no registry."""

    def wrapper(cls: Type) -> Type:
        instance = cls()
        provider_registry.register(node_name, instance)
        return cls

    return wrapper
