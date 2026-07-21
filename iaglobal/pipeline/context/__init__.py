# iaglobal/pipeline/context/__init__.py

from .protocol import (
    MissionContext,
    RuntimeContext,
    HistoryContext,
    MemoryContext,
    MetricsContext,
    PipelineExecutionContext,
    NodeSection,
    NodeContext,
    TokenBudget,
    TokenEstimator,
    CharTokenEstimator,
    ContextProvider,
    MemorySnapshot,
    SecuritySnapshot,
    PerformanceSnapshot,
)
from .resolver import DependencyResolver
from .contextproviderregistry import (
    ContextProviderRegistry,
    ProviderRegistry,  # Alias de compatibilidade
    context_provider_registry,
    provider_registry,  # Alias de compatibilidade
    register_provider,
)
from .context_providers.base import (
    ProjectionProvider,
    SectionSpec,
    register_projection_provider,
)
from .context_providers.planner import PlannerContextProvider
from .context_providers.coder import CoderContextProvider
from .context_providers.tester import TesterContextProvider
from .context_providers.critic import CriticContextProvider
from .context_providers.knowledge import KnowledgeContextProvider
from .context_providers.memory import MemoryContextProvider
from .context_providers.security import SecurityContextProvider
from .context_providers.performance import PerformanceContextProvider
from .context_providers.dependency import DependencyContextProvider
from .serializers import ContextSerializer, JSONSerializer

__all__ = [
    "MissionContext",
    "RuntimeContext",
    "HistoryContext",
    "MemoryContext",
    "MetricsContext",
    "PipelineExecutionContext",
    "NodeSection",
    "NodeContext",
    "TokenBudget",
    "TokenEstimator",
    "CharTokenEstimator",
    "ContextProvider",
    "MemorySnapshot",
    "SecuritySnapshot",
    "PerformanceSnapshot",
    "DependencyResolver",
    "ContextProviderRegistry",
    "ProviderRegistry",  # Alias de compatibilidade
    "context_provider_registry",
    "provider_registry",  # Alias de compatibilidade
    "register_provider",
    "ProjectionProvider",
    "SectionSpec",
    "register_projection_provider",
    "PlannerContextProvider",
    "CoderContextProvider",
    "TesterContextProvider",
    "CriticContextProvider",
    "KnowledgeContextProvider",
    "MemoryContextProvider",
    "SecurityContextProvider",
    "PerformanceContextProvider",
    "DependencyContextProvider",
    "ContextSerializer",
    "JSONSerializer",
]
