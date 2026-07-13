# iaglobal/graphs/comms/__init__.py
"""Comunicação interna entre agentes do grafo."""

from iaglobal.graphs.comms.acetylcholine_bus import bus as acetylcholine_bus
from iaglobal.graphs.comms.agent_mailbox import AgentMailbox
from iaglobal.graphs.comms.membrane_key import MembraneKey

__all__ = ["acetylcholine_bus", "AgentMailbox", "MembraneKey"]