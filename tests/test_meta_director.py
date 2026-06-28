# tests/test_meta_director.py
"""Testes do diretor de propósito macro."""
import pytest

from iaglobal.intention.meta_director import MetaDirector, MetaIntent, MetaObjective, LawOfSuccess


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

    def test_decompose_succeed(self):
        """Decompõe sucesso em tarefas."""
        director = MetaDirector()
        
        tasks = director._decompose(
            MetaObjective(
                intent=MetaIntent.SUCCEED,
                description="test",
                success_criteria=[]
            )
        )
        
        # SUCCEED deve ter tarefas alinhadas à evolução

    def test_law_of_success_validation(self):
        """Valida Lei do Sucesso."""
        valid = LawOfSuccess.validate_action({
            "ivm": 0.9,
            "threats_detected": False,
            "disciplined_execution": True,
        })
        
        assert valid == "ALINHADO: O propósito é digno."

    def test_law_of_success_violation(self):
        """Detecta violação da Lei do Sucesso."""
        invalid = LawOfSuccess.validate_action({
            "ivm": 0.3,
            "threats_detected": True,
            "disciplined_execution": False,
        })
        
        assert "DESCALIBRADO" in invalid or "VIOLAÇÃO" in invalid

    def test_queue_global_objective(self):
        """Enfileira objetivo global."""
        director = MetaDirector()
        
        queued_id = director.queue_global_objective(
            "research", 
            "Explore quantum algorithms"
        )
        
        assert queued_id.startswith("queued_research")