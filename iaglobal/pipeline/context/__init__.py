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
from .providers.base import (
    ProjectionProvider,
    SectionSpec,
    register_projection_provider,
)
from .providers.planner import PlannerContextProvider
from .providers.coder import CoderContextProvider
from .providers.tester import TesterContextProvider
from .providers.critic import CriticContextProvider
from .providers.knowledge import KnowledgeContextProvider
from .providers.memory import MemoryContextProvider
from .providers.security import SecurityContextProvider
from .providers.performance import PerformanceContextProvider
from .providers.dependency import DependencyContextProvider
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
