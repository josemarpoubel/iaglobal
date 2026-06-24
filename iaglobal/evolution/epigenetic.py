"""Epigenetic Config - Dynamic feature flagging for runtime reconfiguration."""

import os
import json
import threading
import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_FLAGS = {
    "evolve_knowledge": True,
    "evolve_methylation": True,
    "auto_correction": True,
    "loop_detection": True,
    "homeostasis_enforcement": True,
    "glutathione_validation": True,
    "max_iterations": 5,
    "sam_budget_multiplier": 1.0,
    "bandit_epsilon": 0.2,
}

# Thread-safe in-memory flags
_flags_lock = threading.Lock()
_memory_flags: Dict[str, Any] = DEFAULT_FLAGS.copy()


def get_flag(key: str, default: Any = None) -> Any:
    """Get a flag value from memory."""
    with _flags_lock:
        return _memory_flags.get(key, default)


def is_flag_enabled(key: str) -> bool:
    """Check if a boolean flag is enabled."""
    return bool(get_flag(key, False))


def set_flag(key: str, value: Any) -> None:
    """Set a flag value in memory (thread-safe)."""
    with _flags_lock:
        _memory_flags[key] = value


def all_memory_flags() -> Dict[str, Any]:
    """Return copy of all in-memory flags."""
    with _flags_lock:
        return _memory_flags.copy()


def adapt_bandit_policy() -> Dict[str, Any]:
    """
    Apply epigenetic flags to BanditPolicy configuration.
    
    Returns adjustments to apply to the bandit.
    """
    adjustments = {}
    
    # Adapt epsilon for exploration/exploitation
    if "bandit_epsilon" in all_memory_flags():
        adjustments["epsilon"] = get_flag("bandit_epsilon")
        logger.info(f"[EPIGENETIC-BANDIT] Epsilon adapted to {adjustments['epsilon']}")
    
    # Adapt SAM budget if specified
    if "sam_budget_multiplier" in all_memory_flags():
        adjustments["sam_budget_multiplier"] = get_flag("sam_budget_multiplier")
        logger.info(f"[EPIGENETIC-BANDIT] SAM budget multiplier: {adjustments['sam_budget_multiplier']}")
    
    return adjustments


def get_max_iterations() -> int:
    """Get max iterations for reflexion loops from epigenetic config."""
    return int(get_flag("max_iterations", DEFAULT_FLAGS["max_iterations"]))