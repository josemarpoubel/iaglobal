# iaglobal/providers/provider_config.py

import logging
import os

logger = logging.getLogger("iaglobal.providers")


class _ConfigMeta(type):
    """Metaclass para acesso lazy a vars de ambiente via atributos de classe."""

    def __getattr__(cls, key):
        MAP = {
            "GROQ_API_KEY": ("GROQ_API_KEY", None),
            "GEMINI_API_KEY": ("GEMINI_API_KEY", None),
            "OPENROUTER_API_KEY": ("OPENROUTER_API_KEY", None),
            "NVIDIA_API_KEY": ("NVIDIA_API_KEY", None),
            "OPENCODE_API_KEY": ("OPENCODE_API_KEY", None),
            "DEFAULT_NVIDIA_MODEL": ("DEFAULT_NVIDIA_MODEL", "meta/llama-3.3-70b-instruct"),
            "HUGGINGFACE_API_KEY": ("HUGGINGFACE_API_KEY", None),
            "OLLAMA_URL": ("OLLAMA_URL", "http://localhost:11434"),
            "DEFAULT_OLLAMA_MODEL": ("DEFAULT_OLLAMA_MODEL", "qwen2.5:0.5b"),
            "DEFAULT_GROQ_MODEL": ("DEFAULT_GROQ_MODEL", "llama-3.1-8b-instant"),
            "DEFAULT_OPENROUTER_MODEL": (
                "DEFAULT_OPENROUTER_MODEL",
                "meta-llama/llama-3.1-8b-instruct",
            ),
        }
        if key in MAP:
            env_key, default = MAP[key]
            value = os.getenv(env_key, default)
            source = "env" if os.environ.get(env_key) is not None else "default"
            logger.debug("[CONFIG] %s=%s (source=%s, env_key=%s)", key, value[:30] if value else None, source, env_key)
            return value
        raise AttributeError(f"ProviderConfig has no attribute '{key}'")


class ProviderConfig(metaclass=_ConfigMeta):

    @classmethod
    def validate(cls):
        present = []
        missing = []
        for key in ["GROQ_API_KEY", "NVIDIA_API_KEY", "OPENROUTER_API_KEY", "OPENCODE_API_KEY"]:
            val = getattr(cls, key)
            if val:
                present.append(key)
            else:
                missing.append(key)
        logger.info("[CONFIG] API keys: %d present, %d missing", len(present), len(missing))
        logger.debug("[CONFIG] Keys present: %s", present)
        if missing:
            logger.warning("[CONFIG] Chaves ausentes: %s (modo local)", missing)

