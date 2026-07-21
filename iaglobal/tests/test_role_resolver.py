# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes unitários para RoleResolver — Fase 1 da refatoração de papéis.

Nenhuma dependência externa: apenas lógica pura de mapeamento node_id → AgentRole.
"""

import pytest

from iaglobal.core.agent_roles import AgentRole
from iaglobal.core.role_resolver import RoleResolver


class TestRoleResolver:
    """Valida RoleResolver.resolve(node_id) sem tocar no TaskRouter ou provider_router."""

    def test_critic_names_are_critic(self):
        for node_id in ("critic", "critic_agent", "no_critic"):
            assert RoleResolver.resolve(node_id) == AgentRole.CRITIC

    def test_known_critic_nodes_are_critic(self):
        known = [
            "no_validator_retry",
            "no_reflexion",
            "no_reviewer",
        ]
        for node_id in known:
            assert RoleResolver.resolve(node_id) == AgentRole.CRITIC, node_id

    def test_local_nodes_are_local(self):
        for node_id in (
            "coder",
            "tester",
            "planner",
            "pm",
            "architect",
            "debugger_agent",
        ):
            assert RoleResolver.resolve(node_id) == AgentRole.LOCAL

    def test_empty_and_none_are_local(self):
        assert RoleResolver.resolve("") == AgentRole.LOCAL
        assert RoleResolver.resolve(None) == AgentRole.LOCAL
        assert RoleResolver.resolve("   ") == AgentRole.LOCAL

    def test_case_insensitive(self):
        assert RoleResolver.resolve("CRITIC") == AgentRole.CRITIC
        assert RoleResolver.resolve("Critic_Agent") == AgentRole.CRITIC
        assert RoleResolver.resolve("NO_CRITIC") == AgentRole.CRITIC
        assert RoleResolver.resolve("CODER") == AgentRole.LOCAL

    def test_false_positive_critic_substring_is_local(self):
        # Fase 2+ usa lista fechada, não substring; estes não são falsos-positivos.
        for node_id in (
            "critical_path",
            "criticidade",
            "no_critical_thinking",
            "critical_analysis",
        ):
            assert RoleResolver.resolve(node_id) == AgentRole.LOCAL, node_id

    @pytest.mark.xfail(
        reason="Phase 1 closed set incomplete; these are known desired CRITIC roles missing from _CRITIC_NODE_IDS.",
        strict=True,
    )
    def test_unregistered_critic_variants_not_yet_in_list(self):
        for node_id in ("critic_batch",):
            assert RoleResolver.resolve(node_id) == AgentRole.CRITIC, node_id
