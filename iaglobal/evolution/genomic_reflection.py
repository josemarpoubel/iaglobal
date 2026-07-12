# ============================================================
# ARQUIVO: iaglobal/evolution/genomic_reflection.py
# REFLEXÃO GENÔMICA: "O passado é o ativo mais valioso..."
# ============================================================
"""GenomicReflection — ResultAgent propõe mutações de DNA à BanditPolicy.

A Lei da Memória Imunológica estabelece que erros do passado são o ativo
mais valioso do sistema. Este módulo implementa:

1. **Análise de Performance** — ResultAgent analisa resultados de execuções
2. **Proposta de Mutação** — Sugere mudanças no DNA de agentes/skills
3. **Validação com BanditPolicy** — Propostas são avaliadas pelo Bandit
4. **Implementação de Mutação** — Mutações aprovadas são aplicadas

Operação:
- ResultAgent coleta métricas de execuções passadas
- Identifica padrões de sucesso/fracasso
- Propõe mutações de traits para melhorar fitness
- BanditPolicy avalia impacto esperado da mutação
- Mutações aprovadas são registradas no FusionEngine

Padrão Singleton — existe um único GenomicReflection para todo o ecossistema.

Exemplo de uso assíncrono:
    ```python
    from iaglobal.evolution.genomic_reflection import genomic_reflection
    
    # ResultAgent analisa performance
    analysis = await genomic_reflection.analyze_performance_async(
        agent_id="coder_agent",
        execution_history=executions,
    )
    
    # Propor mutações
    mutations = await genomic_reflection.propose_mutations_async(
        agent_id="coder_agent",
        analysis=analysis,
    )
    
    # Validar com BanditPolicy
    for mutation in mutations:
        approved = await genomic_reflection.validate_with_bandit_async(mutation)
        if approved:
            await genomic_reflection.apply_mutation_async(mutation)
    ```
"""

from __future__ import annotations

import asyncio
import logging
import hashlib
import threading
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from enum import Enum

from iaglobal.utils.logger import get_logger
from iaglobal.evolution.fusion_engine import fusion_engine, AgentDNA, DNATrait

logger = get_logger("iaglobal.genomic_reflection")


class MutationType(Enum):
    """Tipos de mutação genômica."""
    TRAIT_ENHANCEMENT = "trait_enhancement"  # Melhorar trait existente
    TRAIT_SUPPRESSION = "trait_suppression"  # Reduzir/silenciar trait
    TRAIT_ADDITION = "trait_addition"  # Adicionar novo trait
    MARKER_ADDITION = "marker_addition"  # Adicionar compatibility marker
    FITNESS_ADJUSTMENT = "fitness_adjustment"  # Ajustar fitness score


class MutationImpact(Enum):
    """Impacto esperado de uma mutação."""
    LOW = "low"  # Mudança sutil (< 10%)
    MEDIUM = "medium"  # Mudança moderada (10-30%)
    HIGH = "high"  # Mudança drástica (> 30%)


@dataclass
class ExecutionMetrics:
    """Métricas de uma execução de agente."""
    execution_id: str
    agent_id: str
    timestamp: float
    success: bool
    latency_ms: float
    fitness_score: float
    traits_used: Dict[str, float]  # trait → expression_level
    outcome_quality: float  # 0.0 → 1.0


@dataclass
class PerformanceAnalysis:
    """Análise de performance de um agente."""
    agent_id: str
    total_executions: int
    success_rate: float
    avg_fitness: float
    avg_latency_ms: float
    avg_outcome_quality: float
    best_traits: List[str]  # Traits com melhor performance
    worst_traits: List[str]  # Traits com pior performance
    patterns: Dict[str, Any]  # Padrões detectados
    recommendations: List[str]


@dataclass
class MutationProposal:
    """Proposta de mutação genômica."""
    mutation_id: str
    agent_id: str
    mutation_type: MutationType
    target_trait: Optional[str]
    proposed_change: Any  # Valor/ação proposta
    expected_impact: MutationImpact
    confidence_score: float  # 0.0 → 1.0 (confiança na proposta)
    rationale: str  # Justificativa da mutação
    evidence: List[str]  # Evidências que suportam a proposta
    status: str = "pending"  # pending, approved, rejected, applied


