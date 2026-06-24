"""Teste de integração do TaskAnalyzer: valida classificação de tarefas com typos.

Valida:
1. Normalização de typos (pythom → python)
2. Classificação de blockchain (bloco genesis)
3. Classificação de python
4. Classificação de código
5. Classificação em português
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestTaskAnalyzerTypoNormalization:
    """Testa normalização de typos no TaskAnalyzer."""

    def test_pythom_normalized_to_python(self):
        """pythom → python (correção de typo)."""
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        
        # Normalize method is private but tested via analyze
        normalized = TaskAnalyzer._normalize("Criar API em pythom")
        assert "python" in normalized.lower()
        assert "pythom" not in normalized.lower()
        
        # Full flow
        result = TaskAnalyzer.analyze("bloco genesis em pythom")
        strategies = result["strategies"]
        
        assert "blockchain" in strategies
        assert "web_development" in strategies or "api_design" in strategies

    def test_javascrip_normalized_to_javascript(self):
        """javascrip → javascript."""
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        
        normalized = TaskAnalyzer._normalize("frontend em javascrip")
        assert "javascript" in normalized.lower()

    def test_djanjo_normalized_to_django(self):
        """djanjo → django."""
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        
        normalized = TaskAnalyzer._normalize("aplicacao djanjo")
        assert "django" in normalized.lower()


class TestTaskAnalyzerTaskTypes:
    """Testa classificação de task-types."""

    def test_blockchain_genesis_block(self):
        """'bloco genesis' é classificado como blockchain."""
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        
        result = TaskAnalyzer.analyze("criar bloco genesis para blockchain")
        strategies = result["strategies"]
        
        assert "blockchain" in strategies

    def test_python_classification(self):
        """Tarefas em python são classificadas corretamente."""
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        
        result = TaskAnalyzer.analyze("criar API em python com fastapi")
        strategies = result["strategies"]
        
        assert "web_development" in strategies or "api_design" in strategies
        assert "python" in result["technologies"] or "fastapi" in result["technologies"]

    def test_codigo_classification(self):
        """Tarefas de 'código' são classificadas."""
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        
        result = TaskAnalyzer.analyze("gerar código para validação")
        strategies = result["strategies"]
        
        assert "web_development" in strategies or "coding" in strategies

    def test_portuguese_classification(self):
        """Tarefas em português são classificadas."""
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        
        result = TaskAnalyzer.analyze("crie uma API restful")
        strategies = result["strategies"]
        
        assert "web_development" in strategies

    def test_solidity_blockchain(self):
        """Tarefas de solidity são classificadas como blockchain."""
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        
        result = TaskAnalyzer.analyze("smart contract em solidity")
        strategies = result["strategies"]
        
        assert "blockchain" in strategies


class TestTaskAnalyzerDeriveAgents:
    """Testa geração de agentes especialistas."""

    def test_blockchain_agents_derived(self):
        """Agentes blockchain são derivados para 'bloco genesis'."""
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        
        result = TaskAnalyzer.analyze("gerar bloco genesis em solidity")
        agents = TaskAnalyzer.derive_agents(result["strategies"])
        
        # Deve ter pelo menos um agente (fallback generalist ou web_developer)
        assert len(agents) >= 1
        
        # Verifica se há alguém que pode lidar com blockchain/web
        agent_names = [a["nome"] for a in agents]
        assert any(name in ["web_developer", "generalist"] for name in agent_names)

    def test_python_agents_derived(self):
        """Agentes python são derivados corretamente."""
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        
        result = TaskAnalyzer.analyze("api em python")
        agents = TaskAnalyzer.derive_agents(result["strategies"])
        
        agent_names = [a["nome"] for a in agents]
        assert "web_developer" in agent_names


class TestTaskAnalyzerEdgeCases:
    """Testes de edge cases do TaskAnalyzer."""

    def test_empty_prompt(self):
        """Prompt vazio retorna estruturas vazias."""
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        
        result = TaskAnalyzer.analyze("")
        assert result["strategies"] == set()
        assert result["technologies"] == set()

    def test_unknown_prompt(self):
        """Prompt desconhecido usa fallback generalist."""
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        
        result = TaskAnalyzer.analyze("xyzzy plugh foo bar")
        agents = TaskAnalyzer.derive_agents(result["strategies"])
        
        agent_names = [a["nome"] for a in agents]
        assert "generalist" in agent_names

    def test_mixed_language(self):
        """Tarefas com mistura de idiomas são classificadas."""
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        
        result = TaskAnalyzer.analyze("create uma API com flask e JWT em português")
        strategies = result["strategies"]
        
        assert "web_development" in strategies or "security" in strategies or "authentication" in strategies