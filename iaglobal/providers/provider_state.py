# iaglobal/providers/provider_state.py

import logging
import time
from dataclasses import dataclass, field
from typing import Dict

logger = logging.getLogger("iaglobal.providers")


@dataclass
class ProviderStats:
    success: int = 0
    fail: int = 0
    total_latency: float = 0.0
    cooldown_until: float = 0.0

    def success_rate(self):
        total = self.success + self.fail
        result = self.success / total if total > 0 else 0.5
        logger.debug("[STATE] %s success_rate=%d/%d=%.3f",
                     id(self), self.success, total if total > 0 else 0, result)
        return result

    def avg_latency(self):
        total = self.success + self.fail
        result = self.total_latency / total if total > 0 else 1.0
        logger.debug("[STATE] %s avg_latency=%.2f/%d=%.3f",
                     id(self), self.total_latency, total if total > 0 else 0, result)
        return result


class ProviderState:

    def __init__(self):
        self.providers: Dict[str, ProviderStats] = {
            "ollama": ProviderStats(),
            "nvidia": ProviderStats(),
            "groq": ProviderStats(),
            "openrouter": ProviderStats(),
            "opencode": ProviderStats(),
        }
        logger.debug("[STATE] ProviderState init: %d providers", len(self.providers))

    def is_available(self, provider: str) -> bool:
        stats = self.providers.get(provider)
        if not stats:
            logger.debug("[STATE] is_available(%s) -> False (not found)", provider)
            return False

        now = time.time()
        available = now > stats.cooldown_until
        if not available:
            logger.debug("[STATE] is_available(%s) -> False (cooldown until %.1f, now=%.1f)",
                         provider, stats.cooldown_until, now)
        return available

    def score(self, provider: str) -> float:
        stats = self.providers.get(provider)
        if not stats:
            logger.debug("[STATE] score(%s) -> 0.5 (not found)", provider)
            return 0.5

        sr = stats.success_rate()
        al = stats.avg_latency()
        result = sr * 0.7 - al * 0.2
        logger.debug("[STATE] score(%s)=%.3f (sr=%.3f*0.7 - al=%.3f*0.2)",
                     provider, result, sr, al)
        return result

    def update(self, provider: str, success: bool, latency: float):
        if provider not in self.providers:
            self.providers[provider] = ProviderStats()
            logger.debug("[STATE] update(%s) -> novo provider registrado", provider)

        stats = self.providers[provider]

        if success:
            stats.success += 1
        else:
            stats.fail += 1

        stats.total_latency += latency

        if not success:
            stats.cooldown_until = time.time() + 5
            logger.debug("[STATE] update(%s) FAIL -> cooldown until %.1f (success=%d fail=%d)",
                         provider, stats.cooldown_until, stats.success, stats.fail)
        else:
            logger.debug("[STATE] update(%s) OK latency=%.2f (success=%d fail=%d total_lat=%.2f)",
                         provider, latency, stats.success, stats.fail, stats.total_latency)
