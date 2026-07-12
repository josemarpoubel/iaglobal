#!/usr/bin/env python3
"""
BanditPolicy Evolutiva — Aprendizado Contínuo com Histórico de IVM

Esta extensão da BanditPolicy original adiciona:
1. Memória de longo prazo de performance de providers
2. Ajuste automático de weights baseado em IVM histórico
3. Banimento automático de providers persistentemente ruins
4. Métricas de "fitness evolutivo" para seleção natural de providers

DNA Evolutivo:
- Fitness = média móvel de IVM dos últimos N usos
- Banimento = 3 strikes consecutivos com IVM < 0.3
- Weight adjustment = gradient descent no espaço de rewards
"""

import asyncio
import json
import random
import logging
from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib

from iaglobal.chappie import IVMAxiom
from iaglobal.graphs.bandit import BanditPolicy

logger = logging.getLogger("iaglobal.policy.bandit_evolutivo")


@dataclass
class ProviderFitnessRecord:
    """Registro de fitness evolutivo de um provider."""
    
    provider_id: str
    total_uses: int = 0
    successful_uses: int = 0
    failed_uses: int = 0
    
    # Histórico de IVM (últimos 100 usos)
    ivm_history: List[float] = field(default_factory=list)
    ivm_media_movel: float = 0.0
    
    # Strikes para banimento
    strikes_consecutivos: int = 0
    ultimo_banimento: Optional[datetime] = None
    
    # Métricas de performance
    latencia_media_ms: float = 0.0
    custo_medio_creditos: float = 0.0
    
    # Fitness score (0-1)
    fitness_score: float = 0.0
    
    def atualizar_fitness(self, ivm: float, latencia_ms: float, custo: float):
        """Atualiza fitness score baseado em nova execução."""
        self.total_uses += 1
        
        if ivm >= 0.7:
            self.successful_uses += 1
            self.strikes_consecutivos = 0  # Reseta strikes
        else:
            self.failed_uses += 1
            self.strikes_consecutivos += 1
        
        # Atualiza histórico de IVM (mantém últimos 100)
        self.ivm_history.append(ivm)
        if len(self.ivm_history) > 100:
            self.ivm_history.pop(0)
        
        # Calcula média móvel de IVM
        self.ivm_media_movel = sum(self.ivm_history) / len(self.ivm_history)
        
        # Atualiza latência média (média exponencial)
        alpha = 0.1
        self.latencia_media_ms = (
            alpha * latencia_ms + (1 - alpha) * self.latencia_media_ms
        )
        
        # Atualiza custo médio
        self.custo_medio_creditos = (
            alpha * custo + (1 - alpha) * self.custo_medio_creditos
        )
        
        # Calcula fitness score composto
        # Fitness = (IVM média × 0.6) + (1/latência × 0.2) + (1/custo × 0.2)
        latency_score = min(1.0, 1000 / max(self.latencia_media_ms, 100))
        cost_score = min(1.0, 10 / max(self.custo_medio_creditos, 0.1))
        
        self.fitness_score = (
            self.ivm_media_movel * 0.6 +
            latency_score * 0.2 +
            cost_score * 0.2
        )
    
    def deve_ser_banido(self) -> bool:
        """
        Verifica se provider deve ser banido temporariamente.
        
        Regras de banimento:
        1. 3+ strikes consecutivos COM fitness baixo (<0.5)
        2. Fitness médio histórico <0.3 (incompetência crônica)
        3. Mais de 80% de falhas no total
        
        Providers com fitness alto (>0.7) NÃO devem ser banidos
        mesmo com alguns failures isolados.
        """
        # Protege providers com fitness alto
        if self.fitness_score >= 0.7:
            return False
        
        # Banimento por performance crônica ruim
        if self.ivm_media_movel < 0.3 and self.total_uses >= 10:
            return True
        
        # Banimento por taxa de falha alta
        if self.total_uses > 0:
            taxa_falha = self.failed_uses / self.total_uses
            if taxa_falha > 0.8 and self.total_uses >= 10:
                return True
        
        # Banimento por strikes consecutivos (apenas se fitness baixo)
        return self.strikes_consecutivos >= 3 and self.fitness_score < 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa para dict."""
        return {
            "provider_id": self.provider_id,
            "total_uses": self.total_uses,
            "successful_uses": self.successful_uses,
            "failed_uses": self.failed_uses,
            "ivm_history": self.ivm_history[-20:],  # Últimos 20 para persistência
            "ivm_media_movel": self.ivm_media_movel,
            "strikes_consecutivos": self.strikes_consecutivos,
            "ultimo_banimento": self.ultimo_banimento.isoformat() if self.ultimo_banimento else None,
            "latencia_media_ms": self.latencia_media_ms,
            "custo_medio_creditos": self.custo_medio_creditos,
            "fitness_score": self.fitness_score,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderFitnessRecord":
        """Deserializa de dict."""
        record = cls(provider_id=data["provider_id"])
        record.total_uses = data.get("total_uses", 0)
        record.successful_uses = data.get("successful_uses", 0)
        record.failed_uses = data.get("failed_uses", 0)
        record.ivm_history = data.get("ivm_history", [])
        record.ivm_media_movel = data.get("ivm_media_movel", 0.0)
        record.strikes_consecutivos = data.get("strikes_consecutivos", 0)
        record.latencia_media_ms = data.get("latencia_media_ms", 0.0)
        record.custo_medio_creditos = data.get("custo_medio_creditos", 0.0)
        record.fitness_score = data.get("fitness_score", 0.0)
        
        if data.get("ultimo_banimento"):
            record.ultimo_banimento = datetime.fromisoformat(data["ultimo_banimento"])
        
        return record


class BanditPolicyEvolutiva(BanditPolicy):
    """
    BanditPolicy com aprendizado evolutivo contínuo.
    
    Diferenças da BanditPolicy original:
    1. Mantém histórico de fitness de cada provider
    2. Ajusta weights automaticamente baseado em IVM histórico
    3. Bane providers com performance consistentemente ruim
    4. Prioriza exploration de providers com alto fitness mas pouco usados
    """
    
    def __init__(
        self,
        epsilon: float = 0.2,
        decay: float = 0.995,
        min_sample_size: int = 10,
        db_path: Optional[Path] = None,
    ):
        # Inicializa rewards antes de chamar super
        self.rewards: Dict[str, float] = {}
        
        super().__init__(
            epsilon=epsilon,
            decay=decay,
        )
        
        # Registro de fitness de providers
        self.fitness_records: Dict[str, ProviderFitnessRecord] = {}
        
        # Providers banidos temporariamente
        self.banned_providers: Dict[str, datetime] = {}
        
        # Configurações de evolução
        self.db_path = db_path or Path("iaglobal/memory/bandit_evolutivo.json")
        self.ban_duration_hours = 24
        self.min_fitness_for_selection = 0.3
        
        # Carrega estado persistido
        self._carregar_estado()
    
    def _get_fitness_record(self, provider_id: str) -> ProviderFitnessRecord:
        """Obtém ou cria registro de fitness de um provider."""
        if provider_id not in self.fitness_records:
            self.fitness_records[provider_id] = ProviderFitnessRecord(
                provider_id=provider_id
            )
        return self.fitness_records[provider_id]
    
    async def registrar_execucao(
        self,
        provider_id: str,
        ivm: float,
        latencia_ms: float,
        custo_creditos: float,
        sucesso: bool,
    ):
        """
        Registra execução de provider e atualiza fitness evolutivo.
        
        Este método conecta o IVM do agent com o fitness do provider,
        criando feedback loop evolutivo.
        """
        # Atualiza registro de fitness
        record = self._get_fitness_record(provider_id)
        record.atualizar_fitness(ivm, latencia_ms, custo_creditos)
        
        # Verifica banimento
        if record.deve_ser_banido():
            await self._banir_provider(provider_id)
            logger.warning(
                f"[BANIMENTO] Provider {provider_id} banido por {self.ban_duration_hours}h "
                f"(strikes={record.strikes_consecutivos}, fitness={record.fitness_score:.3f})"
            )
        
        # Ajusta weights baseado em fitness
        await self._ajustar_weights_evolutivo()
        
        # Persiste estado
        self._salvar_estado()
        
        logger.debug(
            f"[FITNESS] {provider_id}: fitness={record.fitness_score:.3f}, "
            f"IVM_médio={record.ivm_media_movel:.3f}, "
            f"strikes={record.strikes_consecutivos}"
        )
    
    async def _banir_provider(self, provider_id: str):
        """Bane provider temporariamente."""
        
        ban_until = datetime.now(UTC) + timedelta(hours=self.ban_duration_hours)
        self.banned_providers[provider_id] = ban_until
        
        # Remove dos weights atuais
        if provider_id in self.rewards:
            del self.rewards[provider_id]
        
        logger.info(f"[BANIMENTO] {provider_id} até {ban_until.isoformat()}")
    
    def _verificar_banimentos_expirados(self):
        """Verifica e remove banimentos expirados."""
        agora = datetime.now(UTC)

        providers_expirados = [
            provider for provider, ban_until in self.banned_providers.items()
            if ban_until <= agora
        ]
        
        for provider in providers_expirados:
            del self.banned_providers[provider]
            logger.info(f"[UNBAN] Provider {provider} liberado")
    
    async def _ajustar_weights_evolutivo(self):
        """
        Ajusta weights dos providers baseado em fitness evolutivo.
        
        Providers com alto fitness ganham weight, baixo fitness perdem.
        Usa gradient descent suave para evitar oscilações bruscas.
        """
        if not self.fitness_records:
            return
        
        # Calcula fitness médio de todos providers
        fitness_medio = sum(
            r.fitness_score for r in self.fitness_records.values()
        ) / len(self.fitness_records)
        
        # Ajusta weights proporcionalmente ao fitness
        for provider_id, record in self.fitness_records.items():
            if record.provider_id in self.banned_providers:
                continue
            
            # Weight alvo baseado em fitness relativo
            weight_alvo = record.fitness_score / max(fitness_medio, 0.1)
            
            # Gradual adjustment (evita mudanças bruscas)
            weight_atual = self.rewards.get(provider_id, 1.0)
            alpha = 0.05  # Learning rate
            
            novo_weight = (1 - alpha) * weight_atual + alpha * weight_alvo
            self.rewards[provider_id] = max(0.1, novo_weight)  # Mínimo 0.1
    
    def rank_providers(self, task_type: str = "general") -> List[Tuple[str, float]]:
        """
        Rankeia providers por fitness + IVM do agent + task suitability.
        
        Retorna lista de (provider_id, score) ordenada por score decrescente.
        """
        # Verifica banimentos expirados
        self._verificar_banimentos_expirados()
        
        rankings = []
        
        for provider_id, record in self.fitness_records.items():
            # Pula providers banidos
            if provider_id in self.banned_providers:
                continue
            
            # Pula providers com fitness muito baixo
            if record.fitness_score < self.min_fitness_for_selection:
                continue
            
            # Score composto: fitness + IVM agent + bonus task_type
            score_base = record.fitness_score
            
            # Bonus por especialização (se implementado)
            bonus_task = 1.0  # TODO: Implementar por task_type
            
            score_final = score_base * bonus_task
            
            rankings.append((provider_id, score_final))
        
        # Ordena por score decrescente
        rankings.sort(key=lambda x: x[1], reverse=True)
        
        return rankings
    
    def select_provider(
        self,
        available_providers: List[str],
        task_type: str = "general",
        use_exploration: bool = True,
    ) -> str:
        """
        Seleciona provider usando epsilon-greedy evolutivo.
        
        - (1-epsilon): Escolhe provider com maior fitness
        - epsilon: Explora providers pouco usados mas promissores
        """
        if not available_providers:
            raise ValueError("Nenhum provider disponível")
        
        # Filtra providers banidos
        available = [
            p for p in available_providers
            if p not in self.banned_providers
        ]
        
        if not available:
            # Fallback: usa ollama local se tudo banido
            logger.warning("Todos providers banidos! Fallback para ollama")
            return "ollama"
        
        # Verifica exploração
        if use_exploration and random.random() < self.epsilon:
            # Exploração: escolhe provider pouco usado com fitness decente
            pouco_usados = [
                (p, self.fitness_records.get(p, ProviderFitnessRecord(p)))
                for p in available
                if self.fitness_records.get(p, ProviderFitnessRecord(p)).total_uses < 10
            ]
            
            if pouco_usados:
                # Escolhe o com maior fitness entre pouco usados
                escolhido = max(pouco_usados, key=lambda x: x[1].fitness_score)[0]
                logger.debug(f"[EXPLORAÇÃO] {escolhido}")
                return escolhido
        
        # Exploração: usa ranking de fitness
        rankings = self.rank_providers(task_type)
        
        for provider_id, _ in rankings:
            if provider_id in available:
                logger.debug(f"[EXPLORAÇÃO] {provider_id}")
                return provider_id
        
        # Fallback: primeiro disponível
        return available[0]
    
    def _salvar_estado(self):
        """Persiste estado evolutivo em disco."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            estado = {
                "fitness_records": {
                    k: v.to_dict()
                    for k, v in self.fitness_records.items()
                },
                "banned_providers": {
                    k: v.isoformat()
                    for k, v in self.banned_providers.items()
                },
                "weights": dict(self.rewards),
                "updated_at": datetime.now(UTC).isoformat(),
            }
            
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(estado, f, indent=2)
                
            logger.debug(f"[PERSISTÊNCIA] Estado salvo em {self.db_path}")
            
        except Exception as e:
            logger.error(f"[PERSISTÊNCIA] Erro ao salvar: {e}")
    
    def _carregar_estado(self):
        """Carrega estado evolutivo persistido."""
        if not self.db_path.exists():
            logger.info("[PERSISTÊNCIA] Nenhum estado persistido encontrado")
            return
        
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                estado = json.load(f)
            
            # Carrega fitness records
            for provider_id, data in estado.get("fitness_records", {}).items():
                self.fitness_records[provider_id] = ProviderFitnessRecord.from_dict(data)
            
            # Carrega banimentos
            for provider_id, ban_until_str in estado.get("banned_providers", {}).items():
                ban_until = datetime.fromisoformat(ban_until_str)
                if ban_until > datetime.now(UTC):
                    self.banned_providers[provider_id] = ban_until
                    logger.info(f"[PERSISTÊNCIA] {provider_id} ainda banido até {ban_until}")
            
            # Carrega weights
            for provider_id, reward in estado.get("weights", {}).items():
                self.rewards[provider_id] = reward
            
            logger.info(
                f"[PERSISTÊNCIA] Estado carregado: {len(self.fitness_records)} providers, "
                f"{len(self.banned_providers)} banidos"
            )
            
        except Exception as e:
            logger.error(f"[PERSISTÊNCIA] Erro ao carregar: {e}")
    
    def get_status_evolutivo(self) -> Dict[str, Any]:
        """Retorna status detalhado da evolução."""
        if not self.fitness_records:
            return {"status": "sem_dados"}
        
        # Estatísticas de fitness
        fitness_scores = [r.fitness_score for r in self.fitness_records.values()]
        ivm_medias = [r.ivm_media_movel for r in self.fitness_records.values()]
        
        # providers banidos
        banidos = list(self.banned_providers.keys())
        
        # Top 5 providers
        rankings = self.rank_providers()
        top_5 = rankings[:5]
        
        return {
            "status": "operacional",
            "total_providers": len(self.fitness_records),
            "providers_banidos": len(banidos),
            "fitness_medio": sum(fitness_scores) / len(fitness_scores) if fitness_scores else 0,
            "fitness_max": max(fitness_scores) if fitness_scores else 0,
            "fitness_min": min(fitness_scores) if fitness_scores else 0,
            "ivm_medio_historico": sum(ivm_medias) / len(ivm_medias) if ivm_medias else 0,
            "top_providers": top_5,
            "banidos": banidos,
            "epsilon_atual": self.epsilon,
        }

# Alias para compatibilidade
BanditPolicyAutoEvoliva = BanditPolicyEvolutiva