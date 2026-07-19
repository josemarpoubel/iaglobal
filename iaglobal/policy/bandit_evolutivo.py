# iaglobal/policy/bandit_evolutivo.py
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

Proteção de concorrência:
- Toda mutação de estado passa por _registrar_execucao_sync(),
  executada em thread pool sob threading.Lock + AtomicJSONStore.mutate_sync().
- Leitores snapshot os dicts sob _lock e operam sobre cópias.
- ProviderFitnessRecord é imutável — atualizar_fitness() retorna novo record.
"""

import asyncio
import logging
import random
import threading
from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.utils.atomic_io import AtomicJSONStore

logger = logging.getLogger("iaglobal.policy.bandit_evolutivo")

_INITIAL_EVOLUTIVE_STATE: dict = {
    "fitness_records": {},
    "banned_providers": {},
    "weights": {},
    "updated_at": None,
}


@dataclass(frozen=True)
class ProviderFitnessRecord:
    """Registro de fitness evolutivo de um provider. Imutável."""

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

    def atualizar_fitness(
        self, ivm: float, latencia_ms: float, custo: float
    ) -> "ProviderFitnessRecord":
        """Retorna NOVO ProviderFitnessRecord com fitness atualizado."""
        total_uses = self.total_uses + 1
        sucesso = ivm >= 0.7

        successful_uses = self.successful_uses + (1 if sucesso else 0)
        failed_uses = self.failed_uses + (0 if sucesso else 1)
        strikes_consecutivos = 0 if sucesso else self.strikes_consecutivos + 1

        ivm_history = self.ivm_history[-99:] + [ivm]
        ivm_media_movel = sum(ivm_history) / len(ivm_history)

        alpha = 0.1
        latencia_media_ms = alpha * latencia_ms + (1 - alpha) * self.latencia_media_ms
        custo_medio_creditos = alpha * custo + (1 - alpha) * self.custo_medio_creditos

        latency_score = min(1.0, 1000 / max(latencia_media_ms, 100))
        cost_score = min(1.0, 10 / max(custo_medio_creditos, 0.1))
        fitness_score = (
            ivm_media_movel * 0.6 + latency_score * 0.2 + cost_score * 0.2
        )

        return ProviderFitnessRecord(
            provider_id=self.provider_id,
            total_uses=total_uses,
            successful_uses=successful_uses,
            failed_uses=failed_uses,
            ivm_history=ivm_history,
            ivm_media_movel=ivm_media_movel,
            strikes_consecutivos=strikes_consecutivos,
            ultimo_banimento=self.ultimo_banimento,
            latencia_media_ms=latencia_media_ms,
            custo_medio_creditos=custo_medio_creditos,
            fitness_score=fitness_score,
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
        if self.fitness_score >= 0.7:
            return False

        if self.ivm_media_movel < 0.3 and self.total_uses >= 10:
            return True

        if self.total_uses > 0:
            taxa_falha = self.failed_uses / self.total_uses
            if taxa_falha > 0.8 and self.total_uses >= 10:
                return True

        return self.strikes_consecutivos >= 3 and self.fitness_score < 0.5

    def to_dict(self) -> Dict[str, Any]:
        """Serializa para dict."""
        return {
            "provider_id": self.provider_id,
            "total_uses": self.total_uses,
            "successful_uses": self.successful_uses,
            "failed_uses": self.failed_uses,
            "ivm_history": self.ivm_history[-20:],
            "ivm_media_movel": self.ivm_media_movel,
            "strikes_consecutivos": self.strikes_consecutivos,
            "ultimo_banimento": self.ultimo_banimento.isoformat()
            if self.ultimo_banimento
            else None,
            "latencia_media_ms": self.latencia_media_ms,
            "custo_medio_creditos": self.custo_medio_creditos,
            "fitness_score": self.fitness_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderFitnessRecord":
        """Deserializa de dict."""
        ultimo_banimento = None
        if data.get("ultimo_banimento"):
            ultimo_banimento = datetime.fromisoformat(data["ultimo_banimento"])
        return cls(
            provider_id=data["provider_id"],
            total_uses=data.get("total_uses", 0),
            successful_uses=data.get("successful_uses", 0),
            failed_uses=data.get("failed_uses", 0),
            ivm_history=data.get("ivm_history", []),
            ivm_media_movel=data.get("ivm_media_movel", 0.0),
            strikes_consecutivos=data.get("strikes_consecutivos", 0),
            ultimo_banimento=ultimo_banimento,
            latencia_media_ms=data.get("latencia_media_ms", 0.0),
            custo_medio_creditos=data.get("custo_medio_creditos", 0.0),
            fitness_score=data.get("fitness_score", 0.0),
        )


class BanditPolicyEvolutiva(BanditPolicy):
    """
    BanditPolicy com aprendizado evolutivo contínuo.

    Diferenças da BanditPolicy original:
    1. Mantém histórico de fitness de cada provider
    2. Ajusta weights automaticamente baseado em IVM histórico
    3. Bane providers com performance consistentemente ruim
    4. Prioriza exploration de providers com alto fitness mas pouco usados

    Toda mutação de estado é serializada por threading.Lock + fcntl.flock
    via AtomicJSONStore.mutate_sync(). A lambda recebe o estado FRESCO do
    disco e aplica APENAS o delta desta execução — nunca serializa a cópia
    residente. Leitores snapshot os dicts sob lock e operam sobre cópias.
    """

    def __init__(
        self,
        epsilon: float = 0.2,
        decay: float = 0.995,
        min_sample_size: int = 10,
        db_path: Optional[Path] = None,
    ):
        super().__init__(
            epsilon=epsilon,
            decay=decay,
        )

        self.evolutionary_weights: Dict[str, float] = {}
        self.fitness_records: Dict[str, ProviderFitnessRecord] = {}
        self.banned_providers: Dict[str, datetime] = {}

        self.db_path = db_path or Path("iaglobal/memory/bandit_evolutivo.json")
        self.ban_duration_hours = 24
        self.min_fitness_for_selection = 0.3

        self._lock = threading.Lock()
        self._store = AtomicJSONStore(self.db_path, default=_INITIAL_EVOLUTIVE_STATE)
        self._sincronizar_de(self._store.read_sync())

    def _sincronizar_de(self, estado: dict) -> None:
        """Atualiza resident memory a partir de estado serializado (dicts)."""
        self.fitness_records = {
            pid: ProviderFitnessRecord.from_dict(data)
            for pid, data in estado.get("fitness_records", {}).items()
        }
        self.banned_providers = {
            pid: datetime.fromisoformat(ban_str)
            for pid, ban_str in estado.get("banned_providers", {}).items()
        }
        self.evolutionary_weights = dict(estado.get("weights", {}))

    async def registrar_execucao(
        self,
        provider_id: str,
        ivm: float,
        latencia_ms: float,
        custo_creditos: float,
        sucesso: bool,
    ) -> None:
        """
        Registra execução de provider e atualiza fitness evolutivo.

        Conecta o IVM do agent com o fitness do provider,
        criando feedback loop evolutivo. Síncrono em thread pool.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            self._registrar_execucao_sync,
            provider_id,
            ivm,
            latencia_ms,
            custo_creditos,
            sucesso,
        )

    def _registrar_execucao_sync(
        self,
        provider_id: str,
        ivm: float,
        latencia_ms: float,
        custo_creditos: float,
        sucesso: bool,
    ) -> None:
        """Seção crítica síncrona — muta estado sob threading.Lock + flock."""

        def apply_delta(fresh: dict) -> dict:
            estado = dict(fresh) if fresh else dict(_INITIAL_EVOLUTIVE_STATE)
            agora = datetime.now(UTC)

            # Expurga bans expirados do estado fresco
            estado["banned_providers"] = {
                pid: ban_str
                for pid, ban_str in estado["banned_providers"].items()
                if datetime.fromisoformat(ban_str) > agora
            }

            # Cria/atualiza fitness record sobre o fresco
            fitness = estado["fitness_records"]
            existente = fitness.get(provider_id)
            record = (
                ProviderFitnessRecord.from_dict(existente)
                if existente
                else ProviderFitnessRecord(provider_id=provider_id)
            )
            novo = record.atualizar_fitness(ivm, latencia_ms, custo_creditos)
            fitness[provider_id] = novo.to_dict()

            # Banimento
            if novo.deve_ser_banido():
                estado["banned_providers"][provider_id] = (
                    agora + timedelta(hours=self.ban_duration_hours)
                ).isoformat()
                estado["weights"].pop(provider_id, None)
                logger.warning(
                    "[BANIMENTO] Provider %s banido por %sh "
                    "(strikes=%d, fitness=%.3f)",
                    provider_id,
                    self.ban_duration_hours,
                    novo.strikes_consecutivos,
                    novo.fitness_score,
                )

            # Recalcula weights sobre o fitness fresco
            estado["weights"] = BanditPolicyEvolutiva._calcular_weights(
                fitness,
                estado["banned_providers"],
                estado.get("weights", {}),
            )
            estado["updated_at"] = agora.isoformat()
            return estado

        with self._lock:
            estado = self._store.mutate_sync(apply_delta)
            self._sincronizar_de(estado)

        logger.debug(
            "[FITNESS] %s: fitness=%.3f, IVM_médio=%.3f, strikes=%d",
            provider_id,
            self.fitness_records.get(provider_id, ProviderFitnessRecord(provider_id)).fitness_score,
            self.fitness_records.get(provider_id, ProviderFitnessRecord(provider_id)).ivm_media_movel,
            self.fitness_records.get(provider_id, ProviderFitnessRecord(provider_id)).strikes_consecutivos,
        )

    @staticmethod
    def _calcular_weights(
        fitness: Dict[str, dict],
        banned: Dict[str, str],
        prev_weights: Dict[str, float],
    ) -> Dict[str, float]:
        """Função pura: calcula weights a partir de fitness serializado + bans."""
        if not fitness:
            return {}
        fitness_values = [r["fitness_score"] for r in fitness.values()]
        fitness_medio = sum(fitness_values) / len(fitness_values)
        weights = {}
        for pid, r in fitness.items():
            if pid in banned:
                continue
            weight_alvo = r["fitness_score"] / max(fitness_medio, 0.1)
            weight_atual = prev_weights.get(pid, 1.0)
            alpha = 0.05
            novo_weight = (1 - alpha) * weight_atual + alpha * weight_alvo
            weights[pid] = max(0.1, novo_weight)
        return weights

    def rank_providers(self, task_type: str = "general") -> List[Tuple[str, float]]:
        """
        Rankeia providers por fitness + task suitability.

        Retorna lista de (provider_id, score) ordenada por score decrescente.
        """
        with self._lock:
            fitness = dict(self.fitness_records)
            banned = dict(self.banned_providers)

        rankings = []
        for provider_id, record in fitness.items():
            if provider_id in banned:
                continue
            if record.fitness_score < self.min_fitness_for_selection:
                continue
            score_base = record.fitness_score
            bonus_task = 1.0  # TODO: Implementar por task_type
            score_final = score_base * bonus_task
            rankings.append((provider_id, score_final))

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

        with self._lock:
            fitness = dict(self.fitness_records)
            banned = dict(self.banned_providers)

        available = [p for p in available_providers if p not in banned]

        if not available:
            logger.warning("Todos providers banidos! Fallback para ollama")
            return "ollama"

        if use_exploration and random.random() < self.epsilon:
            pouco_usados = [
                (p, fitness.get(p, ProviderFitnessRecord(p)))
                for p in available
                if fitness.get(p, ProviderFitnessRecord(p)).total_uses < 10
            ]
            if pouco_usados:
                escolhido = max(pouco_usados, key=lambda x: x[1].fitness_score)[0]
                logger.debug("[EXPLORAÇÃO] %s", escolhido)
                return escolhido

        rankings = self.rank_providers(task_type)
        for provider_id, _ in rankings:
            if provider_id in available:
                logger.debug("[EXPLORAÇÃO] %s", provider_id)
                return provider_id

        return available[0]

    def get_status_evolutivo(self) -> Dict[str, Any]:
        """Retorna status detalhado da evolução."""
        with self._lock:
            if not self.fitness_records:
                return {"status": "sem_dados"}
            fitness = dict(self.fitness_records)
            banned = dict(self.banned_providers)

        fitness_scores = [r.fitness_score for r in fitness.values()]
        ivm_medias = [r.ivm_media_movel for r in fitness.values()]
        banidos = list(banned.keys())
        rankings = self.rank_providers()
        top_5 = rankings[:5]

        return {
            "status": "operacional",
            "total_providers": len(fitness),
            "providers_banidos": len(banidos),
            "fitness_medio": sum(fitness_scores) / len(fitness_scores)
            if fitness_scores
            else 0,
            "fitness_max": max(fitness_scores) if fitness_scores else 0,
            "fitness_min": min(fitness_scores) if fitness_scores else 0,
            "ivm_medio_historico": sum(ivm_medias) / len(ivm_medias)
            if ivm_medias
            else 0,
            "top_providers": top_5,
            "banidos": banidos,
            "epsilon_atual": self.epsilon,
        }


# Alias para compatibilidade
BanditPolicyAutoEvoliva = BanditPolicyEvolutiva
