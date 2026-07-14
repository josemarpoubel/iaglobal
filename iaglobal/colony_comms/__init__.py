# iaglobal/colony_comms/__init__.py
"""Protocolos de comunicação externa entre colônias/nós."""

from iaglobal.colony_comms.fitness import ColonyFitness
from iaglobal.colony_comms.genesis_handshake import GenesisHandshake
from iaglobal.colony_comms.integrator import ColonyIntegrator
from iaglobal.colony_comms.queen import ColonyQueen
from iaglobal.colony_comms.worker import ColonyWorker

__all__ = [
    "ColonyFitness",
    "GenesisHandshake",
    "ColonyIntegrator",
    "ColonyQueen",
    "ColonyWorker",
]
