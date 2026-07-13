# iaglobal/providers/provider_registry.py

from iaglobal.providers.groq_provider import generate as groq
from iaglobal.providers.gemini_provider import generate as google
from iaglobal.providers.nvidia_provider import generate as nvidia
from iaglobal.providers.openrouter_provider import generate as openrouter
from iaglobal.providers.hf_router_provider import async_generate as hf
from iaglobal.providers.opencode_provider import generate as opencode
from iaglobal.providers.openai_provider import generate as openai
from iaglobal.providers.ollama_provider import generate as ollama
from iaglobal.providers.poe_provider import generate as poe

from iaglobal.utils.logger import logger

PROVIDERS = {
    "groq": groq,
    "google": google,
    "nvidia": nvidia,
    "openrouter": openrouter,
    "hf": hf,
    "opencode": opencode,
    "openai": openai,
    "poe": poe,
    "ollama": ollama,
}

logger.info("[REGISTRY] PROVIDERS loaded: %s", list(PROVIDERS.keys()))
