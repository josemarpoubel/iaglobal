# iaglobal/providers/task_router.py

TASK_PROVIDER_MAP = {
    "coding": "openrouter",
    "reflection": "ollama",
    "planning": "nvidia",
    "debug": "openrouter",
    "fast": "groq"
}

def detect_task_type(prompt: str) -> str:
    p = prompt.lower()

    if any(x in p for x in ["debug", "error", "trace"]):
        return "debug"

    if any(x in p for x in ["explain", "why", "reason"]):
        return "reflection"

    if any(x in p for x in ["plan", "architecture", "design"]):
        return "planning"

    if any(x in p for x in ["code", "function", "implement"]):
        return "coding"

    return "fast"
