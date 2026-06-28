"""
URLs principais de IAGLOBAL
"""
from django.urls import include, path

urlpatterns = [
    path("ui/", include("iaglobal.ui.urls")),
]