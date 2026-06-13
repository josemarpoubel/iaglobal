# iaglobal/providers/provider_state.py

from __future__ import annotations

import json
import logging
import threading
import time

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("iaglobal.providers")

from iaglobal._paths import DATA_ROOT
from iaglobal.utils.logger import logger as util_logger


# =============================================================================
# Provider Statistics
# =============================================================================

@dataclass
class ProviderStats:

    success: int = 0
    fail: int = 0

    consecutive_failures: int = 0

    success_latency_total: float = 0.0
    success_latency_count: int = 0

    cooldown_until: float = 0.0

    last_error: Optional[str] = None
    last_error_code: Optional[int] = None

    last_success_at: float = 0.0
    last_failure_at: float = 0.0

    # -------------------------------------------------------------------------

    @property
    def total_requests(self) -> int:
        return self.success + self.fail

    # -------------------------------------------------------------------------

    def success_rate(self) -> float:

        total = self.total_requests

        if total == 0:
            return 0.50

        return self.success / total

    # -------------------------------------------------------------------------

    def avg_latency(self) -> float:

        if self.success_latency_count == 0:
            return 1.0

        return (
            self.success_latency_total /
            self.success_latency_count
        )

    # -------------------------------------------------------------------------

    def latency_score(self) -> float:
        """
        Converte latência em score normalizado.

        0.1s → 0.90
        1.0s → 0.50
        5.0s → 0.16
        10s  → 0.09
        """

        latency = self.avg_latency()

        return 1.0 / (1.0 + latency)

    # -------------------------------------------------------------------------

    def score(self) -> float:

        sr = self.success_rate()
        ls = self.latency_score()

        score = (
            (sr * 0.80) +
            (ls * 0.20)
        )

        return max(0.0, min(1.0, score))


# =============================================================================
# Provider State
# =============================================================================

