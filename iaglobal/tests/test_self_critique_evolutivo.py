# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes para Self-Critique Evolutivo.

Cobertura:
  - Avaliação de código Python
  - Avaliação de testes unitários
  - Geração de sugestões de refinamento
  - Integração com TesterAgent e DebuggerAgent
"""
import pytest
import asyncio

from iaglobal.reflection.self_critique_evolutivo import SelfCritiqueEvolutivo


class TestSelfCritiqueEvolutivo:
    """Testes para SelfCritiqueEvolutivo."""

    def setup_method(self):
        """Setup para cada teste."""
        self.critique = SelfCritiqueEvolutivo()

    def test_avaliar_codigo_sintaxe_valida(self):
        """Testa avaliação de código com sintaxe válida."""
        codigo = """
def soma(a, b):
    return a + b

resultado = soma(2, 3)
"""
        critique = self.critique.evaluate(codigo, contexto={"tipo": "codigo"})
        
        assert critique["score"] > 0.5
        assert "sintaxe_valida" in critique["forças"]
        assert critique["line_count"] > 0

    def test_avaliar_codigo_com_erro_sintaxe(self):
        """Testa avaliação de código com erro de sintaxe."""
        codigo = """
def soma(a, b)
    return a + b
"""
        critique = self.critique.evaluate(codigo, contexto={"tipo": "codigo"})
        
        # Erro de sintaxe reduz score mas não zera (outros critérios contam)
        assert "erro_sintaxe" in critique["fraquezas"]
        assert critique["score"] < 0.7  # Score reduzido

    def test_avaliar_codigo_sem_imports(self):
        """Testa avaliação de código sem imports problemáticos."""
        codigo = """
def fatorial(n):
    if n == 0:
        return 1
    return n * fatorial(n - 1)
"""
        critique = self.critique.evaluate(codigo, contexto={"tipo": "codigo"})
        
        assert "imports_resolvidos" in critique["forças"]

    def test_avaliar_codigo_com_tratamento_erros(self):
        """Testa avaliação de código com tratamento de erros."""
        codigo = """
def divide(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        return None
"""
        critique = self.critique.evaluate(codigo, contexto={"tipo": "codigo"})
        
        assert "tratamento_erros" in critique["forças"]
        assert critique["score"] > 0.6

    def test_avaliar_testes_com_asserts(self):
        """Testa avaliação de testes com asserts."""
        testes = """
def test_soma():
    assert soma(2, 3) == 5
    assert soma(-1, 1) == 0

def test_soma_edge_cases():
    assert soma(0, 0) == 0
    assert soma(None, 1) is None
"""
        critique = self.critique.evaluate(
            testes,
            contexto={
                "tipo": "testes",
                "codigo_original": "def soma(a, b): return a + b",
            },
        )
        
        assert critique["score"] > 0.5
        assert "asserts_presentes" in critique["forças"]

    def test_avaliar_testes_sem_asserts(self):
        """Testa avaliação de testes sem asserts."""
        testes = """
def test_soma():
    resultado = soma(2, 3)
    print(resultado)
"""
        critique = self.critique.evaluate(
            testes,
            contexto={
                "tipo": "testes",
                "codigo_original": "def soma(a, b): return a + b",
            },
        )
        
        assert "sem_asserts" in critique["fraquezas"]
        assert critique["score"] < 0.6

    def test_avaliar_testes_com_edge_cases(self):
        """Testa avaliação de testes com edge cases."""
        testes = """
def test_divide():
    assert divide(10, 2) == 5
    assert divide(0, 1) == 0
    assert divide(1, 0) is None  # Edge case
    assert divide(-10, 2) == -5  # Edge case
"""
        critique = self.critique.evaluate(
            testes,
            contexto={
                "tipo": "testes",
                "codigo_original": "def divide(a, b): ...",
            },
        )
        
        assert "edge_cases" in str(critique["forças"])
        assert critique["score"] > 0.6

    def test_gerar_sugestoes_refinamento(self):
        """Testa geração de sugestões de refinamento."""
        critique_dict = {
            "fraquezas": [
                "erro_sintaxe",
                "imports_problematicos",
                "sem_tratamento_erros",
            ],
        }
        
        sugestoes = self.critique.gerar_sugestoes_refinamento(critique_dict)
        
        assert len(sugestoes) > 0
        assert "Corrija erros de sintaxe" in sugestoes[0]
        assert "imports" in sugestoes[1].lower()

    def test_avaliar_testes_com_mocks(self):
        """Testa avaliação de testes com mocks."""
        testes = """
from unittest.mock import patch

@patch('requests.get')
def test_api_call(mock_get):
    mock_get.return_value.status_code = 200
    result = api_call()
    assert result is not None
"""
        critique = self.critique.evaluate(
            testes,
            contexto={
                "tipo": "testes",
                "codigo_original": "def api_call(): ...",
            },
        )
        
        assert "mocks_isolados" in critique["forças"]
        assert critique["score"] > 0.7

    def test_historico_criticas(self):
        """Testa se histórico de críticas é mantido."""
        # Cria nova instância para evitar histórico de outros testes
        critique_engine = SelfCritiqueEvolutivo()
        
        codigo = "def teste(): pass"
        
        critique_engine.evaluate(codigo, contexto={"tipo": "codigo"})
        critique_engine.evaluate(codigo, contexto={"tipo": "codigo"})
        
        # Cada evaluate chama o parent.evaluate() + adiciona ao history
        # Total: 4 entradas (2 base + 2 especificas)
        assert len(critique_engine.critique_history) >= 2


class TestIntegracaoTesterAgent:
    """Testes de integração com TesterAgent."""

    def test_tester_agent_com_validacao_local(self):
        """Testa se TesterAgent usa validacao local (Jedi/pyflakes)."""
        from iaglobal.agents.tester_agent import TesterAgent
        
        agent = TesterAgent()
        
        assert hasattr(agent, "_validar_testes_com_jedi")
        assert asyncio.iscoroutinefunction(agent._validar_testes_com_jedi)
        assert hasattr(agent, "_corrigir_testes_com_jedi")
        assert asyncio.iscoroutinefunction(agent._corrigir_testes_com_jedi)


class TestIntegracaoDebuggerAgent:
    """Testes de integração com DebuggerAgent."""

    def test_debugger_agent_com_auto_critica(self):
        """Testa se DebuggerAgent usa auto-crítica."""
        from iaglobal.agents.debugger_agent import DebuggerAgent
        
        agent = DebuggerAgent()
        
        # Verifica se método existe
        assert hasattr(agent, "_auto_critica_codigo")
        assert asyncio.iscoroutinefunction(agent._auto_critica_codigo)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])