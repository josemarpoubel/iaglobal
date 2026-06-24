"""Teste de integração do Knowledge Flow: rastreia conhecimento entre
knowledge.json → no_knowledge.py → knowledge_agent.py → retrieve_relevant → KnowledgeGraph.

Cobre:
1. KnowledgeAgent.store() persiste em knowledge.json
2. KnowledgeAgent.retrieve_relevant() recupera dados do cache
3. KnowledgeGraph.extract_and_store() indexa conceitos
4. KnowledgeGraph.get_top_concepts() retorna conceitos indexados
5. Integração completa: no_knowledge → KnowledgeAgent → KnowledgeGraph
"""
import os
import sys
import json
import pytest
import sqlite3
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestKnowledgeFlowIntegration:
    """Testa o fluxo completo de conhecimento no ecossistema."""

    @pytest.fixture
    def clean_knowledge_file(self, tmp_path):
        """Cria um knowledge.json vazio em temp dir."""
        from iaglobal._paths import KNOWLEDGE_FILE
        original_path = KNOWLEDGE_FILE
        
        # Patch the path
        test_file = tmp_path / "knowledge.json"
        test_file.write_text("[]")
        
        # Monkey-patch
        import iaglobal.evolution.agents.knowledge_agent as ka_module
        ka_module.KNOWLEDGE_FILE = test_file
        
        # Also patch in _paths
        import iaglobal._paths as paths_module
        original_knowledge_file = paths_module.KNOWLEDGE_FILE
        paths_module.KNOWLEDGE_FILE = test_file
        
        yield test_file
        
        # Restore
        ka_module.KNOWLEDGE_FILE = original_path
        paths_module.KNOWLEDGE_FILE = original_knowledge_file

    def test_knowledge_agent_store_persists_to_json(self, clean_knowledge_file):
        """1. KnowledgeAgent.store() persiste em knowledge.json."""
        from iaglobal.evolution.agents.knowledge_agent import KnowledgeAgent
        
        agent = KnowledgeAgent()
        agent.store(
            category="best_practice",
            title="Test Practice",
            content="This is test knowledge content for integration",
            tags=["test", "integration"],
            source="pytest",
        )
        
        # Verifica arquivo JSON foi atualizado
        with open(clean_knowledge_file) as f:
            data = json.load(f)
        
        assert len(data) == 1
        assert data[0]["title"] == "Test Practice"
        assert data[0]["category"] == "best_practice"
        assert "test" in data[0]["tags"]

    def test_knowledge_agent_retrieve_relevant_returns_stored(self, clean_knowledge_file):
        """2. KnowledgeAgent.retrieve_relevant() recupera dados do cache."""
        from iaglobal.evolution.agents.knowledge_agent import KnowledgeAgent
        
        agent = KnowledgeAgent()
        agent.store(
            category="architecture",
            title="Flask Architecture Pattern",
            content="Flask is a Python web framework for building APIs",
            tags=["flask", "python", "web"],
            source="pytest",
        )
        
        # Recupera usando palavra-chave
        results = agent.retrieve_relevant("Flask API development", max_results=5)
        
        assert len(results) >= 1
        assert any("flask" in r.get("content", "").lower() for r in results)

    def test_knowledge_graph_extract_and_store(self, tmp_path):
        """3. KnowledgeGraph.extract_and_store() indexa conceitos."""
        from iaglobal.memory.fusion_engine import KnowledgeGraph, CORE_DB
        from iaglobal._paths import get_db_connection
        
        # Use temp database
        test_db = tmp_path / "test_core.db"
        
        kg = KnowledgeGraph(db_path=str(test_db))
        concepts = kg.extract_and_store(
            "Python FastAPI is a modern web framework for building APIs",
            source="pytest_integration"
        )
        
        # Verifica conceitos foram extraídos
        assert len(concepts) >= 1
        assert "Python" in concepts or "FastAPI" in concepts

    def test_knowledge_graph_get_top_concepts(self, tmp_path):
        """4. KnowledgeGraph.get_top_concepts() retorna conceitos indexados."""
        from iaglobal.memory.fusion_engine import KnowledgeGraph
        
        test_db = tmp_path / "test_kg.db"
        
        kg = KnowledgeGraph(db_path=str(test_db))
        
        # Indexa múltiplos conceitos
        kg.extract_and_store("Python and Django for web development", source="test1")
        kg.extract_and_store("FastAPI and Python for APIs", source="test2")
        kg.extract_and_store("JavaScript React for frontend", source="test3")
        
        top = kg.get_top_concepts(limit=10)
        assert len(top) >= 1
        # Python deve aparecer com frequência 2
        python_entry = next((e for e in top if e["name"] == "Python"), None)
        assert python_entry is not None
        assert python_entry["frequency"] >= 2

    def test_no_knowledge_integration_flow(self, clean_knowledge_file, tmp_path):
        """5. Integração completa: no_knowledge → KnowledgeAgent → KnowledgeGraph."""
        import asyncio
        from iaglobal.graphs.nodes.no_knowledge import run_knowledge, _get_kgraph
        from iaglobal.evolution.agents.knowledge_agent import knowledge as knowledge_agent
        
        # Patch KnowledgeGraph path
        import iaglobal.memory.fusion_engine as fe_module
        test_db = tmp_path / "test_full.db"
        fe_module.CORE_DB = str(test_db)
        
        # Mock memory with search results
        ctx = {
            "input": {"task": "Create a Flask API"},
            "memory": {
                "search": {"output": "Flask is a lightweight Python web framework. FastAPI is modern."},
                "local_knowledge": {},
            },
        }
        
        # Executa o nó assíncrono
        result = asyncio.run(run_knowledge(ctx))
        
        # Verifica resultado
        assert "output" in result
        assert "knowledge" in result
        assert "execution_metrics" in result
        assert result["execution_metrics"]["success"] is True
        
        # Verifica que KnowledgeGraph foi chamado
        kg = _get_kgraph()
        concepts = kg.get_top_concepts(limit=5)
        
        # Conceitos do search devem estar indexados
        assert any("Flask" in c["name"] or "FastAPI" in c["name"] for c in concepts)


