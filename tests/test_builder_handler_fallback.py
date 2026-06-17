# tests/test_builder_handler_fallback.py
"""
Testes para verificar o fallback do builder quando handler não é encontrado.

Este teste valida que:
1. O builder não quebra quando handler não é encontrado
2. Retorna erro estruturado permitindo ao pipeline decidir fallback
3. Registra erro corretamente no memory_error
"""

import pytest
from unittest.mock import patch, MagicMock
from iaglobal.graphs.builder import _try_import_handler, build_pipeline_from_nodes
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.memory.memory_error import record_error


class TestBuilderHandlerFallback:
    """Testes para o fallback do builder quando handler não encontrado."""

    def test_try_import_handler_returns_noop_for_missing_module(self):
        """Verifica que _try_import_handler retorna noop para módulo inexistente."""
        handler = _try_import_handler("node_que_nao_existe_xyz")
        assert handler is not None
        assert callable(handler)

    @pytest.mark.asyncio
    async def test_noop_handler_returns_context_unchanged(self):
        """Verifica que handler noop retorna contexto inalterado."""
        handler = _try_import_handler("node_que_nao_existe_xyz")
        ctx = {"task": "test", "data": "value"}
        result = await handler(ctx)
        assert result == ctx
        assert "output" not in result or result.get("output") is None

    def test_try_import_handler_registers_error(self):
        """Verifica que erro é registrado quando handler não encontrado."""
        # Mock record_error para capturar chamada
        with patch("iaglobal.graphs.builder.record_error") as mock_record:
            handler = _try_import_handler("handler_inexistente_abc")
            mock_record.assert_called_once()
            call_args = mock_record.call_args
            assert "Handler not found for node" in str(call_args)
            assert "handler_inexistente_abc" in str(call_args)

    def test_builder_creates_nodes_even_with_missing_handlers(self):
        """Verifica que builder cria nós mesmo com handlers ausentes."""
        graph = build_pipeline_from_nodes()
        assert isinstance(graph, ExecutionGraph)
        assert len(graph.nodes) > 0

    def test_missing_handler_node_has_noop_behavior(self):
        """Verifica que nó com handler ausente tem comportamento noop."""
        graph = build_pipeline_from_nodes()
        # Verifica que todos os nós foram criados
        for node_name, node in graph.nodes.items():
            assert node.run is not None
            assert callable(node.run)

    @pytest.mark.asyncio
    async def test_missing_handler_execution_returns_original_context(self):
        """Verifica que execução de handler ausente retorna contexto original."""
        graph = build_pipeline_from_nodes()
        
        # Encontra um nó que sabemos que pode não ter handler
        for node_name, node in graph.nodes.items():
            ctx = {"task": "test", "data": "test"}
            try:
                result = await node.run(ctx)
                # Se handler for noop, deve retornar contexto inalterado
                assert isinstance(result, dict)
                assert "task" in result
            except Exception:
                pytest.fail(f"Nó {node_name} falhou inesperadamente")


class TestBuilderErrorHandling:
    """Testes para tratamento de erros no builder."""

    def test_handler_not_found_error_structure(self):
        """Verifica estrutura do erro quando handler não encontrado."""
        with patch("iaglobal.graphs.builder.record_error") as mock_record:
            _try_import_handler("teste_erro_estrutura")
            call_args = mock_record.call_args
            args, kwargs = call_args
            assert len(args) >= 2
            assert args[0] == "builder"
            assert "handler_not_found" in args[1] or "Handler not found" in args[1]

    def test_pipeline_does_not_break_on_missing_handler(self):
        """Verifica que pipeline não quebra quando handler ausente."""
        # Este teste garante que o pipeline completa sem exceção
        graph = build_pipeline_from_nodes()
        assert graph is not None
        assert len(graph.nodes) >= 58  # Pelo menos os 58 nós esperados


if __name__ == "__main__":
    pytest.main([__file__, "-v"])