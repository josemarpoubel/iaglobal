"""
Views ReactPy para IAGLOBAL Dashboard
======================================
Integração Django + ReactPy para UI reativa dos agentes.
"""

import os
import logging

# Configure Django antes de importar reactpy_django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'iaglobal.settings')

import django
django.setup()

logger = logging.getLogger(__name__)

try:
    from reactpy_django import ReactPyView
    REACTPY_DJANGO_AVAILABLE = True
except ImportError:
    REACTPY_DJANGO_AVAILABLE = False


