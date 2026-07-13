# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
FeedbackLoop — Registra se a busca ajudou e ajusta confiança.

Funcionalidades:
1. record_outcome(query, agent_id, task_hash, helped) → Registra feedback
2. update_confidence(agent_id, task_hash, helped) → Ajusta confiança
3. get_feedback_history() → Histórico de feedbacks
4. compute_search_effectiveness() → Métricas de eficácia

Integra com:
- SearchMiddleware (feedback pós-execução)
- ConfidenceTracker (ajusta threshold dinamicamente)
- CreditAssignmentEngine (recompensa por busca útil)
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.search.feedback_loop")


class FeedbackOutcome(Enum):
    """Resultado do feedback."""

    HELPED = "helped"  # Busca ajudou
    HARMED = "harmed"  # Busca atrapalhou (info errada)
    NEUTRAL = "neutral"  # Sem impacto
    IGNORED = "ignored"  # Agente ignorou resultados


@dataclass
class FeedbackRecord:
    """Registro de feedback."""

    query: str
    query_hash: str
    agent_id: str
    task_hash: str
    outcome: str  # helped, harmed, neutral, ignored
    timestamp: float
    search_results_count: int = 0
    confidence_before: Optional[float] = None
    confidence_after: Optional[float] = None
    latency_ms: Optional[float] = None  # Tempo da busca
    tokens_used: Optional[int] = None  # Tokens do contexto

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FeedbackRecord":
        return cls(**data)