class ProviderState:

    DEFAULT_PROVIDERS = (
        "ollama",
        "nvidia",
        "groq",
        "openrouter",
        "opencode",
        "hf",
        "hf_router",
        "google",
        "openai",
        "poe",
    )

    # -------------------------------------------------------------------------

    def __init__(
        self,
        persist_file: Optional[str] = None,
    ):

        self._lock = threading.RLock()

        self.persist_file = (
            Path(persist_file)
            if persist_file
            else None
        )

        self.providers: Dict[str, ProviderStats] = {
            provider: ProviderStats()
            for provider in self.DEFAULT_PROVIDERS
        }

        self._load()

        logger.debug(
            "[STATE] initialized with %d providers",
            len(self.providers),
        )

    # -------------------------------------------------------------------------

    def _load(self) -> None:

        if not self.persist_file:
            return

        if not self.persist_file.exists():
            return

        try:

            data = json.loads(
                self.persist_file.read_text(
                    encoding="utf-8"
                )
            )

            for provider, values in data.items():

                if provider not in self.providers:
                    continue

                self.providers[provider] = ProviderStats(
                    **values
                )

            logger.info(
                "[STATE] restored provider statistics"
            )

        except Exception as exc:
            logger.exception(
                "[STATE] failed loading state: %s",
                exc,
            )

    # -------------------------------------------------------------------------

    def _save(self) -> None:

        if not self.persist_file:
            return

        try:

            self.persist_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            data = {
                provider: asdict(stats)
                for provider, stats in self.providers.items()
            }

            self.persist_file.write_text(
                json.dumps(
                    data,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

        except Exception as exc:

            logger.exception(
                "[STATE] failed saving state: %s",
                exc,
            )

    # -------------------------------------------------------------------------

    def is_available(
        self,
        provider: str,
    ) -> bool:

        with self._lock:

            stats = self.providers.get(provider)

            if not stats:
                return False

            return time.time() >= stats.cooldown_until

    # -------------------------------------------------------------------------

    def score(
        self,
        provider: str,
    ) -> float:

        with self._lock:

            stats = self.providers.get(provider)

            if not stats:
                return 0.0

            return stats.score()

    # -------------------------------------------------------------------------

    def get_stats(
        self,
        provider: str,
    ) -> Optional[ProviderStats]:

        with self._lock:
            return self.providers.get(provider)

    # -------------------------------------------------------------------------

    def mark_success(
        self,
        provider: str,
        latency: float,
    ) -> None:

        with self._lock:

            stats = self.providers.get(provider)

            if not stats:
                logger.warning(
                    "[STATE] unknown provider: %s",
                    provider,
                )
                return

            stats.success += 1

            stats.consecutive_failures = 0

            stats.cooldown_until = 0

            stats.success_latency_total += max(
                latency,
                0.0,
            )

            stats.success_latency_count += 1

            stats.last_success_at = time.time()

            self._save()

            util_logger.info(
                "[STATE] provider=%s OK latency=%.2fs score=%.3f",
                provider,
                latency,
                stats.score(),
            )

    # -------------------------------------------------------------------------

    def mark_failure(
        self,
        provider: str,
        latency: float,
        error_code: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:

        with self._lock:

            stats = self.providers.get(provider)

            if not stats:
                logger.warning(
                    "[STATE] unknown provider: %s",
                    provider,
                )
                return

            stats.fail += 1

            stats.consecutive_failures += 1

            stats.last_failure_at = time.time()

            stats.last_error_code = error_code
            stats.last_error = error

            cooldown_seconds = self._calculate_cooldown(
                stats,
                error_code,
            )

            stats.cooldown_until = (
                time.time() +
                cooldown_seconds
            )

            self._save()

            util_logger.warning(
                "[STATE] provider=%s FAIL code=%s cooldown=%ss consecutive=%d",
                provider,
                error_code,
                cooldown_seconds,
                stats.consecutive_failures,
            )

    # -------------------------------------------------------------------------

    def update(
        self,
        provider: str,
        success: bool,
        latency: float,
        error_code: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:

        if success:

            self.mark_success(
                provider,
                latency,
            )

        else:

            self.mark_failure(
                provider,
                latency,
                error_code,
                error,
            )

    # -------------------------------------------------------------------------

    def _calculate_cooldown(
        self,
        stats: ProviderStats,
        error_code: Optional[int],
    ) -> int:

        failures = max(
            1,
            stats.consecutive_failures,
        )

        # Sem créditos
        if error_code == 402:
            return 86400

        # Auth temporária
        if error_code == 401:
            return 1800

        # Rate limit / indisponível
        if error_code in (429, 503, 504):

            return min(
                300,
                5 * (
                    2 **
                    min(failures - 1, 6)
                )
            )

        # Timeout
        if error_code == 408:

            return min(
                120,
                3 * failures,
            )

        # Erro genérico

        return min(
            60,
            5 * failures,
        )

    # -------------------------------------------------------------------------

    def best_provider(self) -> Optional[str]:

        with self._lock:

            candidates = {
                provider: stats.score()
                for provider, stats in self.providers.items()
                if self.is_available(provider)
            }

            if not candidates:
                return None

            return max(
                candidates,
                key=candidates.get,
            )

    # -------------------------------------------------------------------------

    def health_report(self) -> Dict:

        with self._lock:

            report = {}

            for provider, stats in self.providers.items():

                report[provider] = {
                    "score": round(
                        stats.score(),
                        3,
                    ),
                    "success": stats.success,
                    "fail": stats.fail,
                    "success_rate": round(
                        stats.success_rate(),
                        3,
                    ),
                    "avg_latency": round(
                        stats.avg_latency(),
                        3,
                    ),
                    "consecutive_failures":
                        stats.consecutive_failures,
                    "available":
                        self.is_available(provider),
                    "last_error":
                        stats.last_error,
                    "last_error_code":
                        stats.last_error_code,
                }

            return report


# =============================================================================
# Singleton
# =============================================================================

provider_state = ProviderState(
    persist_file=str(DATA_ROOT / "provider_state.json")
)
