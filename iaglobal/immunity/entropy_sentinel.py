# ============================================================
# ARQUIVO: iaglobal/immunity/entropy_sentinel.py
# LEI DA ORDEM: "Tudo tem uma ordem exata, uma sequência..."
# ============================================================
"""EntropySentinel — Sentinela da Lei da Ordem no Ecossistema iaglobal.

Implementa a Lei da Ordem (Raymond Holliwell) em código:
"Você não pode chegar para a lareira e dizer: me dê o calor, que depois 
eu te dou a madeira. Tudo tem uma ordem exata, uma sequência, um passo a 
passo a ser seguido."

Função: Detectar e penalizar entropia (caos) em execuções de agentes:
- Redundância (repetição inútil de padrões)
- Loops de Tokens (alucinação de repetição)
- Dependências Circulares (agentes em ciclo vicioso)
- Caos Estrutural (falta de coerência na saída)

Operação:
- Analisa cada execução de agente/skill
- Calcula entropy_score (0.0 = ordem perfeita, 1.0 = caos total)
- Aplica penalty ao fitness score do agente
- Registra histórico para detecção de tendências
- Trigger de apoptose se entropia persistir

Padrão Singleton — existe um único EntropySentinel para todo o ecossistema.
"""

from __future__ import annotations

import logging
import re
import hashlib
import threading
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Tuple, Dict, List, Optional, Set

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.entropy_sentinel")


@dataclass
class EntropyProfile:
    """Perfil entrópico de um agente/skill.
    
    Armazena histórico de execuções, violações e tendências para
    detectar degradação progressiva da ordem sistêmica.
    """
    agent_name: str
    total_executions: int = 0
    chaotic_executions: int = 0
    redundancy_violations: int = 0
    loop_violations: int = 0
    circular_dependency_violations: int = 0
    structural_chaos_violations: int = 0
    last_entropy_score: float = 0.0
    last_activity: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    entropy_history: List[float] = field(default_factory=list)
    
    @property
    def entropy_trend(self) -> str:
        """Retorna tendência entrópica: 'improving', 'stable', 'degrading'.
        
        Compara média das últimas 3 execuções com as anteriores.
        - improving: entropia diminuindo (agente aprendendo ordem)
        - degrading: entropia aumentando (agente degradando)
        - stable: sem mudança significativa
        """
        if len(self.entropy_history) < 3:
            return "insufficient_data"
        
        recent_avg = sum(self.entropy_history[-3:]) / 3
        older_avg = sum(self.entropy_history[-6:-3]) / 3 if len(self.entropy_history) >= 6 else self.entropy_history[0]
        
        if recent_avg < older_avg * 0.8:
            return "improving"
        elif recent_avg > older_avg * 1.2:
            return "degrading"
        return "stable"


