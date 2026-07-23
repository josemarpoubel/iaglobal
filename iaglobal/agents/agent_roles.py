# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

# iaglobal/agents/agent_roles.py

"""
AgentRole — Papel cognitivo de um nó no pipeline iaglobal.
"""

from enum import Enum


class AgentRole(str, Enum):
    """Papel cognitivo de um nó no pipeline iaglobal."""

    LOCAL = "local"
    CRITIC = "critic"
    # Adicione as variantes não registradas aqui, por exemplo:
    CRITIC_GAP = "critic_gap"
    CRITIC_BANDIT = "critic_bandit"
