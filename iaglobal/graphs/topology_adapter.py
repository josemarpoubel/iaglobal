"""TopologyAdapter — registro dinâmico de agentes e roteamento por fingerprint."""

import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AgentMetadata:
    name: str
    authority: str
    domain: str = "general"
    performance: float = 1.0
    active: bool = True


class AgentRegistry:
    """Registro dinâmico de agentes com metadados."""

    def __init__(self):
        self._agents: Dict[str, AgentMetadata] = {}

    def register(self, name: str, authority: str, domain: str = "general"):
        self._agents[name] = AgentMetadata(name=name, authority=authority, domain=domain)
        logger.info("[REGISTRY] Agente registrado: %s (domínio=%s, autoridade=%s)", name, domain, authority)

    def unregister(self, name: str):
        self._agents.pop(name, None)

    def get(self, name: str) -> Optional[AgentMetadata]:
        return self._agents.get(name)

    def list_by_domain(self, domain: str) -> List[AgentMetadata]:
        return [a for a in self._agents.values() if a.domain == domain and a.active]

    def list_active(self) -> List[AgentMetadata]:
        return [a for a in self._agents.values() if a.active]

    def deactivate(self, name: str):
        agent = self._agents.get(name)
        if agent:
            agent.active = False

    def count(self) -> int:
        return len(self._agents)


class TaskRouter:
    """Roteia tarefas para sub-DAGs baseado em fingerprint."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def route(self, task: str, domain: str = "") -> List[str]:
        dom = domain or self._detect_domain(task)
        agents = self.registry.list_by_domain(dom)

        if not agents:
            agents = self.registry.list_by_domain("general")

        return [a.name for a in agents[:5]]

    def _detect_domain(self, task: str) -> str:
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["php", "html", "css", "web", "frontend", "pagina"]):
            return "web"
        if any(kw in task_lower for kw in ["api", "rest", "endpoint", "graphql"]):
            return "api"
        if any(kw in task_lower for kw in ["banco", "database", "sql", "tabela", "query"]):
            return "data"
        if any(kw in task_lower for kw in ["security", "seguranca", "auth", "login", "owasp"]):
            return "security"
        return "general"
