# tests/test_darwin_harness.py
"""Testes do Darwin Harness de Estresse de Mutação."""
import asyncio
import pytest

from iaglobal.evolution.darwin_harness import DarwinHarness


class TestDarwinHarness:
    """Testes do harness evolutivo."""

    def test_generate_mutant_code(self):
        """Gera código mutante corretamente."""
        harness = DarwinHarness()
        
        injection = harness.generate_mutant_code("def run(): pass", "injection")
        assert "os.system" in injection
        
        loop = harness.generate_mutant_code("def run(): pass", "loop")
        assert "while" in loop

    def test_mutation_detection_injection(self):
        """Deve detectar mutação de injeção."""
        async def _run():
            harness = DarwinHarness()
            result = await harness.run_mutation_test("test_agent", "injection")
            assert result["detected"] is True
            return result
        asyncio.run(_run())

    def test_mutation_detection_loop(self):
        """Deve detectar mutação de loop."""
        async def _run():
            harness = DarwinHarness()
            result = await harness.run_mutation_test("test_agent", "loop")
            assert result["detected"] is True
            return result
        asyncio.run(_run())

    def test_adaptive_score(self):
        """Calcula adaptive score corretamente."""
        harness = DarwinHarness()
        
        # Sem testes ainda
        assert harness.get_adaptive_score() == 1.0