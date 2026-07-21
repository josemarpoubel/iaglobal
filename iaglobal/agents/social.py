# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/agents/social.py

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


HEARTBEAT_TTL_SECONDS = 120
"""Um agente é considerado morto se não enviar heartbeat por esse período."""

CHANNEL_ADVERTISE = "social.agent.advertise"
"""Canal AcetylcholineBus para publicações de Advertisement."""

CHANNEL_HEARTBEAT = "social.agent.heartbeat"
"""Canal AcetylcholineBus para heartbeats de agente."""

CHANNEL_WITHDRAW = "social.agent.withdraw"
"""Canal AcetylcholineBus para remoção voluntária."""


@dataclass
class Capability:
    domain: str
    proficiency: float = 0.0
    latency_p50_ms: float = 0.0


@dataclass
class Advertisement:
    agent_id: str
    skills: dict[str, Capability] = field(default_factory=dict)
    load_factor: float = 0.0
    last_seen: float = field(default_factory=time.time)

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.last_seen) > HEARTBEAT_TTL_SECONDS

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "skills": {
                d: {
                    "domain": d,
                    "proficiency": c.proficiency,
                    "latency_p50_ms": c.latency_p50_ms,
                }
                for d, c in self.skills.items()
            },
            "load_factor": self.load_factor,
            "last_seen": self.last_seen,
        }


class SocialRegistry:
    _instance: Optional[SocialRegistry] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._advertisements: dict[str, Advertisement] = {}
        self._bus = None
        self._subscribed: list[Callable] = []

    @classmethod
    def get_instance(cls) -> SocialRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── CRUD ──────────────────────────────────────────────────────────

    def publish(self, adv: Advertisement) -> None:
        with self._lock:
            existing = self._advertisements.get(adv.agent_id)
            if existing:
                existing.skills.update(adv.skills)
                existing.load_factor = adv.load_factor
            else:
                self._advertisements[adv.agent_id] = adv

    def heartbeat(self, agent_id: str, load_factor: Optional[float] = None) -> None:
        with self._lock:
            adv = self._advertisements.get(agent_id)
            if adv:
                adv.last_seen = time.time()
                if load_factor is not None:
                    adv.load_factor = load_factor

    def withdraw(self, agent_id: str) -> Optional[Advertisement]:
        with self._lock:
            return self._advertisements.pop(agent_id, None)

    def get(self, agent_id: str) -> Optional[Advertisement]:
        with self._lock:
            adv = self._advertisements.get(agent_id)
            if adv and adv.is_stale:
                del self._advertisements[agent_id]
                return None
            return adv

    def query(self, domain: str, min_proficiency: float = 0.0) -> list[Advertisement]:
        """Retorna agentes com a skill `domain`, ordenados por proficiência descendente.

        Agentes stale são excluídos automaticamente.
        """
        now = time.time()
        result: list[Advertisement] = []
        stale_ids: list[str] = []
        with self._lock:
            for agent_id, adv in self._advertisements.items():
                if (now - adv.last_seen) > HEARTBEAT_TTL_SECONDS:
                    stale_ids.append(agent_id)
                    continue
                cap = adv.skills.get(domain)
                if cap is not None and cap.proficiency >= min_proficiency:
                    result.append(adv)
            for sid in stale_ids:
                del self._advertisements[sid]
        result.sort(key=lambda a: a.skills[domain].proficiency, reverse=True)
        return result

    def all_alive(self) -> list[Advertisement]:
        now = time.time()
        result: list[Advertisement] = []
        stale_ids: list[str] = []
        with self._lock:
            for agent_id, adv in self._advertisements.items():
                if (now - adv.last_seen) > HEARTBEAT_TTL_SECONDS:
                    stale_ids.append(agent_id)
                else:
                    result.append(adv)
            for sid in stale_ids:
                del self._advertisements[sid]
        return result

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._advertisements)

    def clear_stale(self) -> int:
        now = time.time()
        stale_ids: list[str] = []
        with self._lock:
            for agent_id, adv in self._advertisements.items():
                if (now - adv.last_seen) > HEARTBEAT_TTL_SECONDS:
                    stale_ids.append(agent_id)
            for sid in stale_ids:
                del self._advertisements[sid]
        return len(stale_ids)

    def to_dict(self) -> dict[str, Any]:
        return {adv.agent_id: adv.to_dict() for adv in self.all_alive()}

    # ── Integração com AcetylcholineBus ───────────────────────────────

    def start(self, bus=None) -> None:
        """Conecta ao AcetylcholineBus e escuta canais sociais.

        Chame isto durante o bootstrap (após bus inicializado).
        """
        if self._bus is not None:
            return
        if bus is None:
            from iaglobal.graphs.comms.acetylcholine_bus import bus as _bus

            bus = _bus
        self._bus = bus

        def _on_advertise(msg: Any) -> None:
            content = getattr(msg, "content", {}) or getattr(msg, "payload", {})
            agent_id = content.get("agent_id")
            if not agent_id:
                return
            skills_raw = content.get("skills", {})
            skills = {
                d: Capability(
                    domain=d,
                    proficiency=c.get("proficiency", 0.0),
                    latency_p50_ms=c.get("latency_p50_ms", 0.0),
                )
                for d, c in skills_raw.items()
            }
            adv = Advertisement(
                agent_id=agent_id,
                skills=skills,
                load_factor=content.get("load_factor", 0.0),
            )
            self.publish(adv)

        def _on_heartbeat(msg: Any) -> None:
            content = getattr(msg, "content", {}) or getattr(msg, "payload", {})
            agent_id = content.get("agent_id")
            if not agent_id:
                return
            self.heartbeat(agent_id, load_factor=content.get("load_factor"))

        def _on_withdraw(msg: Any) -> None:
            content = getattr(msg, "content", {}) or getattr(msg, "payload", {})
            agent_id = content.get("agent_id")
            if agent_id:
                self.withdraw(agent_id)

        bus.subscribe(CHANNEL_ADVERTISE, _on_advertise)
        bus.subscribe(CHANNEL_HEARTBEAT, _on_heartbeat)
        bus.subscribe(CHANNEL_WITHDRAW, _on_withdraw)
        self._subscribed = [_on_advertise, _on_heartbeat, _on_withdraw]

    def stop(self) -> None:
        """Desconecta do barramento."""
        if self._bus is None or not self._subscribed:
            return
        self._bus.unsubscribe(CHANNEL_ADVERTISE, self._subscribed[0])
        self._bus.unsubscribe(CHANNEL_HEARTBEAT, self._subscribed[1])
        self._bus.unsubscribe(CHANNEL_WITHDRAW, self._subscribed[2])
        self._subscribed = []
        self._bus = None


# Singleton global
social_registry = SocialRegistry.get_instance()