class GenomicReflection:
    """Reflexão Genômica — Proposta de Mutações à BanditPolicy.
    
    A Lei da Memória Imunológica exige aprendizado com erros passados.
    Este módulo:
    
    1. Analisa performance histórica de agentes
    2. Identifica padrões de sucesso/fracasso
    3. Propõe mutações de DNA baseadas em evidências
    4. Valida propostas com BanditPolicy
    5. Aplica mutações aprovadas
    
    Critérios de Proposta:
    
    **Trait Enhancement** (melhorar trait):
    - Trait está correlacionado com sucesso (> 0.7)
    - Expression level atual < 0.8
    - Proposta: aumentar para 0.9
    
    **Trait Suppression** (reduzir trait):
    - Trait está correlacionado com fracasso (> 0.6)
    - Expression level atual > 0.5
    - Proposta: reduzir para 0.3
    
    **Trait Addition** (adicionar trait):
    - Agente não tem trait crítico para seu tipo
    - Traits similares em agentes bem-sucedidos
    - Proposta: adicionar com expression 0.5
    
    **Validação com BanditPolicy**:
    - Mutação deve melhorar fitness esperado em > 5%
    - Não deve reduzir diversidade genética
    - Deve manter compatibilidade com pais
    
    Padrão Singleton — existe um único GenomicReflection para todo o ecossistema.
    """

    _instance: Optional["GenomicReflection"] = None
    _lock = threading.Lock()

    # Limiares configuráveis (epigenéticos)
    _SUCCESS_CORRELATION_THRESHOLD = 0.7  # Correlação mínima para enhancement
    _FAILURE_CORRELATION_THRESHOLD = 0.6  # Correlação mínima para suppression
    _MIN_FITNESS_IMPROVEMENT = 0.05  # 5% de melhoria mínima esperada
    _CONFIDENCE_MINIMUM = 0.6  # Confiança mínima para propor mutação

    def __new__(cls, *args, **kwargs) -> "GenomicReflection":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._execution_history: Dict[str, List[ExecutionMetrics]] = {}  # agent_id → executions
        self._mutation_proposals: Dict[str, MutationProposal] = {}
        self._applied_mutations: List[MutationProposal] = []
        self._rlock = threading.RLock()
        
        # Callbacks para integração com BanditPolicy
        self._bandit_validator: Optional[Callable] = None
        
        logger.info(
            "[GenomicReflection] Reflexão Genômica initialized | "
            "success_threshold=%.2f | confidence_min=%.2f",
            self._SUCCESS_CORRELATION_THRESHOLD,
            self._CONFIDENCE_MINIMUM,
        )

    def register_execution(self, metrics: ExecutionMetrics) -> None:
        """
        Registra execução de agente para análise futura.
        
        Args:
            metrics: Métricas da execução
        """
        with self._rlock:
            if metrics.agent_id not in self._execution_history:
                self._execution_history[metrics.agent_id] = []
            
            self._execution_history[metrics.agent_id].append(metrics)
            
            # Limitar histórico por agente (últimas 100 execuções)
            if len(self._execution_history[metrics.agent_id]) > 100:
                self._execution_history[metrics.agent_id] = \
                    self._execution_history[metrics.agent_id][-100:]

    async def analyze_performance_async(
        self,
        agent_id: str,
        execution_history: Optional[List[ExecutionMetrics]] = None,
    ) -> PerformanceAnalysis:
        """
        Analisa performance de um agente.
        
        Args:
            agent_id: ID do agente
            execution_history: Histórico opcional (usa interno se None)
            
        Returns:
            PerformanceAnalysis: Análise completa
        """
        with self._rlock:
            if execution_history is None:
                history = self._execution_history.get(agent_id, [])
            else:
                history = execution_history
            
            if not history:
                return PerformanceAnalysis(
                    agent_id=agent_id,
                    total_executions=0,
                    success_rate=0.0,
                    avg_fitness=0.0,
                    avg_latency_ms=0.0,
                    avg_outcome_quality=0.0,
                    best_traits=[],
                    worst_traits=[],
                    patterns={},
                    recommendations=[],
                )
            
            # Calcular métricas agregadas
            total = len(history)
            successes = sum(1 for e in history if e.success)
            success_rate = successes / total
            
            avg_fitness = sum(e.fitness_score for e in history) / total
            avg_latency = sum(e.latency_ms for e in history) / total
            avg_quality = sum(e.outcome_quality for e in history) / total
            
            # Analisar traits
            trait_performance = self._analyze_trait_performance(history)
            
            best_traits = [
                trait for trait, perf in trait_performance.items()
                if perf["correlation_with_success"] > self._SUCCESS_CORRELATION_THRESHOLD
            ]
            
            worst_traits = [
                trait for trait, perf in trait_performance.items()
                if perf["correlation_with_failure"] > self._FAILURE_CORRELATION_THRESHOLD
            ]
            
            # Detectar padrões
            patterns = self._detect_patterns(history, trait_performance)
            
            # Gerar recomendações
            recommendations = self._generate_recommendations(
                agent_id, success_rate, best_traits, worst_traits, patterns
            )
            
            return PerformanceAnalysis(
                agent_id=agent_id,
                total_executions=total,
                success_rate=round(success_rate, 3),
                avg_fitness=round(avg_fitness, 3),
                avg_latency_ms=round(avg_latency, 2),
                avg_outcome_quality=round(avg_quality, 3),
                best_traits=best_traits,
                worst_traits=worst_traits,
                patterns=patterns,
                recommendations=recommendations,
            )

    def _analyze_trait_performance(
        self,
        history: List[ExecutionMetrics],
    ) -> Dict[str, Dict[str, float]]:
        """Analisa performance de cada trait."""
        trait_data = {}
        
        for execution in history:
            for trait, level in execution.traits_used.items():
                if trait not in trait_data:
                    trait_data[trait] = {
                        "success_count": 0,
                        "failure_count": 0,
                        "total_level": 0.0,
                        "occurrences": 0,
                    }
                
                data = trait_data[trait]
                data["occurrences"] += 1
                data["total_level"] += level
                
                if execution.success:
                    data["success_count"] += 1
                else:
                    data["failure_count"] += 1
        
        # Calcular correlações
        result = {}
        for trait, data in trait_data.items():
            total = data["success_count"] + data["failure_count"]
            if total > 0:
                success_corr = data["success_count"] / total
                failure_corr = data["failure_count"] / total
                avg_level = data["total_level"] / data["occurrences"]
                
                result[trait] = {
                    "correlation_with_success": success_corr,
                    "correlation_with_failure": failure_corr,
                    "avg_expression_level": avg_level,
                }
        
        return result

    def _detect_patterns(
        self,
        history: List[ExecutionMetrics],
        trait_performance: Dict[str, Dict[str, float]],
    ) -> Dict[str, Any]:
        """Detecta padrões nas execuções."""
        patterns = {}
        
        # Padrão 1: Sucesso consistente
        recent_successes = sum(1 for e in history[-10:] if e.success)
        if recent_successes >= 8:
            patterns["consistent_success"] = True
        
        # Padrão 2: Degradação de performance
        if len(history) >= 20:
            first_half_avg = sum(e.fitness_score for e in history[:10]) / 10
            second_half_avg = sum(e.fitness_score for e in history[-10:]) / 10
            if second_half_avg < first_half_avg * 0.8:
                patterns["performance_degradation"] = True
        
        # Padrão 3: Trait dominante
        for trait, perf in trait_performance.items():
            if perf["correlation_with_success"] > 0.9:
                patterns[f"dominant_trait_{trait}"] = True
        
        return patterns

    def _generate_recommendations(
        self,
        agent_id: str,
        success_rate: float,
        best_traits: List[str],
        worst_traits: List[str],
        patterns: Dict[str, Any],
    ) -> List[str]:
        """Gera recomendações baseadas na análise."""
        recommendations = []
        
        if success_rate < 0.5:
            recommendations.append(
                f"Sucesso baixo ({success_rate:.1%}). Considerar mutações drásticas."
            )
        
        if best_traits:
            recommendations.append(
                f"Reforçar traits de sucesso: {', '.join(best_traits)}"
            )
        
        if worst_traits:
            recommendations.append(
                f"Reduzir/silenciar traits problemáticos: {', '.join(worst_traits)}"
            )
        
        if "performance_degradation" in patterns:
            recommendations.append(
                "Degradação detectada. Intervenção urgente necessária."
            )
        
        return recommendations

    async def propose_mutations_async(
        self,
        agent_id: str,
        analysis: PerformanceAnalysis,
    ) -> List[MutationProposal]:
        """
        Propõe mutações baseadas na análise de performance.
        
        Args:
            agent_id: ID do agente
            analysis: Análise de performance
            
        Returns:
            Lista de MutationProposal
        """
        proposals = []
        
        # Obter DNA atual do agente
        dna = fusion_engine._agent_dnas.get(agent_id)
        
        # Proposta 1: Trait Enhancement para best_traits
        for trait in analysis.best_traits:
            if dna and trait in dna.traits:
                current_level = dna.traits[trait].expression_level
                if current_level < 0.8:
                    proposal = MutationProposal(
                        mutation_id=self._generate_mutation_id(agent_id, trait),
                        agent_id=agent_id,
                        mutation_type=MutationType.TRAIT_ENHANCEMENT,
                        target_trait=trait,
                        proposed_change=0.9,  # Aumentar para 90%
                        expected_impact=MutationImpact.MEDIUM,
                        confidence_score=0.8,
                        rationale=f"Trait {trait} correlacionado com sucesso ({analysis.success_rate:.1%})",
                        evidence=[f"Best trait identified in {analysis.total_executions} executions"],
                    )
                    proposals.append(proposal)
        
        # Proposta 2: Trait Suppression para worst_traits
        for trait in analysis.worst_traits:
            if dna and trait in dna.traits:
                current_level = dna.traits[trait].expression_level
                if current_level > 0.3:
                    proposal = MutationProposal(
                        mutation_id=self._generate_mutation_id(agent_id, trait),
                        agent_id=agent_id,
                        mutation_type=MutationType.TRAIT_SUPPRESSION,
                        target_trait=trait,
                        proposed_change=0.3,  # Reduzir para 30%
                        expected_impact=MutationImpact.MEDIUM,
                        confidence_score=0.7,
                        rationale=f"Trait {trait} correlacionado com fracasso",
                        evidence=[f"Worst trait identified in {analysis.total_executions} executions"],
                    )
                    proposals.append(proposal)
        
        # Proposta 3: Trait Addition se agente tem baixa diversidade
        if dna and len(dna.traits) < 5:
            # Sugerir traits comuns em agentes similares
            common_traits = self._identify_common_traits(agent_id)
            for trait in common_traits[:2]:  # Máximo 2 traits novos
                if dna and trait not in dna.traits:
                    proposal = MutationProposal(
                        mutation_id=self._generate_mutation_id(agent_id, trait),
                        agent_id=agent_id,
                        mutation_type=MutationType.TRAIT_ADDITION,
                        target_trait=trait,
                        proposed_change={"expression_level": 0.5, "value": "default"},
                        expected_impact=MutationImpact.HIGH,
                        confidence_score=0.6,
                        rationale=f"Trait {trait} comum em agentes similares",
                        evidence=[f"Missing trait for agent type {dna.agent_type}"],
                    )
                    proposals.append(proposal)
        
        # Registrar propostas
        with self._rlock:
            for proposal in proposals:
                self._mutation_proposals[proposal.mutation_id] = proposal
        
        return proposals

    def _generate_mutation_id(self, agent_id: str, trait: str) -> str:
        """Gera ID único para mutação."""
        data = f"{agent_id}:{trait}:{time.time()}"
        return hashlib.sha3_256(data.encode()).hexdigest()[:16]

    def _identify_common_traits(self, agent_id: str) -> List[str]:
        """Identifica traits comuns em agentes similares."""
        # Obter tipo do agente
        dna = fusion_engine._agent_dnas.get(agent_id)
        if not dna:
            return []
        
        agent_type = dna.agent_type
        
        # Encontrar agentes do mesmo tipo
        similar_agents = [
            (aid, adna)
            for aid, adna in fusion_engine._agent_dnas.items()
            if adna.agent_type == agent_type and aid != agent_id
        ]
        
        # Contar traits
        trait_counts = {}
        for _, adna in similar_agents:
            for trait in adna.traits.keys():
                trait_counts[trait] = trait_counts.get(trait, 0) + 1
        
        # Retornar traits mais comuns que o agente atual não tem
        current_traits = set(dna.traits.keys()) if dna else set()
        common_missing = [
            trait for trait, count in sorted(trait_counts.items(), key=lambda x: x[1], reverse=True)
            if trait not in current_traits
        ]
        
        return common_missing[:5]

    async def validate_with_bandit_async(
        self,
        proposal: MutationProposal,
        validator: Optional[Callable] = None,
    ) -> bool:
        """
        Valida mutação com BanditPolicy.
        
        Args:
            proposal: Proposta de mutação
            validator: Função de validação opcional (default: bandit_validator)
            
        Returns:
            bool: True se aprovada
        """
        if validator is None:
            validator = self._bandit_validator
        
        if validator is None:
            # Fallback: validação simples baseada em confiança
            approved = proposal.confidence_score > self._CONFIDENCE_MINIMUM
            logger.info(
                "[GenomicReflection] Validação fallback: %s → %s",
                proposal.mutation_id,
                "aprovada" if approved else "rejeitada",
            )
            return approved
        
        # Chamar validator externo (BanditPolicy)
        try:
            result = await asyncio.to_thread(
                validator, proposal
            )
            return result
        except Exception as e:
            logger.error(
                "[GenomicReflection] Erro na validação: %s", e
            )
            return False

    async def apply_mutation_async(self, proposal: MutationProposal) -> bool:
        """
        Aplica mutação aprovada ao DNA do agente.
        
        Args:
            proposal: Proposta aprovada
            
        Returns:
            bool: True se aplicada com sucesso
        """
        if proposal.status != "approved":
            logger.warning(
                "[GenomicReflection] Tentativa de aplicar mutação não aprovada: %s",
                proposal.mutation_id,
            )
            return False
        
        dna = fusion_engine._agent_dnas.get(proposal.agent_id)
        if not dna:
            logger.error(
                "[GenomicReflection] DNA não encontrado: %s",
                proposal.agent_id,
            )
            return False
        
        with self._rlock:
            try:
                if proposal.mutation_type == MutationType.TRAIT_ENHANCEMENT:
                    if proposal.target_trait in dna.traits:
                        dna.traits[proposal.target_trait].expression_level = \
                            proposal.proposed_change
                
                elif proposal.mutation_type == MutationType.TRAIT_SUPPRESSION:
                    if proposal.target_trait in dna.traits:
                        dna.traits[proposal.target_trait].expression_level = \
                            proposal.proposed_change
                
                elif proposal.mutation_type == MutationType.TRAIT_ADDITION:
                    if proposal.target_trait:
                        dna.traits[proposal.target_trait] = DNATrait(
                            trait_name=proposal.target_trait,
                            trait_value=proposal.proposed_change.get("value", "default"),
                            expression_level=proposal.proposed_change.get("expression_level", 0.5),
                            inherited_from="mutation",
                        )
                
                # Atualizar status
                proposal.status = "applied"
                self._applied_mutations.append(proposal)
                
                logger.info(
                    "[GenomicReflection] ✅ Mutação aplicada: %s → %s (%s)",
                    proposal.agent_id,
                    proposal.mutation_type.value,
                    proposal.target_trait or "N/A",
                )
                
                return True
                
            except Exception as e:
                logger.error(
                    "[GenomicReflection] Erro ao aplicar mutação: %s", e
                )
                return False

    def set_bandit_validator(self, validator: Callable) -> None:
        """
        Define função de validação da BanditPolicy.
        
        Args:
            validator: Função(proposal) → bool
        """
        with self._rlock:
            self._bandit_validator = validator
            logger.info("[GenomicReflection] Bandit validator configurado")

    def get_mutation_proposals(
        self,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[MutationProposal]:
        """
        Retorna propostas de mutação.
        
        Args:
            agent_id: Filtrar por agente (opcional)
            status: Filtrar por status (opcional)
            
        Returns:
            Lista de propostas filtradas
        """
        with self._rlock:
            proposals = list(self._mutation_proposals.values())
            
            if agent_id:
                proposals = [p for p in proposals if p.agent_id == agent_id]
            
            if status:
                proposals = [p for p in proposals if p.status == status]
            
            return proposals

    def get_applied_mutations(self, limit: int = 20) -> List[MutationProposal]:
        """Retorna últimas mutações aplicadas."""
        with self._rlock:
            return self._applied_mutations[-limit:]

    def get_reflection_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de reflexões/mutações."""
        with self._rlock:
            total_proposals = len(self._mutation_proposals)
            approved = sum(
                1 for p in self._mutation_proposals.values()
                if p.status == "approved"
            )
            applied = len(self._applied_mutations)
            
            return {
                "total_proposals": total_proposals,
                "approved_count": approved,
                "rejected_count": total_proposals - approved - applied,
                "applied_count": applied,
                "agents_analyzed": len(self._execution_history),
                "total_executions": sum(
                    len(execs) for execs in self._execution_history.values()
                ),
            }

    def reset(self) -> None:
        """Reseta estado (para testes)."""
        with self._rlock:
            self._execution_history.clear()
            self._mutation_proposals.clear()
            self._applied_mutations.clear()
            self._bandit_validator = None
            logger.info("[GenomicReflection] ✅ Estado resetado")


# Singleton global
genomic_reflection = GenomicReflection()