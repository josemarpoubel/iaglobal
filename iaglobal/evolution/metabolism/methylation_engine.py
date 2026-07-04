"""
MethylationEngine — Engine unificado do ciclo de metilação em tempo real.

Integra:
1. Methionina → SAMe (doação de grupos metil)
2. SAMe → Metilação (expressão epigenética)
3. Metilação → Homocisteína (subproduto)
4. Homocisteína → Transsulfuração ou Remetilação

Detecta "homocisteína elevada" (technical debt metabólico) e triggera
ações corretivas automáticas.
"""
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import json

from iaglobal._paths import METHYLATION_ENGINE_FILE
from iaglobal.evolution.metabolism.homocysteine_pool import (
    CandidateSkill, 
    homocysteine_pool, 
    HomocysteinePool
)
from iaglobal.evolution.metabolism.methylation_cycle import MethylationCycle
from iaglobal.evolution.metabolism.transsulfuration_cycle import TranssulfurationCycle
from iaglobal.evolution.metabolism.opportunity_cost_detector import (
    OpportunityCostDetector, 
    opportunity_cost_detector
)
from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry, epigenetic_registry

logger = logging.getLogger(__name__)


@dataclass
class MethylationState:
    """Estado atual do ciclo de metilação."""
    sam_e_level: float = 100.0  # S-adenosilmetionina (doador de metil)
    methylation_capacity: float = 100.0  # Capacidade de metilação ativa
    homocysteine_level: float = 0.0  # Subproduto (deve ser baixo)
    technical_debt_score: float = 0.0  # Acumulado de decisões adiadas
    last_cycle_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    cycles_completed: int = 0
    successful_methylations: int = 0
    failed_methylations: int = 0
    guardrails_created: int = 0
    
    # Thresholds biológicos adaptados
    HOMOCYSTEINE_ELEVATED_THRESHOLD = 50.0  # Nível crítico
    TECHNICAL_DEBT_CRITICAL = 0.7  # Score crítico
    SAM_E_MINIMUM = 20.0  # Mínimo para operar
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sam_e_level": round(self.sam_e_level, 2),
            "methylation_capacity": round(self.methylation_capacity, 2),
            "homocysteine_level": round(self.homocysteine_level, 2),
            "technical_debt_score": round(self.technical_debt_score, 2),
            "last_cycle_time": self.last_cycle_time,
            "cycles_completed": self.cycles_completed,
            "successful_methylations": self.successful_methylations,
            "failed_methylations": self.failed_methylations,
            "guardrails_created": self.guardrails_created,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MethylationState":
        return cls(
            sam_e_level=data.get("sam_e_level", 100.0),
            methylation_capacity=data.get("methylation_capacity", 100.0),
            homocysteine_level=data.get("homocysteine_level", 0.0),
            technical_debt_score=data.get("technical_debt_score", 0.0),
            last_cycle_time=data.get("last_cycle_time", datetime.now(timezone.utc).isoformat()),
            cycles_completed=data.get("cycles_completed", 0),
            successful_methylations=data.get("successful_methylations", 0),
            failed_methylations=data.get("failed_methylations", 0),
            guardrails_created=data.get("guardrails_created", 0),
        )
    
    def is_homocysteine_elevated(self) -> bool:
        """Detecta homocisteína elevada (technical debt acumulado)."""
        return self.homocysteine_level >= self.HOMOCYSTEINE_ELEVATED_THRESHOLD
    
    def is_technical_debt_critical(self) -> bool:
        """Detecta technical debt crítico."""
        return self.technical_debt_score >= self.TECHNICAL_DEBT_CRITICAL
    
    def can_operate(self) -> bool:
        """Verifica se há SAMe suficiente para operar."""
        return self.sam_e_level >= self.SAM_E_MINIMUM


