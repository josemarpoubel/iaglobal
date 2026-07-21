# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
RoleResolver — resolve AgentRole a partir de um node_id.

Fase 1: usa lista fechada de nós conhecidos como CRITIC.
Fase 3: a lista será substituída por consulta ao SkillRegistry.
"""

from iaglobal.core.agent_roles import AgentRole


_CRITIC_NODE_IDS = frozenset(
    {
        "critic",
        "critic_agent",
        "no_critic",
        "no_validator_retry",
        "no_law_of_thought_enforcer",
        "no_reflexion",
        "no_success_ritual",
        "no_reviewer",
    }
)


class RoleResolver:
    @classmethod
    def resolve(cls, node_id: str) -> AgentRole:
        nid = (node_id or "").strip().lower()
        if not nid:
            return AgentRole.LOCAL
        if nid in _CRITIC_NODE_IDS:
            return AgentRole.CRITIC
        return AgentRole.LOCAL
