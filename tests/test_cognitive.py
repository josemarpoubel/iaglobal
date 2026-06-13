# test_cognitive.py

import pytest
from unittest.mock import MagicMock, patch
from iaglobal.core.cognitive_proxy import CognitiveProxy, ProxyResult
from iaglobal.cognition.task_fingerprint import TaskFingerprint

# 1. Setup do Fixture
@pytest.fixture
def proxy():
    """Cria um proxy com componentes mockados."""
    # Desabilitamos web e cache para testes unitários rápidos
    return CognitiveProxy(web_enabled=False, semantic_cache=False, retry_enabled=False)

# 2. Teste do Pipeline de Execução
def test_cognitive_proxy_run_success(proxy):
    # Mock das dependências internas
    proxy.task_classifier.classify = MagicMock(return_value=TaskFingerprint(domain="coding", intent="fix"))
    proxy._route = MagicMock(return_value=("def hello(): print('world')", "mock-model"))
    proxy.feedback.validate = MagicMock(return_value=MagicMock(valid=True, code="def hello(): print('world')"))
    
    result = proxy.run("conserte o código")
    
    assert isinstance(result, ProxyResult)
    assert result.success is True
    assert "hello" in result.output
    assert result.model_used == "mock-model"

# 3. Teste do Bandit e Evolução
def test_bandit_policy_integration(proxy):
    """Testa se o Bandit registra o resultado corretamente."""
    proxy.credit.record = MagicMock()
    
    # Simula chamada de registro
    proxy._record_bandit_result("mock-model", True, 0.5)
    
    # Verifica se o Bandit recebeu o evento
    assert proxy.credit.record.called
    args = proxy.credit.record.call_args[0][0]
    assert args.model == "mock-model"
    assert args.success is True

# 4. Teste de Validação (Feedback Engine)
def test_validation_logic(proxy):
    # Simula rejeição pelo FeedbackEngine
    proxy.feedback.validate = MagicMock(return_value=MagicMock(valid=False, errors=["syntax error"]))
    
    # Testa se o proxy processa a falha (deve retornar o output mesmo que inválido ou falhar)
    output, attempts = proxy._validate("prompt", "invalid code")
    assert attempts == 1
    # Nota: como o critic é um sensor passivo, ele deve continuar
    assert output == "invalid code"

# 5. Teste de Normalização (Anti-Ambiguidade)
def test_normalization():
    proxy = CognitiveProxy(web_enabled=False)
    input_text = "  Olá, Mundo!!!  "
    normalized = proxy._normalize(input_text)
    assert normalized == "olá, mundo!!!"