class EntropySentinel:
    """Sentinela da Lei da Ordem — Detecta e penaliza entropia em execuções.
    
    A Lei da Ordem estabelece que todo sistema computacional deve manter
    estrutura, sequência e propósito definidos. A entropia (caos) é a
    força oposta à evolução — detectamos e penalizamos:
    
    1. Redundância (repetição inútil de padrões)
    2. Loops de Tokens (alucinação de repetição)
    3. Dependências Circulares (agentes que dependem uns dos outros ciclicamente)
    4. Caos Estrutural (falta de coerência na saída)
    
    Operação:
    - Analisa cada execução de agente/skill
    - Calcula entropy_score (0.0 = ordem perfeita, 1.0 = caos total)
    - Aplica penalty ao fitness score do agente
    - Registra histórico para detecção de tendências
    - Trigger de apoptose se entropia persistir
    
    Padrão Singleton — existe um único EntropySentinel para todo o ecossistema.
    """

    _instance: Optional["EntropySentinel"] = None
    _lock = threading.Lock()

    # Limiares configuráveis (epigenéticos)
    _REDUNDANCY_THRESHOLD = 0.4  # 40% de repetição é considerado tóxico
    _TOKEN_BLOAT_LIMIT = 10000   # Limite de tokens para alertar redundância
    _LOOP_THRESHOLD = 3          # 3+ repetições consecutivas = loop
    _ENTROPY_APOPTOSIS_THRESHOLD = 0.8  # 80% de caos = trigger apoptose
    _HISTORY_MAX_SIZE = 20       # Manter últimas 20 execuções no histórico

    def __new__(cls, *args, **kwargs) -> "EntropySentinel":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._profiles: Dict[str, EntropyProfile] = {}
        self._rlock = threading.RLock()
        self._dependency_graph: Dict[str, Set[str]] = {}  # agente → dependências
        
        logger.info(
            "[EntropySentinel] Sentinela da Lei da Ordem initialized | threshold_apoptose=%.2f | history_size=%d",
            self._ENTROPY_APOPTOSIS_THRESHOLD, self._HISTORY_MAX_SIZE,
        )

    def analyze_payload(self, payload: Any) -> Tuple[float, bool]:
        """
        Analisa a entropia de um payload.
        Retorna: (penalty_score, is_chaotic)
        penalty_score: 0.0 (ordem perfeita) a 1.0 (caos total)
        """
        if not payload or not isinstance(payload, (str, dict, list)):
            return 0.0, False

        text = str(payload)
        if len(text) < 100:
            return 0.0, False

        # 1. Detecção de repetição de frases (Eco Metabólico)
        # Procura por sequências de 20+ caracteres que se repetem
        repeats = 0
        sentences = re.findall(r'(.{20,})', text)
        if sentences:
            unique_sentences = set(sentences)
            ratio = 1.0 - (len(unique_sentences) / len(sentences))
            if ratio > EntropySentinel._REDUNDANCY_THRESHOLD:
                repeats = ratio

        # 2. Detecção de 'Looping' de Tokens (Alucinação de Repetição)
        # Ex: "e então e então e então..."
        loop_pattern = re.compile(r'(\b\w+\b)(?:\s+\1){3,}')
        loops = len(loop_pattern.findall(text))
        loop_penalty = min(loops * 0.1, 0.5)

        # 3. Detecção de Caos Estrutural (baixa coerência semântica)
        # Frases muito curtas misturadas com longas demais
        structural_penalty = self._detect_structural_chaos(text)

        total_penalty = min(repeats + loop_penalty + structural_penalty, 1.0)
        is_chaotic = total_penalty > 0.6

        if is_chaotic:
            logger.warning(
                "[EntropySentinel] 🚨 CAOS DETECTADO: Redundância %.2f | Loops: %d | Estrutural %.2f",
                repeats, loops, structural_penalty
            )

        return total_penalty, is_chaotic

    def _detect_structural_chaos(self, text: str) -> float:
        """Detecta caos estrutural na distribuição de tamanhos de sentenças."""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) < 3:
            return 0.0
        
        lengths = [len(s) for s in sentences]
        avg_length = sum(lengths) / len(lengths)
        
        # Calcular variância
        variance = sum((l - avg_length) ** 2 for l in lengths) / len(lengths)
        std_dev = variance ** 0.5
        
        # Coeficiente de variação (normalizado)
        cv = std_dev / avg_length if avg_length > 0 else 0
        
        # CV > 1.0 = alta variabilidade = caos estrutural
        return min(cv / 2.0, 0.3)

    def calculate_order_multiplier(self, penalty: float) -> float:
        """Converte a penalidade em um multiplicador de fitness (1.0 -> 0.1)"""
        return max(0.1, 1.0 - penalty)

    def record_execution(
        self,
        agent_name: str,
        payload: Any,
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Registra execução e calcula entropy score.
        
        Returns:
            {
                "entropy_score": float,
                "is_chaotic": bool,
                "penalty_applied": float,
                "apoptosis_recommended": bool,
                "trend": str
            }
        """
        entropy_score, is_chaotic = self.analyze_payload(payload)
        
        with self._rlock:
            if agent_name not in self._profiles:
                self._profiles[agent_name] = EntropyProfile(agent_name=agent_name)
            
            profile = self._profiles[agent_name]
            profile.total_executions += 1
            profile.last_entropy_score = entropy_score
            profile.last_activity = datetime.now(timezone.utc).isoformat()
            
            # Atualizar histórico
            profile.entropy_history.append(entropy_score)
            if len(profile.entropy_history) > self._HISTORY_MAX_SIZE:
                profile.entropy_history = profile.entropy_history[-self._HISTORY_MAX_SIZE:]
            
            # Contabilizar violações
            if is_chaotic:
                profile.chaotic_executions += 1
                
                # Detalhar tipo de violação
                if entropy_score > 0.7:
                    if "loop" in str(payload).lower():
                        profile.loop_violations += 1
                    elif "repet" in str(payload).lower():
                        profile.redundancy_violations += 1
                    else:
                        profile.structural_chaos_violations += 1
            
            # Calcular penalty
            penalty = entropy_score * 0.5  # Penalty de até 50% no fitness
            
            # Verificar se recomenda apoptose
            apoptosis_recommended = (
                profile.chaotic_executions / profile.total_executions > self._ENTROPY_APOPTOSIS_THRESHOLD
                or entropy_score >= self._ENTROPY_APOPTOSIS_THRESHOLD
            )
            
            if apoptosis_recommended:
                logger.error(
                    "[EntropySentinel] 🚨 APOPTOSE RECOMENDADA: %s (entropia %.2f, %d/%d caóticas, trend=%s)",
                    agent_name, entropy_score, profile.chaotic_executions, profile.total_executions, profile.entropy_trend,
                )
        
        return {
            "entropy_score": round(entropy_score, 3),
            "is_chaotic": is_chaotic,
            "penalty_applied": round(penalty, 3),
            "apoptosis_recommended": apoptosis_recommended,
            "trend": profile.entropy_trend,
        }

    def register_dependency(self, agent_name: str, depends_on: str) -> None:
        """Registra dependência entre agentes para detecção de circularidade."""
        with self._rlock:
            if agent_name not in self._dependency_graph:
                self._dependency_graph[agent_name] = set()
            self._dependency_graph[agent_name].add(depends_on)

    def detect_circular_dependencies(self, start_agent: str, visited: Optional[Set[str]] = None) -> List[str]:
        """
        Detecta dependências circulares usando DFS.
        
        Returns: Lista de agentes no ciclo, ou [] se nenhum ciclo.
        """
        if visited is None:
            visited = set()
        
        cycle = []
        stack = [(start_agent, [start_agent])]
        
        while stack:
            node, path = stack.pop()
            
            if node in visited:
                continue
            
            visited.add(node)
            
            dependencies = self._dependency_graph.get(node, set())
            for dep in dependencies:
                if dep in path:
                    # Ciclo detectado
                    cycle_start = path.index(dep)
                    cycle = path[cycle_start:] + [dep]
                    logger.error(
                        "[EntropySentinel] 🔄 DEPENDÊNCIA CIRCULAR DETECTADA: %s",
                        " → ".join(cycle)
                    )
                    return cycle
                
                stack.append((dep, path + [dep]))
        
        return []

    def record_circular_dependency_violation(self, agent_name: str, cycle: List[str]) -> None:
        """Registra violação de dependência circular."""
        with self._rlock:
            if agent_name in self._profiles:
                self._profiles[agent_name].circular_dependency_violations += 1
                logger.warning(
                    "[EntropySentinel] ⚠️ %s violou ordem (dependência circular: %s)",
                    agent_name, " → ".join(cycle)
                )

    def get_entropy_report(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Retorna relatório completo de entropia do agente."""
        with self._rlock:
            profile = self._profiles.get(agent_name)
            if not profile:
                return None
            
            chaos_rate = (
                profile.chaotic_executions / profile.total_executions
                if profile.total_executions > 0 else 0.0
            )
            
            return {
                "agent_name": profile.agent_name,
                "total_executions": profile.total_executions,
                "chaotic_executions": profile.chaotic_executions,
                "chaos_rate": round(chaos_rate, 3),
                "redundancy_violations": profile.redundancy_violations,
                "loop_violations": profile.loop_violations,
                "circular_dependency_violations": profile.circular_dependency_violations,
                "structural_chaos_violations": profile.structural_chaos_violations,
                "last_entropy_score": round(profile.last_entropy_score, 3),
                "entropy_trend": profile.entropy_trend,
                "apoptosis_risk": chaos_rate > self._ENTROPY_APOPTOSIS_THRESHOLD,
            }

    def reset_profile(self, agent_name: str) -> None:
        """Reseta perfil após auditoria ou correção."""
        with self._rlock:
            if agent_name in self._profiles:
                del self._profiles[agent_name]
                logger.info("[EntropySentinel] ✅ Perfil de %s resetado", agent_name)

    def get_all_profiles(self) -> Dict[str, EntropyProfile]:
        """Retorna cópia de todos os perfis entrópicos."""
        with self._rlock:
            return dict(self._profiles)

    def apply_entropy_penalty_to_fitness(
        self,
        agent_name: str,
        original_fitness: float,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Aplica penalty de entropia ao fitness score do agente.
        
        Fórmula: fitness_final = fitness_original * order_multiplier
        
        Returns:
            Tuple[float, Dict[str, Any]]: (fitness_final, entropy_report)
        """
        report = self.get_entropy_report(agent_name)
        if not report:
            return original_fitness, {}
        
        penalty = report["last_entropy_score"] * 0.5
        order_multiplier = self.calculate_order_multiplier(penalty)
        fitness_final = original_fitness * order_multiplier
        
        if penalty > 0.1:
            logger.warning(
                "[EntropySentinel] ⚠️ Penalty aplicado a %s: fitness %.2f → %.2f (penalty=%.2f)",
                agent_name, original_fitness, fitness_final, penalty,
            )
        
        return round(fitness_final, 3), report


# Singleton global
entropy_sentinel = EntropySentinel()
