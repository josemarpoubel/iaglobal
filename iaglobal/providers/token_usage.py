# iaglobal/providers/token_usage.py
"""Token usage tracking for provider responses."""

from typing import Callable, Dict, Any, Optional, Tuple

# Type for the token collector callback
# Called with (prompt_tokens, completion_tokens)
TokenCollector = Callable[[int, int], None]

# Sentinel type
_Unset = type("_Unset", (), {"__bool__": lambda self: False})()


def extract_usage(data: dict, provider: str) -> Tuple[int, int, int]:
    """Extract (prompt_tokens, completion_tokens, total_tokens) from API response.

    Supports OpenAI-compatible format and Gemini format.
    """
    usage = data.get("usage")
    if isinstance(usage, dict):
        pt = usage.get("prompt_tokens", 0) or 0
        ct = usage.get("completion_tokens", 0) or 0
        tt = usage.get("total_tokens", 0) or (pt + ct)
        return pt, ct, tt

    # Gemini format
    meta = data.get("usageMetadata")
    if isinstance(meta, dict):
        pt = meta.get("promptTokenCount", 0) or 0
        ct = meta.get("candidatesTokenCount", 0) or 0
        tt = meta.get("totalTokenCount", 0) or (pt + ct)
        return pt, ct, tt

    return 0, 0, 0
