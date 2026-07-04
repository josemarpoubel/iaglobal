# iaglobal/providers/task_router.py

from iaglobal.utils.logger import logger

TASK_PROVIDER_MAP = {
    "coding": "openrouter",
    "reflection": "ollama",
    "planning": "nvidia",
    "debug": "openrouter",
    "fast": "groq",
    "reasoning": "nvidia",
    "theming": "hf_router",
    "form_handling": "hf_router",
    "php": "hf_router",
    "web": "hf_router",
}

def detect_task_type(prompt: str) -> str:
    p = prompt.lower()

    task_type = "fast"

    if any(x in p for x in ["debug", "error", "trace"]):
        task_type = "debug"
    elif any(x in p for x in ["explain", "why", "reason"]):
        task_type = "reflection"
    elif any(x in p for x in ["plan", "architecture", "design"]):
        task_type = "planning"
    elif any(x in p for x in ["code", "function", "implement"]):
        task_type = "coding"

    logger.info("[TASK_ROUTER] detect_task_type=%s provider=%s", task_type, TASK_PROVIDER_MAP.get(task_type, "ollama"))
    return task_type
