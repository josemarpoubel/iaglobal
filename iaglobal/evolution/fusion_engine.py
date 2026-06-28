# ============================================================
# ARQUIVO: iaglobal/evolution/fusion_engine.py
# RESSONÂNCIA DE DNA: "O todo é maior que a soma das partes..."
# ============================================================
"""FusionEngine — Síntese de Agentes Híbridos via Ressonância de Linhagem.

A Fusão de DNA permite criar agentes híbridos combinando características
de múltiplos agentes parentais, similar à fusão celular na biologia.

Este módulo implementa:

1. **Ressonância de DNA** — Detecta compatibilidade entre agentes
2. **Fusão Controlada** — Combina skills/traits de múltiplos pais
3. **Validação de Híbrido** — Garante que híbrido é viável
4. **Registro de Linhagem** — Rastreia ancestralidade do híbrido

Operação:
- Analisa DNA de agentes candidatos à fusão
- Calcula ressonância (compatibilidade) entre DNAs
- Sintetiza novo agente com traits combinados
- Registra linhagem no Obsidian (AncestryTree)
- Valida viabilidade do híbrido antes de spawnar

Padrão Singleton — existe um único FusionEngine para todo o ecossistema.

Exemplo de uso assíncrono:
    ```python
    from iaglobal.evolution.fusion_engine import fusion_engine
    
    # Calcular ressonância entre dois agentes
    ressonancia = await fusion_engine.calculate_dna_resonance_async(
        agent_a="coder_agent",
        agent_b="critic_agent",
    )
    
    if ressonancia["compatible"]:
        # Criar híbrido
        hybrid = await fusion_engine.fuse_agents_async(
            parent_ids=["coder_agent", "critic_agent"],
            hybrid_name="coder_critic_hybrid",
        )
        
        # Registrar linhagem no Obsidian
        await fusion_engine.register_lineage_async(
            hybrid_id=hybrid["id"],
            parents=["coder_agent", "critic_agent"],
        )
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
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.fusion_engine")


@dataclass
class DNATrait:
    """Trait individual de um DNA de agente."""
    trait_name: str
    trait_value: Any
    expression_level: float  # 0.0 (silenciado) → 1.0 (máxima expressão)
    inherited_from: str  # ID do agente parental


@dataclass
class AgentDNA:
    """DNA completo de um agente."""
    agent_id: str
    agent_type: str
    generation: int
    traits: Dict[str, DNATrait] = field(default_factory=dict)
    lineage_hash: str = ""
    created_at: float = field(default_factory=lambda: time.time())
    fitness_score: float = 0.0
    compatibility_markers: List[str] = field(default_factory=list)


@dataclass
class FusionResult:
    """Resultado de uma fusão de agentes."""
    success: bool
    hybrid_id: str
    hybrid_dna: Optional[AgentDNA]
    parents: List[str]
    resonance_score: float
    viability_score: float
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class LineageRecord:
    """Registro de linhagem no AncestryTree."""
    hybrid_id: str
    parents: List[str]
    fusion_timestamp: float
    resonance_score: float
    generation: int
    traits_inherited: Dict[str, str]  # trait → parent_id
    obsidian_note_id: Optional[str] = None


class FusionEngine:
    """Motor de Fusão de Agentes — Ressonância de DNA.
    
    A Fusão de DNA permite criar agentes híbridos combinando características
    de múltiplos agentes parentais. Este módulo:
    
    1. Analisa DNA de agentes candidatos
    2. Calcula ressonância (compatibilidade genética)
    3. Sintetiza híbrido com traits combinados
    4. Registra linhagem no Obsidian (AncestryTree)
    5. Valida viabilidade antes de spawnar
    
    Fórmula de Ressonância:
        R = (C × 0.4) + (D × 0.3) + (F × 0.3)
        
        Onde:
        C = Compatibilidade de markers (0.0 → 1.0)
        D = Diversidade de traits (0.0 → 1.0)
        F = Fitness médio dos pais (0.0 → 1.0)
        
        R ≥ 0.6 → Compatível para fusão
        R < 0.6 → Incompatível (rejeitar fusão)
    
    Padrão Singleton — existe um único FusionEngine para todo o ecossistema.
    """

    _instance: Optional["FusionEngine"] = None
    _lock = threading.Lock()

    # Limiares configuráveis (epigenéticos)
    _RESONANCE_THRESHOLD = 0.6  # ≥ 60% = compatível
    _VIABILITY_MIN_SCORE = 0.5  # Viabilidade mínima para spawnar
    _MAX_PARENTS = 4  # Máximo de pais por fusão
    _INHERITANCE_DOMINANCE = 0.6  # 60% de chance de herdar trait dominante

    def __new__(cls, *args, **kwargs) -> "FusionEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._agent_dnas: Dict[str, AgentDNA] = {}
        self._lineage_records: List[LineageRecord] = []
        self._rlock = threading.RLock()
        self._fusion_count = 0
        self._failed_fusions = 0
        
        logger.info(
            "[FusionEngine] Motor de Fusão initialized | "
            "resonance_threshold=%.2f | max_parents=%d",
            self._RESONANCE_THRESHOLD,
            self._MAX_PARENTS,
        )

    def register_agent_dna(
        self,
        agent_id: str,
        agent_type: str,
        traits: Dict[str, Any],
        generation: int = 1,
        fitness_score: float = 0.5,
        compatibility_markers: Optional[List[str]] = None,
    ) -> str:
        """
        Registra DNA de um agente para futura fusão.
        
        Args:
            agent_id: ID único do agente
            agent_type: Tipo/função do agente
            traits: Dicionário de traits (nome → valor)
            generation: Geração do agente
            fitness_score: Score de fitness atual
            compatibility_markers: Markers para compatibilidade
            
        Returns:
            str: lineage_hash do DNA registrado
        """
        now = time.time()
        
        # Criar traits padronizadas
        dna_traits = {}
        for trait_name, trait_value in traits.items():
            dna_traits[trait_name] = DNATrait(
                trait_name=trait_name,
                trait_value=trait_value,
                expression_level=0.8,  # Default alto
                inherited_from="origin",
            )
        
        # Calcular lineage_hash
        lineage_data = f"{agent_id}:{agent_type}:{generation}:{sorted(traits.keys())}"
        lineage_hash = hashlib.sha3_512(lineage_data.encode()).hexdigest()[:32]
        
        with self._rlock:
            self._agent_dnas[agent_id] = AgentDNA(
                agent_id=agent_id,
                agent_type=agent_type,
                generation=generation,
                traits=dna_traits,
                lineage_hash=lineage_hash,
                created_at=now,
                fitness_score=fitness_score,
                compatibility_markers=compatibility_markers or [],
            )
        
        logger.debug(
            "[FusionEngine] DNA registrado: %s (type=%s, generation=%d, hash=%s)",
            agent_id, agent_type, generation, lineage_hash[:8],
        )
        
        return lineage_hash

    def calculate_dna_resonance(
        self,
        agent_a: str,
        agent_b: str,
    ) -> Dict[str, Any]:
        """
        Calcula ressonância de DNA entre dois agentes.
        
        Args:
            agent_a: ID do primeiro agente
            agent_b: ID do segundo agente
            
        Returns:
            Dict[str, Any]: {
                "resonance_score": float,
                "compatible": bool,
                "compatibility_breakdown": {...},
                "warnings": [...]
            }
        """
        with self._rlock:
            dna_a = self._agent_dnas.get(agent_a)
            dna_b = self._agent_dnas.get(agent_b)
            
            if not dna_a or not dna_b:
                return {
                    "resonance_score": 0.0,
                    "compatible": False,
                    "error": "DNA not found for one or both agents",
                }
            
            # Calcular componentes
            # C = Compatibilidade de markers
            markers_a = set(dna_a.compatibility_markers)
            markers_b = set(dna_b.compatibility_markers)
            
            if markers_a or markers_b:
                intersection = len(markers_a & markers_b)
                union = len(markers_a | markers_b)
                compatibility = intersection / union if union > 0 else 0.5
            else:
                compatibility = 0.5  # Default se sem markers
            
            # D = Diversidade de traits
            traits_a = set(dna_a.traits.keys())
            traits_b = set(dna_b.traits.keys())
            unique_traits = len(traits_a ^ traits_b)  # XOR = únicos
            total_traits = len(traits_a | traits_b)
            diversity = unique_traits / total_traits if total_traits > 0 else 0.0
            
            # F = Fitness médio
            avg_fitness = (dna_a.fitness_score + dna_b.fitness_score) / 2
            
            # Calcular ressonância
            # R = (C × 0.4) + (D × 0.3) + (F × 0.3)
            resonance = (compatibility * 0.4) + (diversity * 0.3) + (avg_fitness * 0.3)
            
            compatible = resonance >= self._RESONANCE_THRESHOLD
            
            warnings = []
            if compatibility < 0.3:
                warnings.append("Baixa compatibilidade de markers")
            if diversity > 0.8:
                warnings.append("Alta diversidade pode causar instabilidade")
            if avg_fitness < 0.4:
                warnings.append("Fitness parental baixo")
            
            return {
                "resonance_score": round(resonance, 3),
                "compatible": compatible,
                "compatibility_breakdown": {
                    "compatibility": round(compatibility, 3),
                    "diversity": round(diversity, 3),
                    "avg_fitness": round(avg_fitness, 3),
                },
                "warnings": warnings,
            }

    async def fuse_agents_async(
        self,
        parent_ids: List[str],
        hybrid_name: str,
        force: bool = False,
    ) -> FusionResult:
        """
        Funde múltiplos agentes em um híbrido.
        
        Args:
            parent_ids: Lista de IDs de agentes parentais
            hybrid_name: Nome do agente híbrido resultante
            force: Se True, ignora threshold de ressonância
            
        Returns:
            FusionResult: Resultado da fusão
        """
        if len(parent_ids) > self._MAX_PARENTS:
            return FusionResult(
                success=False,
                hybrid_id="",
                hybrid_dna=None,
                parents=parent_ids,
                resonance_score=0.0,
                viability_score=0.0,
                errors=[f"Máximo de {self._MAX_PARENTS} pais permitido"],
            )
        
        # Validar DNAs parentais
        with self._rlock:
            parent_dnas = []
            for pid in parent_ids:
                dna = self._agent_dnas.get(pid)
                if not dna:
                    return FusionResult(
                        success=False,
                        hybrid_id="",
                        hybrid_dna=None,
                        parents=parent_ids,
                        resonance_score=0.0,
                        viability_score=0.0,
                        errors=[f"DNA não encontrado: {pid}"],
                    )
                parent_dnas.append(dna)
        
        # Calcular ressonância média entre todos os pais
        resonance_scores = []
        for i, pid_a in enumerate(parent_ids):
            for pid_b in parent_ids[i+1:]:
                res = await asyncio.to_thread(self.calculate_dna_resonance, pid_a, pid_b)
                resonance_scores.append(res["resonance_score"])
        
        avg_resonance = sum(resonance_scores) / len(resonance_scores) if resonance_scores else 0.0
        
        if not force and avg_resonance < self._RESONANCE_THRESHOLD:
            with self._rlock:
                self._failed_fusions += 1
            
            return FusionResult(
                success=False,
                hybrid_id="",
                hybrid_dna=None,
                parents=parent_ids,
                resonance_score=avg_resonance,
                viability_score=0.0,
                errors=[f"Ressonância {avg_resonance:.2f} abaixo do threshold {self._RESONANCE_THRESHOLD}"],
            )
        
        # Sintetizar híbrido
        hybrid_dna = await asyncio.to_thread(
            self._synthesize_hybrid,
            hybrid_name,
            parent_dnas,
        )
        
        # Calcular viabilidade
        viability = await asyncio.to_thread(
            self._calculate_viability,
            hybrid_dna,
        )
        
        if viability < self._VIABILITY_MIN_SCORE:
            with self._rlock:
                self._failed_fusions += 1
            
            return FusionResult(
                success=False,
                hybrid_id="",
                hybrid_dna=hybrid_dna,
                parents=parent_ids,
                resonance_score=avg_resonance,
                viability_score=viability,
                errors=[f"Viabilidade {viability:.2f} abaixo do mínimo {self._VIABILITY_MIN_SCORE}"],
            )
        
        # Sucesso!
        with self._rlock:
            self._fusion_count += 1
            self._agent_dnas[hybrid_name] = hybrid_dna
        
        logger.info(
            "[FusionEngine] ✅ Híbrido criado: %s (pais=%d, ressonância=%.2f, viabilidade=%.2f)",
            hybrid_name, len(parent_ids), avg_resonance, viability,
        )
        
        return FusionResult(
            success=True,
            hybrid_id=hybrid_name,
            hybrid_dna=hybrid_dna,
            parents=parent_ids,
            resonance_score=avg_resonance,
            viability_score=viability,
        )

    def _synthesize_hybrid(
        self,
        hybrid_name: str,
        parent_dnas: List[AgentDNA],
    ) -> AgentDNA:
        """Sintetiza DNA híbrido a partir de pais."""
        now = time.time()
        
        # Calcular geração (máximo dos pais + 1)
        hybrid_generation = max(d.generation for d in parent_dnas) + 1
        
        # Combinar traits
        hybrid_traits = {}
        all_trait_names = set()
        for dna in parent_dnas:
            all_trait_names.update(dna.traits.keys())
        
        for trait_name in all_trait_names:
            # Coletar traits de todos os pais
            parent_traits = []
            for dna in parent_dnas:
                if trait_name in dna.traits:
                    parent_traits.append(dna.traits[trait_name])
            
            if parent_traits:
                # Selecionar trait dominante (ou combinar)
                if len(parent_traits) == 1:
                    selected = parent_traits[0]
                else:
                    # Escolher trait com maior expression_level
                    selected = max(parent_traits, key=lambda t: t.expression_level)
                
                # Herdar de um pai específico
                hybrid_traits[trait_name] = DNATrait(
                    trait_name=trait_name,
                    trait_value=selected.trait_value,
                    expression_level=selected.expression_level * 0.9,  # Leve redução
                    inherited_from=selected.inherited_from,
                )
        
        # Calcular lineage_hash do híbrido
        lineage_data = f"{hybrid_name}:hybrid:{hybrid_generation}:{sorted(hybrid_traits.keys())}"
        lineage_hash = hashlib.sha3_512(lineage_data.encode()).hexdigest()[:32]
        
        # Calcular fitness médio dos pais
        avg_fitness = sum(d.fitness_score for d in parent_dnas) / len(parent_dnas)
        
        return AgentDNA(
            agent_id=hybrid_name,
            agent_type="hybrid",
            generation=hybrid_generation,
            traits=hybrid_traits,
            lineage_hash=lineage_hash,
            created_at=now,
            fitness_score=avg_fitness,
            compatibility_markers=self._merge_markers(parent_dnas),
        )

    def _merge_markers(self, parent_dnas: List[AgentDNA]) -> List[str]:
        """Combina compatibility markers dos pais."""
        all_markers = set()
        for dna in parent_dnas:
            all_markers.update(dna.compatibility_markers)
        return list(all_markers)

    def _calculate_viability(self, hybrid_dna: AgentDNA) -> float:
        """Calcula viabilidade do híbrido."""
        # Fatores de viabilidade:
        # 1. Número de traits (nem muito poucos, nem muitos)
        trait_count = len(hybrid_dna.traits)
        trait_score = min(1.0, trait_count / 10)  # Ideal: 10+ traits
        
        # 2. Diversidade de traits
        unique_values = len(set(str(t.trait_value) for t in hybrid_dna.traits.values()))
        diversity_score = min(1.0, unique_values / 5)  # Ideal: 5+ valores únicos
        
        # 3. Expression level médio
        avg_expression = (
            sum(t.expression_level for t in hybrid_dna.traits.values()) /
            len(hybrid_dna.traits) if hybrid_dna.traits else 0.0
        )
        
        # Viabilidade = média ponderada
        viability = (trait_score * 0.4) + (diversity_score * 0.3) + (avg_expression * 0.3)
        
        return viability

    async def register_lineage_async(
        self,
        hybrid_id: str,
        parents: List[str],
        obsidian_note_id: Optional[str] = None,
    ) -> LineageRecord:
        """
        Registra linhagem do híbrido no AncestryTree.
        
        Args:
            hybrid_id: ID do agente híbrido
            parents: Lista de IDs dos pais
            obsidian_note_id: ID da nota no Obsidian (opcional)
            
        Returns:
            LineageRecord: Registro criado
        """
        now = time.time()
        
        with self._rlock:
            hybrid_dna = self._agent_dnas.get(hybrid_id)
            if not hybrid_dna:
                raise ValueError(f"Híbrido não encontrado: {hybrid_id}")
            
            # Calcular ressonância média
            resonance_scores = []
            for i, pid_a in enumerate(parents):
                for pid_b in parents[i+1:]:
                    res = self.calculate_dna_resonance(pid_a, pid_b)
                    resonance_scores.append(res["resonance_score"])
            
            avg_resonance = sum(resonance_scores) / len(resonance_scores) if resonance_scores else 0.0
            
            # Mapear traits herdadas
            traits_inherited = {}
            for trait_name, trait in hybrid_dna.traits.items():
                traits_inherited[trait_name] = trait.inherited_from
            
            record = LineageRecord(
                hybrid_id=hybrid_id,
                parents=parents,
                fusion_timestamp=now,
                resonance_score=avg_resonance,
                generation=hybrid_dna.generation,
                traits_inherited=traits_inherited,
                obsidian_note_id=obsidian_note_id,
            )
            
            self._lineage_records.append(record)
        
        logger.info(
            "[FusionEngine] Linhagem registrada: %s (pais=%d, geração=%d)",
            hybrid_id, len(parents), hybrid_dna.generation,
        )
        
        return record

    def get_lineage(self, agent_id: str) -> Optional[LineageRecord]:
        """Retorna linhagem de um agente (se híbrido)."""
        with self._rlock:
            for record in self._lineage_records:
                if record.hybrid_id == agent_id:
                    return record
        return None

    def get_ancestry_tree(self, agent_id: str, depth: int = 3) -> Dict[str, Any]:
        """
        Constrói árvore de ancestralidade para um agente.
        
        Args:
            agent_id: ID do agente
            depth: Profundidade máxima da árvore
            
        Returns:
            Árvore de ancestralidade em formato dict
        """
        with self._rlock:
            dna = self._agent_dnas.get(agent_id)
            if not dna:
                return {"error": "Agent not found"}
            
            # Encontrar linhagem
            lineage = self.get_lineage(agent_id)
            if not lineage:
                # Agente não-híbrido (original)
                return {
                    "agent_id": agent_id,
                    "type": "original",
                    "generation": dna.generation,
                    "parents": [],
                }
            
            # Construir árvore recursivamente
            tree = {
                "agent_id": agent_id,
                "type": "hybrid",
                "generation": dna.generation,
                "resonance_score": lineage.resonance_score,
                "parents": [],
            }
            
            if depth > 1:
                for parent_id in lineage.parents:
                    parent_tree = self.get_ancestry_tree(parent_id, depth - 1)
                    tree["parents"].append(parent_tree)
            
            return tree

    def get_fusion_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de fusões."""
        with self._rlock:
            total = self._fusion_count + self._failed_fusions
            success_rate = (
                self._fusion_count / total if total > 0 else 0.0
            )
            
            return {
                "total_fusions": total,
                "successful_fusions": self._fusion_count,
                "failed_fusions": self._failed_fusions,
                "success_rate": round(success_rate, 3),
                "registered_dnas": len(self._agent_dnas),
                "lineage_records": len(self._lineage_records),
            }

    def reset(self) -> None:
        """Reseta estado do motor (para testes)."""
        with self._rlock:
            self._agent_dnas.clear()
            self._lineage_records.clear()
            self._fusion_count = 0
            self._failed_fusions = 0
            logger.info("[FusionEngine] ✅ Estado resetado")


# Singleton global
fusion_engine = FusionEngine()