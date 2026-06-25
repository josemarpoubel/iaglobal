# tests/test_meta_director.py
"""Testes do diretor de propósito macro."""
import pytest

from iaglobal.intention.meta_director import MetaDirector, MetaIntent, MetaObjective


class TestMetaDirector:
    """Testa propósito macro com proteção imunológica."""

    def test_meta_objective_creation(self):
        """MetaObjective é criado corretamente."""
        obj = MetaObjective(
            intent=MetaIntent.RESEARCH,
            description="Novel algorithm discovery",
            success_criteria=["novel", "validated"]
        )
        
        assert obj.intent == MetaIntent.RESEARCH
        assert obj.max_cycles == 100

    def test_decompose_research(self):
        """Decompõe pesquisa em tarefas."""
        director = MetaDirector()
        
        tasks = director._decompose(
            MetaObjective(
                intent=MetaIntent.RESEARCH,
                description="test",
                success_criteria=[]
            )
        )
        
        assert "gather_knowledge" in tasks

    def test_queue_global_objective(self):
        """Enfileira objetivo global."""
        director = MetaDirector()
        
        queued_id = director.queue_global_objective(
            "research", 
            "Explore quantum algorithms"
        )
        
        assert queued_id.startswith("queued_research")