"""
Django settings mínimos para IAGLOBAL ReactPy
==============================================
Usado quando Django não está configurado externamente.
"""

SECRET_KEY = "iaglobal-dev-secret-key-change-in-production"

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "channels",
    "iaglobal",
]

# Channels config
ASGI_APPLICATION = "iaglobal.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Database mínima
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "/home/kitohamachi/projeto-iaglobal/iaglobal/memory/data/db/django_meta.db",
    }
}

# Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "iaglobal.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
        ]},
    }
]