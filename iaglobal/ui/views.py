"""
Views ReactPy para IAGLOBAL Dashboard
======================================
Integração Django + ReactPy para UI reativa dos agentes.
"""

import os
import logging

# Configure Django antes de importar reactpy_django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "iaglobal.settings")

import django

django.setup()

logger = logging.getLogger(__name__)

try:
    from reactpy_django import ReactPyView

    REACTPY_DJANGO_AVAILABLE = True
except ImportError:
    REACTPY_DJANGO_AVAILABLE = False

if REACTPY_DJANGO_AVAILABLE:
    from iaglobal.ui.reactpy_components import EntropyDashboard

    class EntropyDashboardView(ReactPyView):
        """View ReactPy para Dashboard de Entropia."""

        component = EntropyDashboard
        template_name = "reactpy_base.html"  # Template base do Django

    from iaglobal.ui.reactpy_components import MetricsDashboard, RestaurantMenuPage

    class DashboardView(ReactPyView):
        """View ReactPy para Dashboard de Agentes."""

        component = MetricsDashboard
        template_name = "reactpy_base.html"

    class RestaurantMenuView(ReactPyView):
        """View ReactPy para Menu do Restaurante."""

        component = RestaurantMenuPage
        template_name = "reactpy_base.html"

    def dashboard_view(request):
        """Wrapper Django view para dashboard."""
        return DashboardView.as_view()(request)

    def restaurant_menu_view(request):
        """Wrapper Django view para menu do restaurante."""
        return RestaurantMenuView.as_view()(request)
else:

    def dashboard_view(request):
        from django.http import HttpResponse

        return HttpResponse(
            "ReactPy Django não disponível. Instale: pip install reactpy-django",
            status=503,
        )

    def restaurant_menu_view(request):
        from django.http import HttpResponse

        return HttpResponse(
            "ReactPy Django não disponível. Instale: pip install reactpy-django",
            status=503,
        )
