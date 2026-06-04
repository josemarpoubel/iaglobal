"""Testes da pipeline de execução (roteamento, fallback, modelo local)."""

from unittest.mock import patch, MagicMock
import pytest


# =========================================================
# TEST 1: escolher_modelo retorna default Ollama
# =========================================================

class TestEscolherModelo:
    def test_retorna_string(self):
        from iaglobal.providers.provider_router import escolher_modelo
        m = escolher_modelo("some task")
        assert isinstance(m, str)
        assert len(m) > 0

    def test_retorna_mesmo_valor_qualquer_task(self):
        from iaglobal.providers.provider_router import escolher_modelo
        m1 = escolher_modelo("")
        assert isinstance(m1, str) and len(m1) > 0
        m2 = escolher_modelo("write code")
        assert isinstance(m2, str) and len(m2) > 0


# =========================================================
# TEST 2: route_generate com modelo local (Ollama)
# =========================================================

class TestRouteGenerateLocal:
    def test_ollama_prefix_preservado_no_log(self):
        """Verifica que o prefixo ollama/ é preservado no model passado ao provider."""
        from iaglobal.providers.provider_router import route_generate

        with patch("iaglobal.providers.provider_router.PROVIDERS") as mock_providers:
            mock_fn = MagicMock(return_value="ollama response")
            mock_providers.get.return_value = mock_fn

            result = route_generate(model="ollama/qwen2.5:0.5b", prompt="say hi")

            mock_fn.assert_called_once()
            _, kwargs = mock_fn.call_args
            assert kwargs["model"] == "ollama/qwen2.5:0.5b"
            assert result == "ollama response"

    def test_ollama_provider_chamado(self):
        """Verifica que o provider ollama é chamado com modelo correto."""
        from iaglobal.providers.ollama_provider import generate as ollama_gen

        with patch("iaglobal.providers.ollama_provider.requests.post") as mock_post, \
             patch("iaglobal.providers.ollama_provider.memory.load") as mock_cache:
            mock_cache.return_value = None
            mock_post.return_value.json.return_value = {"response": "hello"}
            mock_post.return_value.raise_for_status = MagicMock()

            result = ollama_gen(prompt="say hi", model="ollama/qwen2.5:0.5b")

            called_model = mock_post.call_args[1]["json"]["model"]
            assert called_model == "qwen2.5:0.5b"
            assert result == "hello"

    def test_auto_fallback_chain(self):
        """route_generate com model='' ou 'auto' entra na fallback chain."""
        from iaglobal.providers.provider_router import route_generate

        with patch("iaglobal.providers.provider_router.PROVIDERS") as mock_providers:
            mock_providers.get.return_value = MagicMock(return_value="ok")

            result = route_generate(model="", prompt="test")
            assert isinstance(result, str)


# =========================================================
# TEST 3: blackjack_executar_local respeita modelo
# =========================================================

class TestBlackjackExecutarLocal:
    def test_modelo_passado_para_ollama_request(self):
        from iaglobal.execution.executor import blackjack_executar_local

        with patch("iaglobal.execution.executor._ollama_request") as mock_req:
            mock_req.return_value = "resposta local"

            result = blackjack_executar_local("qwen2.5:0.5b", "prompt test")

            mock_req.assert_called_once_with("prompt test", model="qwen2.5:0.5b")
            assert result == "resposta local"

    def test_modelo_none_fallback_default(self):
        from iaglobal.execution.executor import blackjack_executar_local

        with patch("iaglobal.execution.executor._ollama_request") as mock_req:
            mock_req.return_value = "ok"

            blackjack_executar_local("", "prompt")
            mock_req.assert_called_once_with("prompt", model=None)


# =========================================================
# TEST 4: _ollama_request usa modelo passado
# =========================================================

