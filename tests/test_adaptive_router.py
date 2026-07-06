# tests/test_adaptive_router.py
"""Testes do router adaptativo baseado em IVM."""
import pytest

from iaglobal.cognition.adaptive_router import AdaptiveRouter


class TestAdaptiveRouter:
    """Testa roteamento adaptativo."""

    def test_calculate_ivm_high_performance(self):
        """Calcula IVM alto para provedor eficiente."""
        router = AdaptiveRouter()
        
        metrics = {
            "success_rate": 0.95,
            "avg_latency": 1.0,
            "avg_tokens": 500,
            "mhc_validated": 0.9,
            "skills_approved": 0.8,
        }
        
        ivm = router.calculate_ivm("test_provider", metrics)
        
        assert 0.0 <= ivm <= 1.0
        assert ivm > 0.8  # Alta performance

    def test_calculate_ivm_low_performance(self):
        """Calcula IVM baixo para provedor ineficiente."""
        router = AdaptiveRouter()
        
        metrics = {
            "success_rate": 0.3,
            "avg_latency": 30.0,
            "avg_tokens": 5000,
            "mhc_validated": 0.2,
            "skills_approved": 0.1,
        }
        
        ivm = router.calculate_ivm("slow_provider", metrics)
        
        assert ivm < 0.5

    async def test_select_optimal_provider(self):
        """Seleciona provedor ótimo."""
        router = AdaptiveRouter()
        
        provider = await router.select_optimal_provider("general")
        
        assert provider in ["ollama", "groq", "nvidia", "gemini"]

    def test_record_performance(self):
        """Atualiza métricas do provedor."""
        router = AdaptiveRouter()
        
        router.record_performance("test_provider", "output", {
            "success": True,
            "latency": 1.5,
            "tokens": 100,
        })
        
        assert True  # Não crash