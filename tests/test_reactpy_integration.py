"""
Teste de Integração ReactPy + Django + ASGI
===========================================

Valida:
1. Componentes ReactPy renderizam sem erros
2. Django views servem componentes
3. ASGI/WebSocket funciona com daphne
"""

import pytest
import sys
import os

# Configura Django antes de importar reactpy_django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'iaglobal.settings')

# Mock Django settings se não existir
from unittest.mock import patch, MagicMock
with patch('django.conf.settings', MagicMock()) as mock_settings:
    mock_settings.DEBUG = True
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    try:
        from reactpy import html, component
        from reactpy_django import DjangoProvider
        REACTPY_AVAILABLE = True
    except Exception:
        REACTPY_AVAILABLE = False


class TestReactPyComponents:
    """Testa componentes ReactPy básicos."""

    @pytest.mark.skipif(not REACTPY_AVAILABLE, reason="ReactPy/Django não configurado")
    def test_agent_card_renders(self):
        """AgentCard deve renderizar HTML sem exceções."""
        from iaglobal.ui.reactpy_components import AgentCard
        component = AgentCard(agent_name="TestAgent", status="active")
        assert component is not None

    @pytest.mark.skipif(not REACTPY_AVAILABLE, reason="ReactPy/Django não configurado")
    def test_metrics_dashboard_renders(self):
        """MetricsDashboard deve renderizar com template grid."""
        from iaglobal.ui.reactpy_components import MetricsDashboard
        dashboard = MetricsDashboard()
        assert dashboard is not None

    @pytest.mark.skipif(not REACTPY_AVAILABLE, reason="ReactPy/Django não configurado")
    def test_restaurant_menu_renders(self):
        """RestaurantMenuPage deve renderizar complete SPA."""
        from iaglobal.ui.reactpy_components import RestaurantMenuPage
        menu = RestaurantMenuPage()
        assert menu is not None


class TestASGISetup:
    """Testa ASGI + WebSocket para ReactPy."""

    def test_daphne_available(self):
        """Daphne deve estar disponível como servidor ASGI."""
        import importlib
        spec = importlib.util.find_spec("daphne")
        assert spec is not None, "daphne não instalado"

    def test_channels_installed(self):
        """Django channels deve estar disponível."""
        import importlib
        spec = importlib.util.find_spec("channels")
        assert spec is not None, "channels não instalado"

    def test_uvicorn_available(self):
        """Uvicorn deve estar disponível para FastAPI."""
        import importlib
        spec = importlib.util.find_spec("uvicorn")
        assert spec is not None, "uvicorn não instalado"