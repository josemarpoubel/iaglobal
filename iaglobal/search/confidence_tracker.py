# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ConfidenceTracker — Rastreia confiança por agente + tarefa para evitar buscas desnecessárias.

Funcionalidades:
1. should_search(agent_id, task_hash) → True se confiança < threshold
2. record_search_outcome(agent_id, task_hash, helped) → feedback pós-busca
3. adjust_threshold(agent_id, delta) → ajusta threshold dinamicamente
4. get_confidence(agent_id, task_hash) → retorna confiança atual

Integra com:
- SearchMiddleware (check antes de buscar)
- CreditAssignmentEngine (registro de outcome)
- BanditPolicy (ajuste de threshold)
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from iaglobal._paths import JSON_DIR
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.search.confidence_tracker")


@dataclass
class AgentConfidence:
    """Confiança de um agente para uma tarefa específica."""
    agent_id: str
    task_hash: str
    confidence: float  # 0.0 - 1.0
    last_updated: float
    search_count: int = 0  # quantas vezes buscou para esta tarefa
    search_helped: Optional[bool] = None  # feedback da última busca
    threshold: float = 0.8  # threshold atual para este agente

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfidenceTracker:
    """Rastreia confiança por agente + tarefa para otimizar buscas."""

    def __init__(self, default_threshold: float = 0.8):
        self._confidence_cache: Dict[str, AgentConfidence] = {}
        self._default_threshold = default_threshold
        self._persistence_file = JSON_DIR / "search_confidence.json"
        self._load()

    def _task_key(self, agent_id: str, task_hash: str) -> str:
        """Gera chave única para agente + tarefa."""
        return f"{agent_id}:{task_hash}"

    def should_search(self, agent_id: str, task_hash: str, threshold: Optional[float] = None) -> bool:
        """
        Retorna True se confiança < threshold (deve buscar).

        Args:
            agent_id: ID do agente (ex: "coder", "debugger")
            task_hash: Hash da tarefa (ex: sha3_512(prompt)[:16])
            threshold: Threshold override (opcional, usa default se None)

        Returns:
            True se deve buscar, False se confiança já é alta
        """
        key = self._task_key(agent_id, task_hash)
        effective_threshold = threshold if threshold is not None else self._default_threshold

        if key not in self._confidence_cache:
            # Primeira vez: não tem histórico → buscar
            logger.debug("[CONF] %s: primeira vez → buscar", agent_id)
            return True

        conf = self._confidence_cache[key]
        should = conf.confidence < effective_threshold

        logger.debug(
            "[CONF] %s: confidence=%.2f, threshold=%.2f → %s",
            agent_id, conf.confidence, effective_threshold,
            "buscar" if should else "skip"
        )

        return should

    def record_confidence(self, agent_id: str, task_hash: str, confidence: float, search_helped: Optional[bool] = None):
        """
        Registra confiança de agente para tarefa.

        Args:
            agent_id: ID do agente
            task_hash: Hash da tarefa
            confidence: Confiança (0.0 - 1.0)
            search_helped: Se busca ajudou (opcional)
        """
        key = self._task_key(agent_id, task_hash)

        if key in self._confidence_cache:
            conf = self._confidence_cache[key]
            conf.confidence = confidence
            conf.last_updated = time.time()
            if search_helped is not None:
                conf.search_helped = search_helped
                if search_helped:
                    conf.search_count += 1
        else:
            conf = AgentConfidence(
                agent_id=agent_id,
                task_hash=task_hash,
                confidence=confidence,
                last_updated=time.time(),
                search_helped=search_helped,
                search_count=1 if search_helped else 0,
                threshold=self._default_threshold,
            )
            self._confidence_cache[key] = conf

        logger.info(
            "[CONF] %s: confidence=%.2f, search_helped=%s",
            agent_id, confidence, search_helped
        )

        # Persistir a cada 10 registros
        if len(self._confidence_cache) % 10 == 0:
            self._save()

    def record_search_outcome(self, agent_id: str, task_hash: str, helped: bool):
        """
        Registra outcome de busca (feedback loop).

        Args:
            agent_id: ID do agente
            task_hash: Hash da tarefa
            helped: True se busca ajudou, False se atrapalhou
        """
        key = self._task_key(agent_id, task_hash)

        if key in self._confidence_cache:
            conf = self._confidence_cache[key]
            conf.search_helped = helped

            # Ajustar confiança baseado no outcome
            if helped:
                # Busca ajudou → aumentar confiança
                conf.confidence = min(1.0, conf.confidence + 0.1)
                logger.info("[CONF] %s: busca ajudou → confidence=%.2f", agent_id, conf.confidence)
            else:
                # Busca atrapalhou → diminuir confiança
                conf.confidence = max(0.0, conf.confidence - 0.15)
                logger.info("[CONF] %s: busca atrapalhou → confidence=%.2f", agent_id, conf.confidence)

            self._save()
        else:
            logger.debug("[CONF] %s: task não encontrada para outcome", agent_id)

    def adjust_threshold(self, agent_id: str, delta: float):
        """
        Ajusta threshold dinamicamente para um agente.

        Args:
            agent_id: ID do agente
            delta: Variação (+0.05 para aumentar, -0.05 para diminuir)
        """
        # Ajustar threshold global do agente (todas as tarefas)
        for key, conf in self._confidence_cache.items():
            if conf.agent_id == agent_id:
                conf.threshold = max(0.5, min(1.0, conf.threshold + delta))
                logger.info(
                    "[CONF] %s: threshold ajustado para %.2f (delta=%.2f)",
                    agent_id, conf.threshold, delta
                )

        self._save()

    def get_confidence(self, agent_id: str, task_hash: str) -> Optional[float]:
        """Retorna confiança atual para agente + tarefa."""
        key = self._task_key(agent_id, task_hash)
        conf = self._confidence_cache.get(key)
        return conf.confidence if conf else None

    def get_stats(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retorna estatísticas de confiança.

        Args:
            agent_id: Filtrar por agente (opcional)

        Returns:
            Dict com stats
        """
        if agent_id:
            entries = [c for c in self._confidence_cache.values() if c.agent_id == agent_id]
        else:
            entries = list(self._confidence_cache.values())

        if not entries:
            return {"status": "no_data"}

        avg_confidence = sum(c.confidence for c in entries) / len(entries)
        avg_threshold = sum(c.threshold for c in entries) / len(entries)
        search_helped_count = sum(1 for c in entries if c.search_helped is True)
        search_hurt_count = sum(1 for c in entries if c.search_helped is False)

        return {
            "status": "active",
            "total_tasks": len(entries),
            "avg_confidence": round(avg_confidence, 3),
            "avg_threshold": round(avg_threshold, 3),
            "search_helped": search_helped_count,
            "search_hurt": search_hurt_count,
            "search_success_rate": round(search_helped_count / max(1, search_helped_count + search_hurt_count), 3),
        }

    def _load(self):
        """Carrega confiança persistida."""
        if self._persistence_file.exists():
            try:
                data = json.loads(self._persistence_file.read_text(encoding="utf-8"))
                for entry in data.get("confidences", []):
                    key = self._task_key(entry["agent_id"], entry["task_hash"])
                    self._confidence_cache[key] = AgentConfidence(**entry)
                logger.info("[CONF] %d confianças carregadas", len(self._confidence_cache))
            except Exception as e:
                logger.warning("[CONF] Erro ao carregar: %s", e)
        else:
            logger.debug("[CONF] Nenhum dado persistido")

    def _save(self):
        """Salva confiança persistida."""
        self._persistence_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "confidences": [c.to_dict() for c in self._confidence_cache.values()],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        self._persistence_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        logger.debug("[CONF] %d confianças salvas", len(self._confidence_cache))

    def clear(self, agent_id: Optional[str] = None):
        """
        Limpa cache de confiança.

        Args:
            agent_id: Limpar apenas deste agente (opcional, limpa todos se None)
        """
        if agent_id:
            self._confidence_cache = {
                k: v for k, v in self._confidence_cache.items()
                if v.agent_id != agent_id
            }
            logger.info("[CONF] %s: cache limpo", agent_id)
        else:
            self._confidence_cache.clear()
            logger.info("[CONF] cache global limpo")

        self._save()


# Singleton global
_confidence_tracker: Optional[ConfidenceTracker] = None


def get_confidence_tracker() -> ConfidenceTracker:
    """Retorna singleton do ConfidenceTracker."""
    global _confidence_tracker
    if _confidence_tracker is None:
        _confidence_tracker = ConfidenceTracker()
    return _confidence_tracker


# Funções utilitárias
def should_search(agent_id: str, task_hash: str, threshold: Optional[float] = None) -> bool:
    """Wrapper para ConfidenceTracker.should_search()."""
    return get_confidence_tracker().should_search(agent_id, task_hash, threshold)


def record_confidence(agent_id: str, task_hash: str, confidence: float, search_helped: Optional[bool] = None):
    """Wrapper para ConfidenceTracker.record_confidence()."""
    get_confidence_tracker().record_confidence(agent_id, task_hash, confidence, search_helped)


def record_search_outcome(agent_id: str, task_hash: str, helped: bool):
    """Wrapper para ConfidenceTracker.record_search_outcome()."""
    get_confidence_tracker().record_search_outcome(agent_id, task_hash, helped)


def get_stats(agent_id: Optional[str] = None) -> Dict[str, Any]:
    """Wrapper para ConfidenceTracker.get_stats()."""
    return get_confidence_tracker().get_stats(agent_id)