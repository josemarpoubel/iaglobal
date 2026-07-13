"""
URLs para views ReactPy de IAGLOBAL
"""

from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard_view, name="iaglobal_dashboard"),
    path("restaurant/", views.restaurant_menu_view, name="iaglobal_restaurant_menu"),
    path(
        "entropy/",
        views.EntropyDashboardView.as_view(),
        name="iaglobal_entropy_dashboard",
    ),
]
