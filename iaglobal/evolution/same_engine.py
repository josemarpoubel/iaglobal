# iaglobal/evolution/same_engine.py

"""
SAMe Engine — Evolução com orçamento limitado por agente com segurança concorrente (Thread-Safe).
"""

import os
import json
import time
import threading
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict

from iaglobal._paths import SAME_POOL_FILE
from iaglobal.utils.logger import logger
from iaglobal.utils.atomic_io import AtomicJSONStore

POOL_FILE = SAME_POOL_FILE

DEFAULT_BUDGET = int(os.getenv("SAME_DEFAULT_BUDGET", "100"))
RECHARGE_RATE = int(os.getenv("SAME_RECHARGE_RATE", "10"))
INHIBIT_THRESHOLD = int(os.getenv("SAME_INHIBIT_THRESHOLD", "20"))

COST_CREATE_SKILL = 10
COST_FINE_TUNE = 20
COST_CREATE_AGENT = 50
COST_MERGE_SKILLS = 30


@dataclass
class SAMeAccount:
    agent_name: str
    balance: int = DEFAULT_BUDGET
    total_earned: int = 0
    total_spent: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SAMePool:
    """Pool de SAMe — recurso escasso para mutações evolutivas (Thread-Safe)."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or POOL_FILE
        self.accounts: Dict[str, SAMeAccount] = {}
        self._io_lock = threading.Lock()
        self._store = AtomicJSONStore(self.path, default=[])
        self._load()

    def _load(self):
        with self._io_lock:
            try:
                data = self._store.read_sync()
                if isinstance(data, list):
                    for item in data:
                        acc = SAMeAccount(**item)
                        self.accounts[acc.agent_name] = acc
            except json.JSONDecodeError:
                logger.error(
                    "[SAME] Arquivo de pool corrompido. Reinicializando banco local."
                )
            except Exception as e:
                logger.debug("[SAME] Erro ao carregar: %s", e)

    def get_account(self, agent_name: str) -> SAMeAccount:
        with self._io_lock:
            if agent_name not in self.accounts:
                self.accounts[agent_name] = SAMeAccount(agent_name=agent_name)
                self._store.mutate_sync(
                    lambda _: [a.to_dict() for a in self.accounts.values()]
                )
            return self.accounts[agent_name]

    def can_afford(self, agent_name: str, cost: int) -> bool:
        acc = self.get_account(agent_name)
        return acc.balance >= cost

    def spend(self, agent_name: str, cost: int) -> bool:
        with self._io_lock:
            if agent_name not in self.accounts:
                self.accounts[agent_name] = SAMeAccount(agent_name=agent_name)
            acc = self.accounts[agent_name]
            if acc.balance < cost:
                return False
            acc.balance -= cost
            acc.total_spent += cost
            self._store.mutate_sync(
                lambda _: [a.to_dict() for a in self.accounts.values()]
            )
            return True

    def recharge(self, agent_name: str, amount: int = RECHARGE_RATE):
        with self._io_lock:
            if agent_name not in self.accounts:
                self.accounts[agent_name] = SAMeAccount(agent_name=agent_name)
            acc = self.accounts[agent_name]
            acc.balance += amount
            acc.total_earned += amount
            self._store.mutate_sync(
                lambda _: [a.to_dict() for a in self.accounts.values()]
            )

    def balance(self, agent_name: str) -> int:
        return self.get_account(agent_name).balance


class MethylationInhibitor:
    """Inibe mutações não-críticas quando SAMe está baixo."""

    def __init__(self, pool: SAMePool, threshold: int = INHIBIT_THRESHOLD):
        self.pool = pool
        self.threshold = threshold

    def can_mutate(self, agent_name: str, cost: int, critical: bool = False) -> bool:
        if critical:
            return self.pool.can_afford(agent_name, cost)

        current_balance = self.pool.balance(agent_name)
        if current_balance < self.threshold:
            logger.info(
                "[SAME-INHIBITOR] SAMe baixo (%d < %d) — mutação não-crítica bloqueada para '%s'",
                current_balance,
                self.threshold,
                agent_name,
            )
            return False
        return self.pool.can_afford(agent_name, cost)


class SAMeBudgetTracker:
    """Controla orçamento por ciclo evolutivo (janela de 24h) com proteção atômica."""

    CYCLE_BUDGET = int(os.getenv("SAME_CYCLE_BUDGET", "100"))
    CYCLE_WINDOW = int(os.getenv("SAME_CYCLE_WINDOW", "86400"))

    def __init__(self, pool: SAMePool):
        self.pool = pool
        self._cycle_start: Dict[str, float] = {}
        self._cycle_spent: Dict[str, int] = {}
        self._tracker_lock = threading.Lock()

    def _check_cycle(self, agent_name: str):
        now = time.time()
        if (
            agent_name not in self._cycle_start
            or (now - self._cycle_start[agent_name]) > self.CYCLE_WINDOW
        ):
            self._cycle_start[agent_name] = now
            self._cycle_spent[agent_name] = 0

    def spend(self, agent_name: str, cost: int) -> bool:
        with self._tracker_lock:
            self._check_cycle(agent_name)
            if self._cycle_spent.get(agent_name, 0) + cost > self.CYCLE_BUDGET:
                return False
            self._cycle_spent[agent_name] = self._cycle_spent.get(agent_name, 0) + cost
            return True


def rewrite_prompt(
    agent_name: str, current_prompt: str, error_history: str = ""
) -> Optional[str]:
    """Reescreve prompt de um agente consumindo SAMe de forma defensiva."""
    if not same_pool.spend(agent_name, COST_FINE_TUNE):
        logger.warning(
            "[SAME-MUTATE] SAMe insuficiente para rewrite_prompt em '%s'", agent_name
        )
        return None

    # RESOLUÇÃO DO BUG 2: Protege contra injeções cegas de strings que quebram o .format do run_fn_factory
    sanitized_history = error_history.replace("{", "[[").replace("}", "]]")

    improved = (
        f"{current_prompt}\n\n[CONTEXTO DE APRENDIZADO]\n{sanitized_history[:500]}"
    )
    logger.info(
        "[SAME-MUTATE] rewrite_prompt: '%s' — prompt melhorado (+%d chars)",
        agent_name,
        len(sanitized_history[:500]),
    )
    return improved


# Instâncias globais coordenadas
same_pool = SAMePool()
same_inhibitor = MethylationInhibitor(same_pool)
same_budget = SAMeBudgetTracker(same_pool)
