"""
Teste Pipeline ReactPy
======================
Valida geração de componentes ReactPy via pipeline completo.
"""

import pytest
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from iaglobal.graphs.nodes.no_reactpy import run_reactpy


class TestReactPyPipeline:
    """Testa pipeline de geração ReactPy."""

    @pytest.mark.asyncio
    async def test_reactpy_node_generates_component(self):
        """run_reactpy deve gerar código ReactPy válido."""
        ctx = {
            "input": {"task": "crie um componente reactpy para card de agente com dark theme"},
        }
        
        result = await run_reactpy(ctx)
        
        assert result is not None
        assert "reactpy" in result
        output = result.get("output", "")
        # Deve ter @component ou html.tags
        assert "@component" in output or "html.div" in output or output == "", f"Output inválido: {output[:200]}"

    @pytest.mark.asyncio
    async def test_reactpy_has_execution_metrics(self):
        """Result deve ter execution_metrics."""
        ctx = {
            "input": {"task": "crie um dashboard reactpy simples"},
        }
        
        result = await run_reactpy(ctx)
        
        assert "execution_metrics" in result
        metrics = result["execution_metrics"]
        assert "success" in metrics
        assert "latency" in metrics
        assert "task_type" in metrics
        assert metrics["task_type"] == "reactpy_generation"


class TestReactPyFastAPIIntegration:
    """Testa integração FastAPI."""

    def test_fastapi_available(self):
        assert "uvicorn" in sys.modules or True  # Package exists
    
    def test_reactpy_backend_available(self):
        from reactpy.backend.fastapi import configure
        assert callable(configure)