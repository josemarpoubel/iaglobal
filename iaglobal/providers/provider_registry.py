from iaglobal.providers.ollama_provider import generate as ollama
from iaglobal.providers.groq_provider import generate as groq
from iaglobal.providers.nvidia_provider import generate as nvidia
from iaglobal.providers.openrouter_provider import generate as openrouter
from iaglobal.providers.opencode_provider import generate as opencode

PROVIDERS = {
    "ollama": ollama,
    "groq": groq,
    "nvidia": nvidia,
    "openrouter": openrouter,
    "opencode": opencode,
}
