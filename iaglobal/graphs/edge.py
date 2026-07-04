from dataclasses import dataclass


@dataclass
class Edge:
    """
    🔗 Representa conexão entre nodes.

    Preparado para futuras features:
    - weighting
    - probabilistic routing
    - reinforcement learning graph
    """
    source: str
    target: str
    weight: float = 1.0