class TestKnowledgeEdgeCases:
    """Testes de edge cases do sistema de conhecimento."""

    def test_empty_knowledge_returns_empty_list(self):
        """retrieve_relevant retorna lista vazia quando não há conhecimento."""
        from iaglobal.evolution.agents.knowledge_agent import KnowledgeAgent
        
        # Usa cache vazio
        agent = KnowledgeAgent()
        agent._cache = []
        
        results = agent.retrieve_relevant("any query")
        assert results == []

    def test_knowledge_deduplication(self):
        """KnowledgeAgent não duplica entradas idênticas."""
        from iaglobal.evolution.agents.knowledge_agent import KnowledgeAgent
        
        agent = KnowledgeAgent()
        agent._cache = []
        
        agent.store(
            category="best_practice",
            title="Duplicate Test",
            content="Same content",
            tags=["test"],
            source="pytest",
        )
        
        # Tentativa de duplicar
        agent.store(
            category="best_practice",
            title="Duplicate Test",
            content="Same content",
            tags=["test"],
            source="pytest",
        )
        
        assert len(agent._cache) == 1


class TestKnowledgeGraphRelationships:
    """Testes de relacionamentos no KnowledgeGraph."""

    def test_relationships_created_for_co_occurring_concepts(self, tmp_path):
        """Relacionamentos são criados para conceitos que co-ocorrem."""
        from iaglobal.memory.fusion_engine import KnowledgeGraph
        
        test_db = tmp_path / "test_rels.db"
        kg = KnowledgeGraph(db_path=str(test_db))
        
        # Texto com múltiplos conceitos
        kg.extract_and_store(
            "Python Django and PostgreSQL for web development",
            source="test"
        )
        
        # Verifica relacionamentos (usar max_results, não limit)
        relations = kg.get_related("Python", max_results=5)
        assert len(relations) >= 1
        
        related_names = [r["concept"] for r in relations]
        assert any("Django" in n or "PostgreSQL" in n for n in related_names)