class FeedbackLoop:
    """Gerencia feedback de buscas e ajusta confiança."""

    # Path do Obsidian
    OBSIDIAN_PATH = Path("obsidian/04_Synapses/feedback_loop")

    # Arquivo de índice
    INDEX_FILE = OBSIDIAN_PATH / "feedback_index.json"

    # Cache em memória
    _cache: List[FeedbackRecord] = []
    _index: Dict[str, FeedbackRecord] = {}  # query_hash → record

    # Stats
    _stats = {
        "total": 0,
        "helped": 0,
        "harmed": 0,
        "neutral": 0,
        "ignored": 0,
        "effectiveness_score": 0.0,
    }

    def __init__(self, obsidian_path: Optional[Path] = None):
        self.obsidian_path = obsidian_path or self.OBSIDIAN_PATH
        self._ensure_directory()
        self._load_index()

    def _ensure_directory(self):
        """Garante que diretório existe."""
        self.obsidian_path.mkdir(parents=True, exist_ok=True)

    def _load_index(self):
        """Carrega índice do disco."""
        if not self.INDEX_FILE.exists():
            logger.debug("[FEEDBACK] Índice não existe, criando vazio")
            self._save_index()
            return

        try:
            with open(self.INDEX_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Carregar cache
            self._cache = []
            self._index = {}

            for record_data in data.get("records", []):
                record = FeedbackRecord.from_dict(record_data)
                self._cache.append(record)
                self._index[record.query_hash] = record

            # Calcular stats
            self._compute_stats()

            logger.info(
                "[FEEDBACK] Carregados %d feedbacks (eficácia=%.2f)",
                len(self._cache),
                self._stats["effectiveness_score"],
            )

        except Exception as e:
            logger.error("[FEEDBACK] Erro ao carregar índice: %s", e)
            self._cache = []
            self._index = {}

    def _save_index(self):
        """Salva índice no disco."""
        try:
            data = {"records": [r.to_dict() for r in self._cache]}

            with open(self.INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug("[FEEDBACK] Índice salvo (%d registros)", len(self._cache))

        except Exception as e:
            logger.error("[FEEDBACK] Erro ao salvar índice: %s", e)

    def _query_hash(self, query: str) -> str:
        """Gera hash único para query."""
        return hashlib.sha3_512(query.encode()).hexdigest()[:32]

    async def record_outcome(
        self,
        query: str,
        agent_id: str,
        task_hash: str,
        outcome: FeedbackOutcome,
        search_results_count: int = 0,
        confidence_before: Optional[float] = None,
        confidence_after: Optional[float] = None,
        latency_ms: Optional[float] = None,
        tokens_used: Optional[int] = None,
    ) -> bool:
        """
        Registra outcome de uma busca.

        Args:
            query: Query original
            agent_id: Agente que fez a busca
            task_hash: Hash da tarefa
            outcome: Resultado (helped, harmed, neutral, ignored)
            search_results_count: Número de resultados retornados
            confidence_before: Confiança antes da busca
            confidence_after: Confiança após a busca
            latency_ms: Latência da busca em ms
            tokens_used: Tokens do contexto injetado

        Returns:
            True se registrou com sucesso
        """
        query_hash = self._query_hash(query)

        # Criar registro
        record = FeedbackRecord(
            query=query,
            query_hash=query_hash,
            agent_id=agent_id,
            task_hash=task_hash,
            outcome=outcome.value,
            timestamp=time.time(),
            search_results_count=search_results_count,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
        )

        # Adicionar ao cache
        self._cache.append(record)
        self._index[query_hash] = record

        # Atualizar stats
        self._update_stats(outcome)

        # Salvar no disco (async)
        await asyncio.to_thread(self._save_index)

        # Salvar arquivo individual (opcional)
        await self._save_individual_record(record)

        logger.info(
            "[FEEDBACK] %s: %s (agent=%s, confidence=%.2f→%.2f)",
            query[:50],
            outcome.value,
            agent_id,
            confidence_before or 0,
            confidence_after or 0,
        )

        return True

    def _update_stats(self, outcome: FeedbackOutcome):
        """Atualiza estatísticas."""
        self._stats["total"] += 1

        if outcome == FeedbackOutcome.HELPED:
            self._stats["helped"] += 1
        elif outcome == FeedbackOutcome.HARMED:
            self._stats["harmed"] += 1
        elif outcome == FeedbackOutcome.NEUTRAL:
            self._stats["neutral"] += 1
        elif outcome == FeedbackOutcome.IGNORED:
            self._stats["ignored"] += 1

        # Calcular eficácia (helped / total)
        if self._stats["total"] > 0:
            self._stats["effectiveness_score"] = (
                self._stats["helped"] / self._stats["total"]
            )

    def _compute_stats(self):
        """Computa stats do cache carregado."""
        self._stats = {
            "total": len(self._cache),
            "helped": 0,
            "harmed": 0,
            "neutral": 0,
            "ignored": 0,
            "effectiveness_score": 0.0,
        }

        for record in self._cache:
            outcome = FeedbackOutcome(record.outcome)
            self._update_stats(outcome)

    async def _save_individual_record(self, record: FeedbackRecord):
        """Salva registro individual em arquivo MD."""
        try:
            filename = f"{record.query_hash}.md"
            filepath = self.obsidian_path / filename

            content = self._format_record_md(record)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        except Exception as e:
            logger.debug("[FEEDBACK] Erro ao salvar arquivo individual: %s", e)

    def _format_record_md(self, record: FeedbackRecord) -> str:
        """Formata registro como Markdown."""
        outcome_emoji = {
            "helped": "✅",
            "harmed": "❌",
            "neutral": "➖",
            "ignored": "🚫",
        }

        lines = [
            f"# Feedback: {record.query}",
            "",
            f"**Hash:** `{record.query_hash}`",
            f"**Data:** {datetime.fromtimestamp(record.timestamp, tz=timezone.utc).isoformat()}",
            f"**Agente:** {record.agent_id}",
            f"**Outcome:** {outcome_emoji.get(record.outcome, '?')} {record.outcome}",
            "",
            "## Métricas",
            "",
            f"- **Resultados:** {record.search_results_count}",
            f"- **Confiança antes:** {record.confidence_before}",
            f"- **Confiança depois:** {record.confidence_after}",
            f"- **Latência:** {record.latency_ms}ms" if record.latency_ms else "",
            f"- **Tokens:** {record.tokens_used}" if record.tokens_used else "",
            "",
            "---",
            f"*Persistido por iaglobal.FeedbackLoop*",
        ]

        return "\n".join(filter(None, lines))

    async def update_confidence(
        self,
        agent_id: str,
        task_hash: str,
        helped: bool,
        delta: float = 0.1,
    ) -> Optional[float]:
        """
        Atualiza confiança do agente baseado no feedback.

        Args:
            agent_id: Agente que fez a busca
            task_hash: Hash da tarefa
            helped: Se a busca ajudou
            delta: Quanto ajustar (padrão 0.1)

        Returns:
            Nova confiança ou None se não encontrou
        """
        try:
            from iaglobal.search.confidence_tracker import get_confidence_tracker

            tracker = get_confidence_tracker()

            # Obter confiança atual
            confidence = tracker.get_confidence(agent_id, task_hash)

            if confidence is None:
                # Criar nova confiança
                confidence = 0.5  # Neutro

            # Ajustar
            if helped:
                new_confidence = min(1.0, confidence + delta)
            else:
                new_confidence = max(0.0, confidence - delta)

            # Registrar
            tracker.record_confidence(agent_id, task_hash, new_confidence)

            logger.debug(
                "[FEEDBACK] %s: confiança %.2f → %.2f (%s)",
                agent_id,
                confidence,
                new_confidence,
                "ajudou" if helped else "atrapalhou",
            )

            return new_confidence

        except Exception as e:
            logger.error("[FEEDBACK] Erro ao atualizar confiança: %s", e)
            return None

    async def get_feedback_history(self, limit: int = 50) -> List[FeedbackRecord]:
        """
        Retorna histórico de feedbacks.

        Args:
            limit: Máximo de registros

        Returns:
            Lista de FeedbackRecord (ordenados por timestamp, mais recente primeiro)
        """
        return sorted(
            self._cache,
            key=lambda r: r.timestamp,
            reverse=True,
        )[:limit]

    def get_stats(self) -> dict:
        """Retorna estatísticas de uso."""
        return self._stats.copy()

    def compute_search_effectiveness(self, agent_id: Optional[str] = None) -> float:
        """
        Computa eficácia de buscas.

        Args:
            agent_id: Filtrar por agente (None = todos)

        Returns:
            Eficácia (0.0 - 1.0)
        """
        if agent_id:
            # Filtrar por agente
            filtered = [r for r in self._cache if r.agent_id == agent_id]
            if not filtered:
                return 0.0

            helped = sum(1 for r in filtered if r.outcome == "helped")
            return helped / len(filtered)

        return self._stats["effectiveness_score"]

    def clear_cache(self):
        """Limpa cache em memória."""
        self._cache.clear()
        self._index.clear()
        logger.debug("[FEEDBACK] Cache em memória limpo")


# Singleton global
_feedback: Optional[FeedbackLoop] = None


def get_feedback_loop(obsidian_path: Optional[Path] = None) -> FeedbackLoop:
    """Retorna singleton do FeedbackLoop."""
    global _feedback
    if _feedback is None:
        _feedback = FeedbackLoop(obsidian_path=obsidian_path)
    return _feedback


# Funções utilitárias
async def record_outcome(
    query: str,
    agent_id: str,
    task_hash: str,
    outcome: FeedbackOutcome,
    **kwargs,
) -> bool:
    """Wrapper para FeedbackLoop.record_outcome()."""
    return await get_feedback_loop().record_outcome(
        query, agent_id, task_hash, outcome, **kwargs
    )


async def update_confidence(
    agent_id: str,
    task_hash: str,
    helped: bool,
    delta: float = 0.1,
) -> Optional[float]:
    """Wrapper para FeedbackLoop.update_confidence()."""
    return await get_feedback_loop().update_confidence(
        agent_id, task_hash, helped, delta
    )


async def get_feedback_history(limit: int = 50) -> List[FeedbackRecord]:
    """Wrapper para FeedbackLoop.get_feedback_history()."""
    return await get_feedback_loop().get_feedback_history(limit)


def get_feedback_stats() -> dict:
    """Wrapper para FeedbackLoop.get_stats()."""
    return get_feedback_loop().get_stats()


def compute_search_effectiveness(agent_id: Optional[str] = None) -> float:
    """Wrapper para FeedbackLoop.compute_search_effectiveness()."""
    return get_feedback_loop().compute_search_effectiveness(agent_id)
