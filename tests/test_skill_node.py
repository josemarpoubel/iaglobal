# iaglobal/tests/test_skill_node.py
"""Testes para a refatoração SkillNode."""
import pytest
from iaglobal.graphs.skill_node import SkillNode


class TestSkillNode:
    def test_skill_node_has_name(self):
        node = SkillNode(name="test", skill_name="debugger")
        assert node.name == "test"

    def test_skill_node_uses_own_skill_name(self):
        node = SkillNode(name="custom", skill_name="reviewer")
        assert node._skill_name == "reviewer"

    def test_skill_node_defaults_to_name(self):
        node = SkillNode(name="tester")
        assert node._skill_name == "tester"

    def test_skill_node_defaults_to_name(self):
        node = SkillNode(name="tester")
        assert node._skill_name == "tester"