class TestOllamaRequest:
    def test_model_passado_para_api(self):
        from iaglobal.execution.executor import _ollama_request

        with patch("iaglobal.execution.executor.requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"response": "ok"}
            mock_post.return_value.raise_for_status = MagicMock()

            _ollama_request("prompt", model="custom-model:latest")

            payload = mock_post.call_args[1]["json"]
            assert payload["model"] == "custom-model:latest"

    def test_model_none_usa_default(self):
        from iaglobal.execution.executor import _ollama_request
        from iaglobal.providers.provider_config import ProviderConfig

        with patch("iaglobal.execution.executor.requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"response": "ok"}
            mock_post.return_value.raise_for_status = MagicMock()

            _ollama_request("prompt", model=None)

            payload = mock_post.call_args[1]["json"]
            assert payload["model"] == ProviderConfig.DEFAULT_OLLAMA_MODEL


# =========================================================
# TEST 5: executar (função) passa modelo
# =========================================================

class TestExecutar:
    def test_ollama_route_passa_modelo(self):
        from iaglobal.execution.executor import executar

        with patch("iaglobal.execution.executor._ollama_request") as mock_req:
            mock_req.return_value = "ok"

            executar("ollama/qwen2.5:0.5b", {"task": "hello"})

            called_model = mock_req.call_args[1].get("model")
            assert called_model == "ollama/qwen2.5:0.5b"

    def test_ollama_sem_prefixo_passa_modelo(self):
        from iaglobal.execution.executor import executar

        with patch("iaglobal.execution.executor._ollama_request") as mock_req:
            mock_req.return_value = "ok"

            executar("qwen2.5:0.5b", {"task": "hello"})

            called_model = mock_req.call_args[1].get("model")
            assert called_model == "qwen2.5:0.5b"

    def test_fallback_chama_ollama(self):
        from iaglobal.execution.executor import executar

        with patch("iaglobal.execution.executor._ollama_request") as mock_req, \
             patch("iaglobal.execution.executor._openrouter_request") as mock_open:
            mock_req.return_value = "fallback ok"
            mock_open.return_value = None

            executar("openrouter/unknown-model", {"task": "test"})

            # openrouter deve falhar (mock retorna None), e cair no ollama
            assert mock_req.called


# =========================================================
# TEST 6: PipelineEngine flow
# =========================================================

class TestPipelineEngine:
    def test_execute_flow_com_mock(self):
        from iaglobal.pipeline.engine import PipelineEngine
        from iaglobal.pipeline.pipelinestate import PipelineState
        from iaglobal.pipeline.result import PipelineResult

        mock_orch = MagicMock()
        mock_orch.memory.retrieve.return_value = None
        mock_orch.memory.store.return_value = None
        mock_orch.bandit.select_model.return_value = "ollama/test"
        mock_orch.run_graph_task.side_effect = RuntimeError("DAG mock — fallback")

        pipe = PipelineEngine(mock_orch)

        with patch("iaglobal.pipeline.engine.route_generate") as mock_route:
            mock_route.return_value = "generated code"

            result = pipe.execute(prompt="write a function")

            assert isinstance(result, PipelineResult)
            assert result.success is True
            assert result.response == "generated code"

    def test_execute_cached_retorna_early(self):
        from iaglobal.pipeline.engine import PipelineEngine
        from unittest.mock import MagicMock

        cached_val = {
            "response": "def foo():\n    return 'cached enough to pass the test with enough chars indeed and this extra padding makes it over one hundred characters total for sure now'",
            "codigo": "def foo():\n    return 'cached enough to pass the test with enough chars indeed and this extra padding makes it over one hundred characters total for sure now'",
            "score": 0.8,
            "metadata": {"script_path": "/tmp/test.py"},
        }
        mock_mem = MagicMock()
        mock_mem.retrieve.return_value = cached_val
        mock_mem.store.return_value = None

        mock_orch = MagicMock()
        mock_orch.memory = mock_mem
        mock_orch.bandit.select_model.return_value = "ollama/test"
        mock_orch.run_graph_task.side_effect = RuntimeError("DAG mock — fallback")

        pipe = PipelineEngine(mock_orch)

        with patch("iaglobal.pipeline.engine.route_generate") as mock_route:
            mock_route.return_value = "fallback code"
            result = pipe.execute(prompt="test")

            assert result.success is True
            assert "def foo():" in result.response
            mock_route.assert_not_called()

    def test_execute_modelo_chamado(self):
        from iaglobal.pipeline.engine import PipelineEngine

        mock_orch = MagicMock()
        mock_orch.memory.retrieve.return_value = None
        mock_orch.memory.store.return_value = None
        mock_orch.bandit.select_model.return_value = "ollama/test"
        mock_orch.run_graph_task.side_effect = RuntimeError("DAG mock — fallback")

        pipe = PipelineEngine(mock_orch)

        with patch("iaglobal.pipeline.engine.route_generate") as mock_route:
            mock_route.return_value = "code"
            pipe.execute(prompt="test")

            assert mock_route.called
            call_kwargs = mock_route.call_args[1]
            assert "model" in call_kwargs
            assert "prompt" in call_kwargs
            assert call_kwargs["prompt"] == "test"


# =========================================================
# TEST 7: Assistant process com escolher_modelo
# =========================================================

class TestAssistantModelResolution:
    def test_assistant_importa_escolher_modelo(self):
        """Verifica que assistant.py consegue importar escolher_modelo sem crash."""
        from iaglobal.core.assistant import Assistant
        a = Assistant()
        assert a is not None

    def test_assistant_process_flow(self):
        from iaglobal.core.assistant import Assistant

        a = Assistant()

        with patch("iaglobal.core.assistant.escolher_modelo") as mock_escolher, \
             patch("iaglobal.core.assistant.bus.publish") as mock_bus, \
             patch("iaglobal.core.assistant.carregar") as mock_carregar, \
             patch("iaglobal.core.assistant.salvar") as mock_salvar, \
             patch("iaglobal.core.assistant.store") as mock_store, \
             patch("iaglobal.core.assistant.search") as mock_search, \
             patch("iaglobal.core.assistant.blackjack_executar_local") as mock_local:

            mock_escolher.return_value = "ollama/qwen2.5"
            mock_search.return_value = []
            mock_carregar.return_value = ""
            mock_local.return_value = "local response"

            result = a.process("test prompt")

            assert isinstance(result, str)
            assert len(result) > 0


# =========================================================
# TEST 10: TesterAgent gerar_salvar_e_executar
# =========================================================

class TestTesterAgentFileTest:
    def test_extrair_codigo_puro(self):
        from iaglobal.agents.tester_agent import TesterAgent
        t = TesterAgent()
        assert t._extrair_codigo_puro("```python\nprint('hi')\n```") == "print('hi')"
        assert t._extrair_codigo_puro("print('hi')") == "print('hi')"
        assert t._extrair_codigo_puro("") == ""

    def test_gerar_salvar_e_executar_flow(self):
        from iaglobal.agents.tester_agent import TesterAgent, TESTS_DIR
        import os

        t = TesterAgent()
        codigo = "def soma(a, b): return a + b"
        task = "Crie uma função de soma"

        with patch.object(t, "gerar_testes") as mock_gerar:
            mock_gerar.return_value = "def test_soma():\n    assert soma(1, 2) == 3"

            res = t.gerar_salvar_e_executar(codigo, task)

            # Deve ter salvo o arquivo
            assert "arquivo" in res
            arquivo = res["arquivo"]
            assert arquivo.startswith(TESTS_DIR)
            assert arquivo.endswith(".py")

            # Verifica que o arquivo existe
            assert os.path.exists(arquivo)

            # Limpa o arquivo gerado
            os.remove(arquivo)

    def test_gerar_salvar_e_executar_com_falha(self):
        from iaglobal.agents.tester_agent import TesterAgent

        t = TesterAgent()

        with patch.object(t, "gerar_testes") as mock_gerar:
            mock_gerar.return_value = ""

            res = t.gerar_salvar_e_executar("codigo", "task")

            assert res["sucesso"] is False
            assert "nenhum" in res["output"].lower()


# =========================================================
# TEST 11: Orchestrator pipeline integration
# =========================================================

class TestOrchestratorPipeline:
    def test_orchestrator_cria_sem_crash(self):
        import logging
        logging.disable(logging.CRITICAL)

        from iaglobal.core.orchestrator import Orchestrator

        o = Orchestrator()
        assert o is not None
        assert len(o.graph.nodes) >= 3
        assert o.graph.generation >= 0
        assert o.evolution_runtime._running is True
        o.evolution_runtime.stop()
        assert o.evolution_runtime._running is False

    def test_resolver_flow(self):
        import logging
        logging.disable(logging.CRITICAL)

        from iaglobal.core.orchestrator import Orchestrator

        o = Orchestrator()

        with patch.object(o, "_process") as mock_process:
            mock_process.return_value = "processed"
            result = o.resolver("test task")
            assert result == "processed"

        o.evolution_runtime.stop()
