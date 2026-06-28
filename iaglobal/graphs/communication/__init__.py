# iaglobal/graphs/communication/__init__.py
"""Communication subsystem for cellular signaling."""
from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus, AgentMessage
from iaglobal.graphs.communication.membrane_key import MembraneKey, membrane_key

__all__ = ["AcetylcholineBus", "AgentMessage", "MembraneKey", "membrane_key"]