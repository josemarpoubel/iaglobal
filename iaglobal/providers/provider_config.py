# iaglobal/providers/provider_config.py

import logging
import os
from enum import Enum

from iaglobal.core.env_loader import load_env

load_env()

logger = logging.getLogger("iaglobal.providers")


class CognitiveRole(Enum):
    """Papéis cognitivos dos modelos locais — diferenciação celular aplicada à IA."""

    JUIZ = "juiz"
    OPERARIO = "operario"
    SENTINELA = "sentinela"


# Mapa de capacidades metabólicas por papel cognitivo.
# Cada entrada define os limites energéticos (concorrência, tokens, timeout)
# e a rota de degradação graciosa (fallback_role).
COGNITIVE_MODELS = {
    CognitiveRole.JUIZ: {
        "model_id": "yasserrmd/GLM4.7-Distill-LFM2.5-1.2B:latest",
        "type": "ollama",
        "max_concurrent_requests": 1,
        "tokens_per_minute_limit": 4096,
        "priority_score": 1.0,
        "fallback_role": CognitiveRole.OPERARIO,
        "timeout_seconds": 120,
    },
    CognitiveRole.OPERARIO: {
        "model_id": "qwen2.5:0.5b",
        "type": "ollama",
        "max_concurrent_requests": 3,
        "tokens_per_minute_limit": 8192,
        "priority_score": 0.5,
        "fallback_role": None,
        "timeout_seconds": 60,
    },
    CognitiveRole.SENTINELA: {
        "model_id": "oamazonasgabriel/lfm2.5-230m:bf16-8gbRAM",
        "type": "ollama",
        "max_concurrent_requests": 5,
        "tokens_per_minute_limit": 15000,
        "priority_score": 0.8,
        "fallback_role": None,
        "timeout_seconds": 30,
    },
}


def get_model_config(role: CognitiveRole) -> dict:
    """Retorna a configuração metabólica para um papel cognitivo."""
    return COGNITIVE_MODELS.get(role)


def get_all_active_models() -> list:
    """Retorna a lista de todos os model_ids dos papéis cognitivos ativos."""
    return [config["model_id"] for config in COGNITIVE_MODELS.values()]


def get_role_by_model_id(model_id: str) -> CognitiveRole | None:
    """Retorna o papel cognitivo de um model_id, ou None se não encontrado."""
    for role, config in COGNITIVE_MODELS.items():
        if config["model_id"] == model_id:
            return role
    return None


_ENV_CACHE: dict = {}
_MAP = {
    "GROQ_API_KEY": ("GROQ_API_KEY", None),
    "GEMINI_API_KEY": ("GEMINI_API_KEY", None),
    "GOOGLE_API_KEY": ("GOOGLE_API_KEY", None),
    "MISTRAL_API_KEY": ("MISTRAL_API_KEY", None),
    "PERPLEXITY_API_KEY": ("PERPLEXITY_API_KEY", None),
    "OPENROUTER_API_KEY": ("OPENROUTER_API_KEY", None),
    "NVIDIA_API_KEY": ("NVIDIA_API_KEY", None),
    "OPENCODE_API_KEY": ("OPENCODE_API_KEY", None),
    "HUGGINGFACE_API_KEY": ("HUGGINGFACE_API_KEY", None),
    "OPENAI_API_KEY": ("OPENAI_API_KEY", None),
    "BRAVE_API_KEY": ("BRAVE_API_KEY", None),
    "TAVILY_API_KEY": ("TAVILY_API_KEY", None),
    "SERP_API_KEY": ("SERP_API_KEY", None),
    "EXA_API_KEY": ("EXA_API_KEY", None),
    "POE_API_KEY": ("POE_API_KEY", None),
    "OLLAMA_URL": ("OLLAMA_URL", "http://localhost:11434"),
    "DEFAULT_NVIDIA_MODEL": ("DEFAULT_NVIDIA_MODEL", None),
    "DEFAULT_OLLAMA_MODEL": ("DEFAULT_OLLAMA_MODEL", None),
    "DEFAULT_GROQ_MODEL": ("DEFAULT_GROQ_MODEL", None),
    "DEFAULT_OPENROUTER_MODEL": ("DEFAULT_OPENROUTER_MODEL", None),
    "DEFAULT_MISTRAL_MODEL": ("DEFAULT_MISTRAL_MODEL", None),
    "DEFAULT_GEMINI_MODEL": ("DEFAULT_GEMINI_MODEL", None),
    "SEARXNG_URL": ("SEARXNG_URL", "http://localhost:4000"),
}


class _ConfigMeta(type):
    """Metaclass para acesso lazy e cacheado a vars de ambiente."""

    def __getattr__(cls, key):
        if key in _ENV_CACHE:
            return _ENV_CACHE[key]

        entry = _MAP.get(key)
        if entry is None:
            raise AttributeError(f"ProviderConfig has no attribute '{key}'")

        env_key, default = entry
        value = os.getenv(env_key, default)
        source = "env" if os.environ.get(env_key) is not None else "default"
        _ENV_CACHE[key] = value

        logger.debug("[CONFIG] %s=*** (source=%s)", key, source)

        return value


class ProviderConfig(metaclass=_ConfigMeta):
    COGNITIVE_MODELS = COGNITIVE_MODELS
    CognitiveRole = CognitiveRole

    @classmethod
    def get_model_config(cls, role: CognitiveRole) -> dict | None:
        return get_model_config(role)

    @classmethod
    def get_all_active_models(cls) -> list:
        return get_all_active_models()

    @classmethod
    def get_role_by_model_id(cls, model_id: str) -> CognitiveRole | None:
        return get_role_by_model_id(model_id)

    @classmethod
    def validate(cls):
        present = []
        missing = []
        for key in [
            "GROQ_API_KEY",
            "NVIDIA_API_KEY",
            "OPENROUTER_API_KEY",
            "OPENCODE_API_KEY",
        ]:
            val = getattr(cls, key)
            if val:
                present.append(key)
            else:
                missing.append(key)
        logger.info(
            "[CONFIG] validate called: %d present, %d missing",
            len(present),
            len(missing),
        )
        logger.info(
            "[CONFIG] API keys: %d present, %d missing", len(present), len(missing)
        )
        if present:
            logger.info("[CONFIG] Keys present: %s", present)
        logger.debug("[CONFIG] Keys present: %s", present)
        if missing:
            logger.warning("[CONFIG] Chaves ausentes: %s (modo local)", missing)
