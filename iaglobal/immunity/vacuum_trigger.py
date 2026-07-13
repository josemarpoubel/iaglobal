# ============================================================
# ARQUIVO: iaglobal/immunity/vacuum_trigger.py
# LEI DO VÁCUO: "Você tem que arrumar um espaço para o bem que deseja..."
# ============================================================
"""VacuumTrigger — Implementação da Lei do Vácuo no Ecossistema iaglobal.

A Lei do Vácuo da Prosperidade estabelece:
"Você não pode sentar na cadeira, até você remover o objeto de cima da cadeira.
Memórias processadas devem ser movidas para o longo prazo e removidas do curto prazo."

Este módulo implementa:

1. **Trigger de Vácuo** — Detecta quando espaço deve ser criado
2. **Forçar Diversidade** — Após apoptose, incentiva novos padrões
3. **Limpeza de Espaço** — Remove dados processados do buffer
4. **Renascimento** — Cria oportunidades para novos agentes/padrões

Operação:
- Monitora densidade de agentes/padrões em execução
- Detecta estagnação (mesmos padrões repetidos)
- Trigger de vácuo quando densidade > threshold
- Força diversidade via mutação epigenética
- Remove padrões antigos para criar espaço

Padrão Singleton — existe um único VacuumTrigger para todo o ecossistema.

Exemplo de uso assíncrono:
    ```python
    from iaglobal.immunity.vacuum_trigger import vacuum_trigger

    # Verificar se precisa de vácuo
    needs_vacuum = await vacuum_trigger.check_vacuum_needed_async()

    if needs_vacuum:
        # Trigger de vácuo com apoptose de padrões antigos
        await vacuum_trigger.trigger_vacuum_async(
            force_diversity=True,
            remove_stale_patterns=True,
        )

    # Forçar diversidade pós-apoptose
    await vacuum_trigger.enforce_diversity_async(
        after_apoptosis=["agent_x", "agent_y"]
    )
    ```
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.vacuum_trigger")


@dataclass
class PatternRecord:
    """Registro de um padrão em execução."""

    pattern_id: str
    agent_type: str
    created_at: float
    last_seen: float
    execution_count: int = 0
    is_stale: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VacuumState:
    """Estado atual do vácuo."""

    total_patterns: int = 0
    stale_patterns: int = 0
    diversity_score: float = 0.0  # 0.0 (sem diversidade) → 1.0 (alta diversidade)
    density: float = 0.0  # Padrões por unidade de capacidade
    last_vacuum: float = 0.0
    vacuum_count: int = 0
    patterns_removed: int = 0
    diversity_enforced: int = 0


class VacuumTrigger:
    """Trigger da Lei do Vácuo — Cria espaço para o novo.

    A Lei do Vácuo estabelece que para receber algo novo, é necessário
    primeiro criar espaço removendo o velho. Este módulo:

    1. Monitora densidade de padrões/agente
    2. Detecta estagnação (padrões repetidos)
    3. Trigger de vácuo quando necessário
    4. Remove padrões antigos/stale
    5. Força diversidade pós-apoptose

    Fórmula de Diversidade:
        D = 1 - (max_frequency / total_executions)

        Onde:
        - max_frequency = execuções do padrão mais comum
        - total_executions = soma de todas as execuções

        D = 1.0 → Todos padrões igualmente frequentes (alta diversidade)
        D = 0.0 → Um único padrão domina (baixa diversidade)

    Limiares de Vácuo:
        - density > 0.8 → Vácuo recomendado
        - diversity < 0.3 → Vácuo crítico
        - stale_patterns > 50% → Vácuo emergencial

    Padrão Singleton — existe um único VacuumTrigger para todo o ecossistema.
    """

    _instance: Optional["VacuumTrigger"] = None
    _lock = threading.Lock()

    # Limiares configuráveis (epigenéticos)
    _DENSITY_THRESHOLD = 0.8  # 80% de capacidade = vácuo recomendado
    _DIVERSITY_CRITICAL = 0.3  # < 30% de diversidade = crítico
    _STALE_RATIO_THRESHOLD = 0.5  # > 50% stale = emergencial
    _PATTERN_TTL_SECONDS = 300  # 5 minutos sem ver = stale
    _MAX_PATTERNS = 100  # Capacidade máxima de padrões
    _MIN_DIVERSITY_TARGET = 0.5  # Diversidade mínima após vácuo

    def __new__(cls, *args, **kwargs) -> "VacuumTrigger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._patterns: Dict[str, PatternRecord] = {}
        self._rlock = threading.RLock()
        self._state = VacuumState()
        self._apoptosis_events: List[Tuple[str, float]] = []  # (agent_id, timestamp)

        logger.info(
            "[VacuumTrigger] Sentinela da Lei do Vácuo initialized | "
            "max_patterns=%d | ttl=%ds | density_threshold=%.2f",
            self._MAX_PATTERNS,
            self._PATTERN_TTL_SECONDS,
            self._DENSITY_THRESHOLD,
        )

    def register_pattern(
        self,
        pattern_id: str,
        agent_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Registra um novo padrão em execução.

        Args:
            pattern_id: Identificador único do padrão
            agent_type: Tipo de agente que gerou o padrão
            metadata: Metadados adicionais do padrão
        """
        now = time.time()

        with self._rlock:
            if pattern_id in self._patterns:
                # Atualizar padrão existente
                pattern = self._patterns[pattern_id]
                pattern.last_seen = now
                pattern.execution_count += 1
                pattern.is_stale = False
            else:
                # Criar novo padrão
                self._patterns[pattern_id] = PatternRecord(
                    pattern_id=pattern_id,
                    agent_type=agent_type,
                    created_at=now,
                    last_seen=now,
                    execution_count=1,
                    metadata=metadata or {},
                )

            # Atualizar estado
            self._update_state()

            logger.debug(
                "[VacuumTrigger] Padrão registrado: %s (tipo=%s, execuções=%d)",
                pattern_id,
                agent_type,
                self._patterns[pattern_id].execution_count,
            )

    def _update_state(self) -> None:
        """Atualiza estado do vácuo."""
        now = time.time()

        with self._rlock:
            # Contar padrões stale
            stale_count = 0
            for pattern in self._patterns.values():
                if (now - pattern.last_seen) > self._PATTERN_TTL_SECONDS:
                    pattern.is_stale = True
                    stale_count += 1

            # Calcular densidade
            self._state.total_patterns = len(self._patterns)
            self._state.stale_patterns = stale_count
            self._state.density = min(
                1.0, self._state.total_patterns / self._MAX_PATTERNS
            )

            # Calcular diversidade
            if self._patterns:
                execution_counts = [p.execution_count for p in self._patterns.values()]
                total_execs = sum(execution_counts)
                max_freq = max(execution_counts) if execution_counts else 0

                if total_execs > 0:
                    self._state.diversity_score = 1.0 - (max_freq / total_execs)
                else:
                    self._state.diversity_score = 1.0
            else:
                self._state.diversity_score = 1.0

    def check_vacuum_needed(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Verifica se vácuo é necessário.

        Returns:
            Tuple[bool, Dict[str, Any]]: (needs_vacuum, reason_dict)
        """
        with self._rlock:
            self._update_state()

            reasons = []
            urgency = "none"

            # Verificar densidade
            if self._state.density > self._DENSITY_THRESHOLD:
                reasons.append(
                    f"density={self._state.density:.2f} > {self._DENSITY_THRESHOLD}"
                )
                urgency = "recommended"

            # Verificar diversidade crítica
            if self._state.diversity_score < self._DIVERSITY_CRITICAL:
                reasons.append(
                    f"diversity={self._state.diversity_score:.2f} < {self._DIVERSITY_CRITICAL}"
                )
                urgency = "critical"

            # Verificar stale ratio
            if self._state.total_patterns > 0:
                stale_ratio = self._state.stale_patterns / self._state.total_patterns
                if stale_ratio > self._STALE_RATIO_THRESHOLD:
                    reasons.append(
                        f"stale_ratio={stale_ratio:.2f} > {self._STALE_RATIO_THRESHOLD}"
                    )
                    urgency = "emergency"

            needs_vacuum = len(reasons) > 0

            if needs_vacuum:
                logger.warning(
                    "[VacuumTrigger] 🚨 VÁCUO NECESSÁRIO: %s | urgency=%s",
                    ", ".join(reasons),
                    urgency,
                )

            return needs_vacuum, {
                "needs_vacuum": needs_vacuum,
                "urgency": urgency,
                "reasons": reasons,
                "density": round(self._state.density, 3),
                "diversity_score": round(self._state.diversity_score, 3),
                "stale_patterns": self._state.stale_patterns,
                "total_patterns": self._state.total_patterns,
            }

    async def trigger_vacuum_async(
        self,
        force_diversity: bool = True,
        remove_stale_patterns: bool = True,
    ) -> Dict[str, Any]:
        """
        Executa vácuo para criar espaço.

        Args:
            force_diversity: Se True, força diversidade após vácuo
            remove_stale_patterns: Se True, remove padrões stale

        Returns:
            Dict[str, Any]: Relatório do vácuo executado
        """
        now = time.time()

        # Operações com lock em thread pool
        removed_patterns = await asyncio.to_thread(
            self._remove_stale_patterns if remove_stale_patterns else lambda: 0
        )

        if force_diversity:
            await asyncio.to_thread(self._enforce_diversity_internal)

        with self._rlock:
            self._state.last_vacuum = now
            self._state.vacuum_count += 1
            self._state.patterns_removed += removed_patterns

            logger.info(
                "[VacuumTrigger] ✅ VÁCUO EXECUTADO: %d padrões removidos, diversity=%.2f",
                removed_patterns,
                self._state.diversity_score,
            )

        return {
            "vacuum_executed": True,
            "patterns_removed": removed_patterns,
            "diversity_after": round(self._state.diversity_score, 3),
            "density_after": round(self._state.density, 3),
            "timestamp": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        }

    def _remove_stale_patterns(self) -> int:
        """Remove padrões stale. Retorna quantidade removida."""
        with self._rlock:
            stale_ids = [
                pid
                for pid, p in self._patterns.items()
                if p.is_stale or (time.time() - p.last_seen) > self._PATTERN_TTL_SECONDS
            ]

            for pid in stale_ids:
                del self._patterns[pid]
                logger.debug("[VacuumTrigger] Padrão stale removido: %s", pid)

            self._update_state()
            return len(stale_ids)

    def _enforce_diversity_internal(self) -> None:
        """Força diversidade internamente (pós-vácuo)."""
        with self._rlock:
            # Penalizar padrões muito frequentes
            if not self._patterns:
                return

            execution_counts = [p.execution_count for p in self._patterns.values()]
            max_freq = max(execution_counts) if execution_counts else 0

            if max_freq > 10:  # Padrão dominante
                # Reduzir contagem de padrão dominante em 20%
                for pattern in self._patterns.values():
                    if pattern.execution_count == max_freq:
                        pattern.execution_count = int(pattern.execution_count * 0.8)
                        logger.debug(
                            "[VacuumTrigger] Diversidade forçada: %s reduzido para %d execuções",
                            pattern.pattern_id,
                            pattern.execution_count,
                        )

            self._state.diversity_enforced += 1
            self._update_state()

    def _trim_apoptosis_events(self) -> None:
        """Limita histórico de apoptoses a 100 eventos."""
        if len(self._apoptosis_events) > 100:
            self._apoptosis_events = self._apoptosis_events[-100:]

    async def enforce_diversity_async(
        self,
        after_apoptosis: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Força diversidade após apoptose de agentes.

        Args:
            after_apoptosis: Lista de agentes que sofreram apoptose

        Returns:
            Dict[str, Any]: Relatório de diversidade forçada
        """
        now = time.time()

        # Registrar eventos de apoptose (com lock)
        if after_apoptosis:
            with self._rlock:
                for agent_id in after_apoptosis:
                    self._apoptosis_events.append((agent_id, now))
                # Limitar histórico após adicionar
                self._trim_apoptosis_events()

        # Forçar diversidade (em thread pool para evitar bloqueio)
        diversity_result = await asyncio.to_thread(self._enforce_diversity_internal)

        logger.info(
            "[VacuumTrigger] 🌱 Diversidade forçada após %d apoptoses",
            len(after_apoptosis) if after_apoptosis else 0,
        )

        return {
            "diversity_enforced": True,
            "apoptosis_events": len(after_apoptosis) if after_apoptosis else 0,
            "diversity_score": round(self._state.diversity_score, 3),
            "timestamp": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        }

    def get_vacuum_state(self) -> Dict[str, Any]:
        """Retorna estado atual do vácuo."""
        with self._rlock:
            self._update_state()
            return {
                "total_patterns": self._state.total_patterns,
                "stale_patterns": self._state.stale_patterns,
                "diversity_score": round(self._state.diversity_score, 3),
                "density": round(self._state.density, 3),
                "last_vacuum": datetime.fromtimestamp(
                    self._state.last_vacuum, timezone.utc
                ).isoformat()
                if self._state.last_vacuum > 0
                else None,
                "vacuum_count": self._state.vacuum_count,
                "patterns_removed": self._state.patterns_removed,
                "diversity_enforced_count": self._state.diversity_enforced,
            }

    def get_patterns(self) -> List[Dict[str, Any]]:
        """Retorna lista de padrões registrados."""
        with self._rlock:
            return [
                {
                    "pattern_id": p.pattern_id,
                    "agent_type": p.agent_type,
                    "execution_count": p.execution_count,
                    "is_stale": p.is_stale,
                    "last_seen": datetime.fromtimestamp(
                        p.last_seen, timezone.utc
                    ).isoformat(),
                }
                for p in self._patterns.values()
            ]

    def reset(self) -> None:
        """Reseta estado do vácuo (para testes/reinício)."""
        with self._rlock:
            self._patterns.clear()
            self._apoptosis_events.clear()
            self._state = VacuumState()
            logger.info("[VacuumTrigger] ✅ Estado resetado")


# Singleton global
vacuum_trigger = VacuumTrigger()