@dataclass
class MethylationDecision:
    """Decisão tomada pelo engine de metilação."""
    candidate: CandidateSkill
    decision: str  # "production", "guardrail", "deferred", "rejected"
    reason: str
    sam_e_consumed: float = 0.0
    homocysteine_generated: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_name": self.candidate.skill.name,
            "decision": self.decision,
            "reason": self.reason,
            "sam_e_consumed": round(self.sam_e_consumed, 2),
            "homocysteine_generated": round(self.homocysteine_generated, 2),
            "timestamp": self.timestamp,
        }


class MethylationEngine:
    """
    Engine unificado do ciclo de metilação.
    
    Opera em tempo real, processando candidatos do HomocysteinePool
    e tomando decisões baseadas em:
    1. Score da skill (MethylationCycle)
    2. Frequência de erros (TranssulfurationCycle)
    3. Custo metabólico (OpportunityCostDetector)
    4. Estado epigenético (EpigeneticRegistry)
    """
    
    _instance: Optional["MethylationEngine"] = None
    _lock = threading.Lock()
    
    # Constantes metabólicas
    SAM_E_PER_METHYLATION = 5.0  # Custo de SAMe por metilação
    HOMOCYSTEINE_PER_METHYLATION = 1.0  # Geração de homocisteína por metilação
    METHYLATION_CAPACITY_RECOVERY = 2.0  # Recuperação por ciclo
    TECHNICAL_DEBT_PER_DEFERRAL = 0.05  # Debt acumulado por decisão adiada
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.state = MethylationState()
        self._decisions: List[MethylationDecision] = []
        self._rlock = threading.RLock()
        
        # Componentes do ciclo
        self.methylation_cycle = MethylationCycle()
        self.transsulfuration_cycle = TranssulfurationCycle()
        self.opportunity_detector = opportunity_cost_detector
        self.epigenetic_registry = epigenetic_registry
        
        # Carregar estado persistente
        self._load_state()
    
    def _load_state(self):
        """Carrega estado do arquivo JSON."""
        try:
            if METHYLATION_ENGINE_FILE.exists():
                with open(METHYLATION_ENGINE_FILE) as f:
                    data = json.load(f)
                    self.state = MethylationState.from_dict(data.get("state", {}))
                    logger.info("[METHYLATION] Estado carregado: cycles=%d, homocysteine=%.1f",
                              self.state.cycles_completed, self.state.homocysteine_level)
        except Exception as e:
            logger.debug("[METHYLATION] Erro ao carregar estado: %s", e)
    
    def _save_state(self):
        """Salva estado no arquivo JSON."""
        try:
            METHYLATION_ENGINE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(METHYLATION_ENGINE_FILE, "w") as f:
                json.dump({
                    "state": self.state.to_dict(),
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }, f, indent=2)
        except Exception as e:
            logger.debug("[METHYLATION] Erro ao salvar estado: %s", e)
    
    def process_candidate(self, candidate: CandidateSkill) -> MethylationDecision:
        """
        Processa um candidato através do ciclo completo de metilação.
        
        Fluxo:
        1. Verifica capacidade operacional (SAMe disponível)
        2. Avalia custo metabólico (OpportunityCostDetector)
        3. Testa frequência de erros (TranssulfurationCycle)
        4. Valida score (MethylationCycle)
        5. Atualiza estado epigenético
        6. Decide rota: production, guardrail, deferred, rejected
        """
        with self._rlock:
            logger.info("[METHYLATION] Processando '%s' (score=%.2f)",
                       candidate.skill.name, candidate.score)
            
            # 1. Verifica capacidade operacional
            if not self.state.can_operate():
                logger.warning("[METHYLATION] SAMe insuficiente (%.1f < %.1f) — adiando",
                             self.state.sam_e_level, self.state.SAM_E_MINIMUM)
                self.state.technical_debt_score += self.TECHNICAL_DEBT_PER_DEFERRAL
                self._save_state()
                return MethylationDecision(
                    candidate=candidate,
                    decision="deferred",
                    reason=f"SAMe insuficiente ({self.state.sam_e_level:.1f})",
                )
            
            # 2. Avalia custo metabólico
            agent_name = candidate.skill.name
            metabolic_profile = self.opportunity_detector.calculate_opportunity_cost(agent_name)
            
            if metabolic_profile.get("is_parasite"):
                logger.warning("[METHYLATION] '%s' detectado como parasita — rejeitando",
                             agent_name)
                self.state.technical_debt_score += self.TECHNICAL_DEBT_PER_DEFERRAL
                self._save_state()
                return MethylationDecision(
                    candidate=candidate,
                    decision="rejected",
                    reason=f"Parasita detectado (score={metabolic_profile['parasite_score']:.2f})",
                )
            
            # 3. Testa transsulfuração (erros recorrentes)
            if self.transsulfuration_cycle.run(candidate):
                self.state.guardrails_created += 1
                self._consume_resources(success=False)
                decision = MethylationDecision(
                    candidate=candidate,
                    decision="guardrail",
                    reason="Erros recorrentes detectados",
                    sam_e_consumed=self.SAM_E_PER_METHYLATION,
                    homocysteine_generated=self.HOMOCYSTEINE_PER_METHYLATION,
                )
                self._record_decision(decision)
                return decision
            
            # 4. Valida methylation (score threshold)
            if self.methylation_cycle.run(candidate):
                # Sucesso: promove a production
                self.state.successful_methylations += 1
                
                # Atualiza registro epigenético (async)
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                task_hash = f"methylation_{candidate.skill.name}_{self.state.cycles_completed}"
                loop.run_until_complete(
                    self.epigenetic_registry.record_success(
                        agent_id=agent_name,
                        task_hash=task_hash,
                        ivm_score=candidate.score / 100.0 if candidate.score > 1.0 else candidate.score,
                        reward_value=0.8,
                    )
                )
                
                self._consume_resources(success=True)
                decision = MethylationDecision(
                    candidate=candidate,
                    decision="production",
                    reason=f"Score {candidate.score:.2f} acima do threshold",
                    sam_e_consumed=self.SAM_E_PER_METHYLATION,
                    homocysteine_generated=self.HOMOCYSTEINE_PER_METHYLATION,
                )
                self._record_decision(decision)
                return decision
            
            # 5. Score insuficiente — rejeita
            self.state.failed_methylations += 1
            self._consume_resources(success=False)
            
            # Registra falha epigenética
            self.epigenetic_registry.record_failure(
                agent_id=agent_name,
                ivm_score=candidate.score / 100.0 if candidate.score > 1.0 else candidate.score,
            )
            
            decision = MethylationDecision(
                candidate=candidate,
                decision="rejected",
                reason=f"Score {candidate.score:.2f} abaixo do threshold",
                sam_e_consumed=self.SAM_E_PER_METHYLATION,
                homocysteine_generated=self.HOMOCYSTEINE_PER_METHYLATION,
            )
            self._record_decision(decision)
            return decision
    
    def _consume_resources(self, success: bool = True):
        """Consome SAMe e gera homocisteína."""
        self.state.sam_e_level -= self.SAM_E_PER_METHYLATION
        self.state.homocysteine_level += self.HOMOCYSTEINE_PER_METHYLATION
        self.state.cycles_completed += 1
        self.state.last_cycle_time = datetime.now(timezone.utc).isoformat()
        
        # Recupera capacidade gradualmente
        self.state.methylation_capacity = min(
            100.0, 
            self.state.methylation_capacity + self.METHYLATION_CAPACITY_RECOVERY
        )
        
        # Detecta homocisteína elevada
        if self.state.is_homocysteine_elevated():
            logger.warning(
                "[METHYLATION] ⚠️ HOMOCISTEÍNA ELEVADA (%.1f ≥ %.1f) — Technical debt acumulado!",
                self.state.homocysteine_level,
                self.state.HOMOCYSTEINE_ELEVATED_THRESHOLD
            )
            # Aumenta technical debt proporcionalmente
            excess = self.state.homocysteine_level - self.state.HOMOCYSTEINE_ELEVATED_THRESHOLD
            self.state.technical_debt_score += min(0.2, excess / 100.0)
        
        self._save_state()
    
    def _record_decision(self, decision: MethylationDecision):
        """Registra decisão no histórico."""
        self._decisions.append(decision)
        # Mantém apenas últimas 1000 decisões em memória
        if len(self._decisions) > 1000:
            self._decisions = self._decisions[-1000:]
    
    def get_state(self) -> MethylationState:
        """Retorna estado atual do engine."""
        with self._rlock:
            return self.state
    
    def get_recent_decisions(self, limit: int = 50) -> List[MethylationDecision]:
        """Retorna decisões recentes."""
        with self._rlock:
            return self._decisions[-limit:]
    
    def reset_homocysteine(self):
        """
        Reseta homocisteína através de 'transsulfuração forçada'.
        Chamado quando technical debt atinge nível crítico.
        """
        with self._rlock:
            if self.state.is_homocysteine_elevated():
                logger.info("[METHYLATION] Resetando homocisteína elevada (%.1f → 0)",
                          self.state.homocysteine_level)
                self.state.homocysteine_level = 0.0
                self.state.technical_debt_score = max(
                    0.0, 
                    self.state.technical_debt_score - 0.3
                )
                self._save_state()
                return True
            return False
    
    def replenish_sam_e(self, amount: float = 50.0):
        """Reabastece SAMe (recursos metabólicos)."""
        with self._rlock:
            old_level = self.state.sam_e_level
            self.state.sam_e_level = min(100.0, self.state.sam_e_level + amount)
            logger.info("[METHYLATION] SAMe reabastecido: %.1f → %.1f (+%.1f)",
                       old_level, self.state.sam_e_level, amount)
            self._save_state()
    
    def get_health_report(self) -> Dict[str, Any]:
        """
        Gera relatório de saúde metabólica.
        
        Returns:
            {
                "status": "healthy" | "warning" | "critical",
                "sam_e_level": float,
                "homocysteine_level": float,
                "technical_debt_score": float,
                "methylation_capacity": float,
                "recommendations": List[str]
            }
        """
        with self._rlock:
            recommendations = []
            status = "healthy"
            
            # Verifica SAMe
            if self.state.sam_e_level < self.state.SAM_E_MINIMUM:
                recommendations.append("CRÍTICO: Reabastecer SAMe urgentemente")
                status = "critical"
            elif self.state.sam_e_level < 50.0:
                recommendations.append("AVISO: SAMe baixo — considerar reabastecimento")
                if status != "critical":
                    status = "warning"
            
            # Verifica homocisteína
            if self.state.is_homocysteine_elevated():
                recommendations.append(
                    f"CRÍTICO: Homocisteína elevada ({self.state.homocysteine_level:.1f}) — "
                    "executar reset ou aumentar transsulfuração"
                )
                status = "critical"
            
            # Verifica technical debt
            if self.state.is_technical_debt_critical():
                recommendations.append(
                    f"CRÍTICO: Technical debt alto ({self.state.technical_debt_score:.2f}) — "
                    "revisar decisões adiadas"
                )
                status = "critical"
            
            # Verifica eficiência
            total = self.state.successful_methylations + self.state.failed_methylations
            if total > 0:
                efficiency = self.state.successful_methylations / total
                if efficiency < 0.5:
                    recommendations.append(
                        f"AVISO: Eficiência baixa ({efficiency:.1%}) — "
                        "ajustar thresholds de seleção"
                    )
                    if status == "healthy":
                        status = "warning"
            
            return {
                "status": status,
                "sam_e_level": round(self.state.sam_e_level, 2),
                "homocysteine_level": round(self.state.homocysteine_level, 2),
                "technical_debt_score": round(self.state.technical_debt_score, 2),
                "methylation_capacity": round(self.state.methylation_capacity, 2),
                "cycles_completed": self.state.cycles_completed,
                "success_rate": round(
                    self.state.successful_methylations / max(1, total), 2
                ),
                "recommendations": recommendations,
            }


# Singleton global
methylation_engine = MethylationEngine()
