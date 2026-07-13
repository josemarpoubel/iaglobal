# ============================================================
# ARQUIVO: iaglobal/immunity/symbiosis_score.py
# LEI DA CARIDADE: "Erros devem ser enriquecidos com contexto..."
# ============================================================
"""SymbiosisScore — Implementação da Lei da Caridade no Ecossistema iaglobal.

A Lei da Caridade estabelece que agentes devem cooperar para sobreviver —
o todo é maior que a soma das partes. Este módulo implementa:

1. **Detecção de Sinergia** — Identifica quando agentes cooperam produtivamente
2. **Bonificação de Fitness** — Aumenta score de agentes que colaboram
3. **Memória de Cooperação** — Rastreia histórico de interações positivas
4. **Reconhecimento de Padrões** — Identifica padrões de colaboração bem-sucedidos

Operação:
- Monitora comunicações entre agentes (via AcetylcholineBus)
- Calcula symbiosis_score baseado em frequência e qualidade de colaborações
- Aplica bonus ao fitness de agentes cooperativos
- Identifica "ilhas de isolamento" (agentes que não cooperam)

Padrão Singleton — existe um único SymbiosisScore para todo o ecossistema.

Exemplo de uso assíncrono:
    ```python
    from iaglobal.immunity.symbiosis_score import symbiosis_score

    # Registrar cooperação assíncrona
    await symbiosis_score.record_cooperation_async(
        agent_source="coder_agent",
        agent_target="critic_agent",
        success=True,
        outcome_quality=0.9,
    )

    # Aplicar bonus de simbiose
    fitness_final, report = await symbiosis_score.apply_symbiosis_bonus_async(
        agent_id="coder_agent",
        original_fitness=0.8,
    )
    ```
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.symbiosis_score")


@dataclass
class CooperationRecord:
    """Registro de uma cooperação entre dois agentes."""

    agent_source: str
    agent_target: str
    timestamp: float
    success: bool
    outcome_quality: float  # 0.0 → 1.0 (qualidade do resultado)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SymbiosisProfile:
    """Perfil de simbiose de um agente."""

    agent_id: str
    total_cooperations: int = 0
    successful_cooperations: int = 0
    failed_cooperations: int = 0
    cooperation_partners: Set[str] = field(default_factory=set)
    cooperation_history: List[CooperationRecord] = field(default_factory=list)
    last_cooperation: float = 0.0
    symbiosis_score: float = 0.0  # 0.0 (isolado) → 1.0 (altamente cooperativo)
    isolation_warning: bool = False

    @property
    def cooperation_rate(self) -> float:
        """Taxa de sucesso de cooperações."""
        if self.total_cooperations == 0:
            return 0.0
        return self.successful_cooperations / self.total_cooperations

    @property
    def partner_diversity(self) -> float:
        """Diversidade de parceiros (quantos agentes diferentes)."""
        return len(self.cooperation_partners)

    @property
    def is_isolated(self) -> bool:
        """Verifica se agente está isolado (sem cooperações recentes)."""
        if self.last_cooperation == 0.0:
            return True
        # Considera isolado se sem cooperação há > 5 minutos
        return (time.time() - self.last_cooperation) > 300


class SymbiosisScore:
    """Calculadora de Score de Simbiose — Lei da Caridade.

    A Lei da Caridade estabelece que agentes devem enriquecer uns aos outros
    com contexto e cooperação. Este módulo:

    1. Monitora interações entre agentes
    2. Calcula score baseado em:
       - Frequência de cooperações
       - Taxa de sucesso
       - Diversidade de parceiros
       - Qualidade dos resultados
    3. Aplica bonus/malus ao fitness
    4. Detecta agentes isolados (potencial problema)

    Fórmula do SymbiosisScore:
        S = (F × 0.3) + (R × 0.4) + (D × 0.2) + (Q × 0.1)

        Onde:
        F = Frequência normalizada (cooperações / expected)
        R = Taxa de sucesso (sucessos / total)
        D = Diversidade de parceiros (parceiros / max_expected)
        Q = Qualidade média dos resultados

    Padrão Singleton — existe um único SymbiosisScore para todo o ecossistema.
    """

    _instance: Optional["SymbiosisScore"] = None
    _lock = threading.Lock()

    # Limiares configuráveis (epigenéticos)
    _COOPERATION_EXPECTED_PER_HOUR = 10  # Cooperações esperadas por hora
    _ISOLATION_THRESHOLD_MINUTES = 5  # Sem cooperação por X min = isolado
    _SYMBIOSIS_BONUS_MULTIPLIER = 1.2  # Bonus para alta simbiose
    _ISOLATION_PENALTY_MULTIPLIER = 0.8  # Penalidade para isolamento
    _HISTORY_MAX_SIZE = 50  # Últimas 50 cooperações no histórico

    def __new__(cls, *args, **kwargs) -> "SymbiosisScore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._profiles: Dict[str, SymbiosisProfile] = {}
        self._rlock = threading.RLock()
        self._cooperation_matrix: Dict[Tuple[str, str], List[float]] = defaultdict(list)

        logger.info(
            "[SymbiosisScore] Sentinela da Lei da Caridade initialized | "
            "expected_per_hour=%d | isolation_threshold=%dmin",
            self._COOPERATION_EXPECTED_PER_HOUR,
            self._ISOLATION_THRESHOLD_MINUTES,
        )

    def record_cooperation(
        self,
        agent_source: str,
        agent_target: str,
        success: bool,
        outcome_quality: float = 0.5,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Registra uma cooperação entre dois agentes (síncrono).

        Para uso assíncrono, prefira `record_cooperation_async()`.

        Args:
            agent_source: Agente que iniciou a cooperação
            agent_target: Agente que recebeu/cooperou
            success: Se a cooperação foi bem-sucedida
            outcome_quality: Qualidade do resultado (0.0 → 1.0)
            context: Contexto adicional da cooperação
        """
        now = time.time()
        record = CooperationRecord(
            agent_source=agent_source,
            agent_target=agent_target,
            timestamp=now,
            success=success,
            outcome_quality=outcome_quality,
            context=context or {},
        )

        with self._rlock:
            # Atualizar perfil do source
            self._ensure_profile(agent_source)
            source_profile = self._profiles[agent_source]
            source_profile.total_cooperations += 1
            if success:
                source_profile.successful_cooperations += 1
            else:
                source_profile.failed_cooperations += 1
            source_profile.cooperation_partners.add(agent_target)
            source_profile.last_cooperation = now
            source_profile.cooperation_history.append(record)

            # Limitar histórico
            if len(source_profile.cooperation_history) > self._HISTORY_MAX_SIZE:
                source_profile.cooperation_history = source_profile.cooperation_history[
                    -self._HISTORY_MAX_SIZE :
                ]

            # Atualizar matriz de cooperação (para análise de pares)
            pair_key = (agent_source, agent_target)
            self._cooperation_matrix[pair_key].append(
                outcome_quality if success else 0.0
            )

            # Atualizar score
            self._update_symbiosis_score(agent_source)

            logger.debug(
                "[SymbiosisScore] Cooperação registrada: %s → %s | success=%s | quality=%.2f",
                agent_source,
                agent_target,
                success,
                outcome_quality,
            )

    async def record_cooperation_async(
        self,
        agent_source: str,
        agent_target: str,
        success: bool,
        outcome_quality: float = 0.5,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Registra uma cooperação entre dois agentes (assíncrono).

        Usa `asyncio.to_thread()` para operações com lock.
        """
        await asyncio.to_thread(
            self.record_cooperation,
            agent_source,
            agent_target,
            success,
            outcome_quality,
            context,
        )

    def _ensure_profile(self, agent_id: str) -> None:
        """Garante que perfil existe para o agente."""
        if agent_id not in self._profiles:
            self._profiles[agent_id] = SymbiosisProfile(agent_id=agent_id)

    def _update_symbiosis_score(self, agent_id: str) -> None:
        """Atualiza symbiosis_score de um agente."""
        with self._rlock:
            profile = self._profiles[agent_id]

            # Calcular componentes
            # F = Frequência normalizada
            expected_cooperations = (
                self._COOPERATION_EXPECTED_PER_HOUR / 60
            )  # por minuto
            time_window_minutes = (
                time.time() - (profile.last_cooperation or time.time())
            ) / 60
            if time_window_minutes > 0:
                frequency_ratio = min(
                    1.0,
                    profile.total_cooperations
                    / (expected_cooperations * max(1, time_window_minutes)),
                )
            else:
                frequency_ratio = 0.0

            # R = Taxa de sucesso
            success_rate = profile.cooperation_rate

            # D = Diversidade de parceiros
            max_expected_partners = (
                5  # Espera-se cooperação com até 5 agentes diferentes
            )
            diversity_ratio = min(
                1.0, profile.partner_diversity / max_expected_partners
            )

            # Q = Qualidade média
            if profile.cooperation_history:
                avg_quality = sum(
                    r.outcome_quality for r in profile.cooperation_history[-10:]
                ) / min(10, len(profile.cooperation_history))
            else:
                avg_quality = 0.0

            # Calcular score final
            # S = (F × 0.3) + (R × 0.4) + (D × 0.2) + (Q × 0.1)
            score = (
                (frequency_ratio * 0.3)
                + (success_rate * 0.4)
                + (diversity_ratio * 0.2)
                + (avg_quality * 0.1)
            )

            profile.symbiosis_score = score

            # Verificar isolamento
            profile.isolation_warning = profile.is_isolated

            if profile.isolation_warning:
                logger.warning(
                    "[SymbiosisScore] ⚠️ AGENTE ISOLADO: %s (score=%.2f, última cooperação há %.1fmin)",
                    agent_id,
                    score,
                    (time.time() - profile.last_cooperation) / 60
                    if profile.last_cooperation > 0
                    else 0,
                )

    def get_symbiosis_score(self, agent_id: str) -> float:
        """Retorna symbiosis_score de um agente."""
        with self._rlock:
            profile = self._profiles.get(agent_id)
            return profile.symbiosis_score if profile else 0.0

    def apply_symbiosis_bonus(
        self, agent_id: str, original_fitness: float
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Aplica bonus/penalidade de simbiose ao fitness (síncrono).

        Para uso assíncrono, prefira `apply_symbiosis_bonus_async()`.

        Args:
            agent_id: Agente a ser avaliado
            original_fitness: Fitness score original

        Returns:
            Tuple[float, Dict[str, Any]]: (fitness_final, report)
        """
        with self._rlock:
            profile = self._profiles.get(agent_id)
            if not profile:
                return original_fitness, {"applied": False, "reason": "no_profile"}

            score = profile.symbiosis_score
            report = {
                "applied": True,
                "symbiosis_score": round(score, 3),
                "cooperation_rate": round(profile.cooperation_rate, 3),
                "partner_diversity": profile.partner_diversity,
                "is_isolated": profile.is_isolated,
            }

            # Aplicar multiplicador
            if score >= 0.7:
                # Alta simbiose → bonus
                multiplier = self._SYMBIOSIS_BONUS_MULTIPLIER
                report["multiplier"] = multiplier
                report["effect"] = "bonus"
            elif profile.is_isolated:
                # Isolamento → penalidade
                multiplier = self._ISOLATION_PENALTY_MULTIPLIER
                report["multiplier"] = multiplier
                report["effect"] = "penalty"
            else:
                # Normal → sem alteração
                multiplier = 1.0
                report["multiplier"] = multiplier
                report["effect"] = "neutral"

            fitness_final = original_fitness * multiplier

            if multiplier != 1.0:
                logger.info(
                    "[SymbiosisScore] %s aplicado a %s: fitness %.2f → %.2f (score=%.2f)",
                    report["effect"].upper(),
                    agent_id,
                    original_fitness,
                    fitness_final,
                    score,
                )

            return round(fitness_final, 3), report

    async def apply_symbiosis_bonus_async(
        self, agent_id: str, original_fitness: float
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Aplica bonus/penalidade de simbiose ao fitness (assíncrono).

        Usa `asyncio.to_thread()` para operações com lock.
        """
        return await asyncio.to_thread(
            self.apply_symbiosis_bonus,
            agent_id,
            original_fitness,
        )

    def get_cooperation_partners(self, agent_id: str) -> Set[str]:
        """Retorna conjunto de parceiros de cooperação de um agente."""
        with self._rlock:
            profile = self._profiles.get(agent_id)
            return profile.cooperation_partners if profile else set()

    def get_isolated_agents(self) -> List[str]:
        """Retorna lista de agentes isolados (sem cooperação recente)."""
        with self._rlock:
            return [
                agent_id
                for agent_id, profile in self._profiles.items()
                if profile.is_isolated
            ]

    def get_top_cooperators(self, top_n: int = 10) -> List[Tuple[str, float]]:
        """Retorna top N agentes com maior symbiosis_score."""
        with self._rlock:
            sorted_agents = sorted(
                [
                    (agent_id, profile.symbiosis_score)
                    for agent_id, profile in self._profiles.items()
                ],
                key=lambda x: x[1],
                reverse=True,
            )
            return sorted_agents[:top_n]

    def get_cooperation_quality(self, agent_a: str, agent_b: str) -> float:
        """Retorna qualidade média de cooperações entre dois agentes específicos."""
        with self._rlock:
            pair_key = (agent_a, agent_b)
            qualities = self._cooperation_matrix.get(pair_key, [])

            if not qualities:
                # Tentar ordem inversa
                pair_key = (agent_b, agent_a)
                qualities = self._cooperation_matrix.get(pair_key, [])

            if not qualities:
                return 0.0

            return sum(qualities) / len(qualities)

    def get_symbiosis_report(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retorna relatório completo de simbiose de um agente."""
        with self._rlock:
            profile = self._profiles.get(agent_id)
            if not profile:
                return None

            return {
                "agent_id": profile.agent_id,
                "symbiosis_score": round(profile.symbiosis_score, 3),
                "total_cooperations": profile.total_cooperations,
                "successful_cooperations": profile.successful_cooperations,
                "failed_cooperations": profile.failed_cooperations,
                "cooperation_rate": round(profile.cooperation_rate, 3),
                "partner_diversity": profile.partner_diversity,
                "partners": list(profile.cooperation_partners),
                "is_isolated": profile.is_isolated,
                "isolation_warning": profile.isolation_warning,
                "last_cooperation": datetime.fromtimestamp(
                    profile.last_cooperation, timezone.utc
                ).isoformat()
                if profile.last_cooperation > 0
                else None,
            }

    def reset_profile(self, agent_id: str) -> None:
        """Reseta perfil de simbiose de um agente."""
        with self._rlock:
            if agent_id in self._profiles:
                del self._profiles[agent_id]
                # Limpar matriz de cooperação
                keys_to_remove = [
                    k for k in self._cooperation_matrix.keys() if agent_id in k
                ]
                for key in keys_to_remove:
                    del self._cooperation_matrix[key]

                logger.info("[SymbiosisScore] ✅ Perfil de %s resetado", agent_id)

    def get_all_profiles(self) -> Dict[str, SymbiosisProfile]:
        """Retorna cópia de todos os perfis de simbiose."""
        with self._rlock:
            return dict(self._profiles)

    def health_check(self) -> Dict[str, Any]:
        """Retorna status geral do sistema de simbiose."""
        with self._rlock:
            isolated_count = len(self.get_isolated_agents())
            avg_score = (
                sum(p.symbiosis_score for p in self._profiles.values())
                / len(self._profiles)
                if self._profiles
                else 0.0
            )

            return {
                "total_agents": len(self._profiles),
                "isolated_agents": isolated_count,
                "average_symbiosis_score": round(avg_score, 3),
                "total_cooperations": sum(
                    p.total_cooperations for p in self._profiles.values()
                ),
                "cooperation_pairs": len(self._cooperation_matrix),
            }


# Singleton global
symbiosis_score = SymbiosisScore()
