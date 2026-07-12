# ============================================================
# CHAPPIE COMPONENTE 4/4: IVM AXIOM
# Lei da Compensação Metabólica + Lei do Sucesso
# ============================================================
"""IVMAxiom — Compensação Explícita via IVM.

Implementa a Lei da Compensação Metabólica:
  "O IVM (Índice de Viabilidade Metabólica) é a medida exata
   da contribuição de um agente para o organismo. Reward no
   BanditPolicy deve ser estritamente proporcional ao IVM —
   sem favorecimento, sem viés."

E a Lei do Sucesso:
  "O sucesso é o resultado natural e inevitável da aplicação
   consistente de todas as leis. Um IVM alto é resultado
   matemático de aplicar todas as leis ao pipeline."

Fórmula do IVM:
  IVM = (P × 0.4) + (E × 0.4) + (C × 0.2)

  Onde:
    P = Produtividade (taxa de conclusão de tarefas)
    E = Eficiência Energética — COMPOSTA (federação de sinais):
        E = 0.7 · E_latência(Chappie) + 0.3 · E_cpu(CpuAffinityManager)
        E_latência = 1 / latência normalizada
        E_cpu       = 1 − (uso_cpu / budget_25%) × 0.5
    C = Cooperação (skills exchanges aprovados + MHC validation)

  IVMAxiom é a ÚNICA fonte canônica de IVM do sistema. O CpuAffinityManager
  delega seu sinal de CPU para cá (ver cpu_affinity.reportar_uso_cpu) em vez
  de manter um índice concorrente — unificação dos subsistemas.

Funcionamento:
  1. Calcula IVM em tempo real para cada agent
  2. Integra com BanditPolicy para reward cálculo explícito
  3. Dashboard de IVM por agent em tempo real
  4. Alertas quando IVM cai abaixo de threshold (degradação)
  5. Histórico de IVM para análise de tendências
  6. Persistência em disco via ShortTermMemory
"""

import asyncio
import threading
import logging
from datetime import datetime, UTC, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from collections import deque
from pathlib import Path

from iaglobal._paths import PACKAGE_DIR
from iaglobal.utils.logger import get_logger
from iaglobal.memory.term_short import ShortTermMemory

logger = get_logger("iaglobal.chappie.ivm_axiom")


@dataclass
class IVMMetrics:
    """Métricas que compõem o IVM de um agent."""

    # Produtividade (P) - 40% do peso
    tasks_completed: int = 0
    tasks_failed: int = 0
    productivity_score: float = 0.0  # tasks_completed / total_tasks

    # Eficiência Energética (E) - 40% do peso
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    energy_efficiency_score: float = 0.0  # 1 / (latência_normalizada)

    # Cooperação (C) - 20% do peso
    skills_exchanged: int = 0
    mhc_validation_score: float = 1.0  # Score do MHC Detector
    cooperation_score: float = 0.0

    # Eficiência de Orçamento de CPU (federação com CpuAffinityManager)
    cpu_usage_atual: float = 0.0       # 0.0 a 1.0 (informado pelo scheduler)
    cpu_budget: float = 0.25           # teto de 25% por agente
    cpu_efficiency_score: float = 0.0  # 1 - (uso/budget) * 0.5
    cpu_signal_ativo: bool = False     # True após 1º sinal de CPU federado

    # Pesos epigenéticos por-agente (antes eram globais no IVMAxiom)
    productivity_weight: float = 0.4
    energy_weight: float = 0.4
    cooperation_weight: float = 0.2

    # IVM Final
    ivm: float = 0.0

    # Timestamps
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "productivity": {
                "tasks_completed": self.tasks_completed,
                "tasks_failed": self.tasks_failed,
                "score": self.productivity_score,
            },
            "energy_efficiency": {
                "total_latency_ms": self.total_latency_ms,
                "avg_latency_ms": self.avg_latency_ms,
                "score": self.energy_efficiency_score,
            },
            "cooperation": {
                "skills_exchanged": self.skills_exchanged,
                "mhc_validation_score": self.mhc_validation_score,
                "score": self.cooperation_score,
            },
            "cpu": {
                "usage_atual": self.cpu_usage_atual,
                "budget": self.cpu_budget,
                "efficiency_score": self.cpu_efficiency_score,
                "signal_ativo": self.cpu_signal_ativo,
            },
            "epigenetic_weights": {
                "productivity": self.productivity_weight,
                "energy": self.energy_weight,
                "cooperation": self.cooperation_weight,
            },
            "ivm": self.ivm,
            "last_updated": self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IVMMetrics":
        """Cria instância a partir de dicionário."""
        productivity = data.get("productivity", {})
        energy = data.get("energy_efficiency", {})
        cooperation = data.get("cooperation", {})
        ew = data.get("epigenetic_weights", {})
        
        metrics = cls(
            tasks_completed=productivity.get("tasks_completed", 0),
            tasks_failed=productivity.get("tasks_failed", 0),
            productivity_score=productivity.get("score", 0.0),
            total_latency_ms=energy.get("total_latency_ms", 0.0),
            avg_latency_ms=energy.get("avg_latency_ms", 0.0),
            energy_efficiency_score=energy.get("score", 0.0),
            skills_exchanged=cooperation.get("skills_exchanged", 0),
            mhc_validation_score=cooperation.get("mhc_validation_score", 1.0),
            cooperation_score=cooperation.get("score", 0.0),
            cpu_usage_atual=cpu.get("usage_atual", 0.0) if (cpu := data.get("cpu", {})) else 0.0,
            cpu_budget=cpu.get("budget", 0.25) if (cpu := data.get("cpu", {})) else 0.25,
            cpu_efficiency_score=cpu.get("efficiency_score", 0.0) if (cpu := data.get("cpu", {})) else 0.0,
            cpu_signal_ativo=cpu.get("signal_ativo", False) if (cpu := data.get("cpu", {})) else False,
            productivity_weight=ew.get("productivity", 0.4),
            energy_weight=ew.get("energy", 0.4),
            cooperation_weight=ew.get("cooperation", 0.2),
            ivm=data.get("ivm", 0.0),
        )
        
        last_updated_str = data.get("last_updated")
        if last_updated_str:
            try:
                metrics.last_updated = datetime.fromisoformat(last_updated_str)
                if metrics.last_updated.tzinfo is None:
                    metrics.last_updated = metrics.last_updated.replace(tzinfo=UTC)
            except Exception:
                metrics.last_updated = datetime.now(UTC)
        
        return metrics


@dataclass
class AgentIVMRecord:
    """Histórico de IVM de um agent."""

    agent_name: str
    current_ivm: float = 0.0
    peak_ivm: float = 0.0
    min_ivm: float = 1.0
    history: deque = field(default_factory=lambda: deque(maxlen=100))
    trend: str = "stable"  # "rising", "falling", "stable"

    def update(self, ivm: float) -> None:
        """Atualiza IVM e histórico."""
        self.current_ivm = ivm
        self.peak_ivm = max(self.peak_ivm, ivm)
        self.min_ivm = min(self.min_ivm, ivm)
        self.history.append((datetime.now(UTC), ivm))

        # Calcula tendência
        if len(self.history) >= 10:
            recent = [ivm for _, ivm in list(self.history)[-10:]]
            if recent[-1] > recent[0] * 1.1:
                self.trend = "rising"
            elif recent[-1] < recent[0] * 0.9:
                self.trend = "falling"
            else:
                self.trend = "stable"

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário serializável."""
        return {
            "agent_name": self.agent_name,
            "current_ivm": self.current_ivm,
            "peak_ivm": self.peak_ivm,
            "min_ivm": self.min_ivm,
            "history": [(ts.isoformat(), ivm) for ts, ivm in self.history],
            "trend": self.trend,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentIVMRecord":
        """Cria instância a partir de dicionário."""
        record = cls(
            agent_name=data.get("agent_name", ""),
            current_ivm=data.get("current_ivm", 0.0),
            peak_ivm=data.get("peak_ivm", 0.0),
            min_ivm=data.get("min_ivm", 1.0),
            trend=data.get("trend", "stable"),
        )
        
        history_data = data.get("history", [])
        for ts_str, ivm in history_data:
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                record.history.append((ts, ivm))
            except Exception:
                pass
        
        return record


class IVMAxiom:
    """Axioma da Compensação Metabólica — IVM Explícito.

    Calcula, rastreia e integra IVM com BanditPolicy para
    rewards justamente proporcionais à contribuição de cada agent.

    Uso:
        ivm_axiom = IVMAxiom(db_path=PACKAGE_DIR / "memory" / "ivm.db")

        # Atualiza métricas após execução de agent
        await ivm_axiom.atualizar_metricas(
            agent_name="coder",
            tasks_completed=1,
            tasks_failed=0,
            latency_ms=1500,
            skills_exchanged=2,
            mhc_score=0.95,
        )

        # Obtém IVM atual
        ivm = await ivm_axiom.get_ivm("coder")

        # Obtém reward para BanditPolicy
        reward = ivm_axiom.calcular_reward("coder")
    """

    # Pesos base da fórmula do IVM (ajustados epigeneticamente)
    PESO_PRODUTIVIDADE_BASE = 0.4
    PESO_EFICIENCIA_BASE = 0.4
    PESO_COOPERACAO_BASE = 0.2

    # Federação de sinais: o E canônico combina eficiência de latência
    # (Chappie) e eficiência de orçamento de CPU (CpuAffinityManager).
    PESO_E_LATENCIA = 0.7
    PESO_E_CPU = 0.3
    CPU_BUDGET_PADRAO = 0.25  # teto homeostático por agente

    # Thresholds
    IVM_EXCELENTE = 0.9
    IVM_BOM = 0.7
    IVM_REGULAR = 0.5
    IVM_CRITICO = 0.3

    # Chaves para memória de curto prazo
    STM_KEY_METRICAS = "ivm_axiom_metricas"
    STM_KEY_HISTORICO = "ivm_axiom_historico"
    STM_KEY_CONFIG = "ivm_axiom_config"

    # Threshold homocisteína
    HOMOCYSTEINE_MAX_FAIL_RATIO = 0.3
    HOMOCYSTEINE_MIN_RECENT_TASKS = 5

    def __init__(
        self,
        latency_baseline_ms: float = 1000.0,
        db_path: Optional[Path] = None,
        stm_max_size: int = 1000,
        stm_ttl_seconds: Optional[int] = 86400,  # 24 horas
    ):
        """Inicializa o IVMAxiom.

        Args:
            latency_baseline_ms: Latência de referência para cálculo de eficiência
            db_path: Caminho para banco de dados SQLite (opcional, habilita persistência)
            stm_max_size: Tamanho máximo da memória de curto prazo
            stm_ttl_seconds: TTL das entradas na memória (default: 24h)
        """
        self.latency_baseline_ms = latency_baseline_ms

        # Normaliza db_path para usar PACKAGE_DIR se for relativo
        if db_path is not None and not db_path.is_absolute():
            db_path = PACKAGE_DIR / db_path
        self.db_path = db_path

        self.stm_max_size = stm_max_size
        self.stm_ttl_seconds = stm_ttl_seconds

        # Métricas atuais por agent
        self._metricas: Dict[str, IVMMetrics] = {}

        # Histórico por agent
        self._historico: Dict[str, AgentIVMRecord] = {}

        # Pool de homocisteína: rastreia falhas sem reciclagem
        # agent_name -> {"failed_since_last_success": int, "last_success": timestamp, "consecutive_failures": int}
        self._homocysteine_pool: Dict[str, Dict[str, Any]] = {}

        # Alerts threshold
        self._alert_threshold = self.IVM_REGULAR
        self._alerts_triggered: int = 0

        # Memória de curto prazo (persistência em disco)
        self._stm: Optional[ShortTermMemory] = None
        if db_path:
            self._iniciar_memoria_curto_prazo()

        logger.info(
            "[IVMAxiom] Inicializado | baseline=%.0fms | persistencia=%s | stm_max_size=%d",
            latency_baseline_ms,
            "ativa" if db_path else "inativa",
            stm_max_size,
        )

    def _iniciar_memoria_curto_prazo(self) -> None:
        """Inicializa sistema de memória de curto prazo com persistência."""
        try:
            self._stm = ShortTermMemory(
                max_size=self.stm_max_size,
                ttl_seconds=self.stm_ttl_seconds,
                db_path=self.db_path,
            )
            logger.info("[IVMAxiom] Memória de curto prazo inicializada | db=%s", self.db_path)
            
            # Carrega estado persisted ao inicializar
            self._carregar_estado()
        except Exception as e:
            logger.error("[IVMAxiom] Falha ao inicializar memória de curto prazo: %s", e)
            self._stm = None

    def _carregar_estado(self) -> None:
        """Carrega estado persisted da memória de curto prazo."""
        if not self._stm:
            return

        try:
            # Carrega todas as entradas e procura pelas chaves do IVM
            # ShortTermMemory armazena entradas com metadata
            todas_entradas = self._stm.get_all_with_metadata()
            
            metricas_data = {}
            historico_data = {}
            
            for entrada in todas_entradas:
                metadata = entrada.get("metadata", {})
                content = entrada.get("content", {})
                
                if metadata.get("chave") == self.STM_KEY_METRICAS:
                    # Merge de múltiplas atualizações de métricas
                    for agent_name, agent_data in content.items():
                        metricas_data[agent_name] = agent_data
                
                elif metadata.get("chave") == self.STM_KEY_HISTORICO:
                    # Merge de múltiplas atualizações de histórico
                    for agent_name, agent_data in content.items():
                        historico_data[agent_name] = agent_data
            
            # Restaura métricas
            for agent_name, agent_data in metricas_data.items():
                self._metricas[agent_name] = IVMMetrics.from_dict(agent_data)
            
            if metricas_data:
                logger.info(
                    "[IVMAxiom] Carregadas %d métricas da memória",
                    len(self._metricas),
                )

            # Restaura histórico
            for agent_name, agent_data in historico_data.items():
                self._historico[agent_name] = AgentIVMRecord.from_dict(agent_data)
            
            if historico_data:
                logger.info(
                    "[IVMAxiom] Carregado histórico de %d agents da memória",
                    len(self._historico),
                )
        except Exception as e:
            logger.error("[IVMAxiom] Falha ao carregar estado: %s", e, exc_info=True)

    def _salvar_estado(self, chave: str, dados: Dict[str, Any]) -> None:
        """Salva estado na memória de curto prazo."""
        if not self._stm:
            return

        try:
            self._stm.add(dados, metadata={"chave": chave, "tipo": "ivm_axiom"})
            logger.debug("[IVMAxiom] Estado salvo na memória | chave=%s", chave)
        except Exception as e:
            logger.error("[IVMAxiom] Falha ao salvar estado: %s", e)

    async def atualizar_metricas(
        self,
        agent_name: str,
        tasks_completed: int = 0,
        tasks_failed: int = 0,
        total_latency_ms: float = 0.0,
        skills_exchanged: int = 0,
        mhc_validation_score: float = 1.0,
        cpu_usage: Optional[float] = None,
        cpu_budget: Optional[float] = None,
    ) -> float:
        """Atualiza métricas de um agent e recalcula IVM.

        Args:
            agent_name: Nome do agent
            tasks_completed: Tarefas completadas com sucesso
            tasks_failed: Tarefas que falharam
            total_latency_ms: Latência total (ou média) em ms
            skills_exchanged: Skills trocados com outros agents
            mhc_validation_score: Score de validação MHC (0-1)
            cpu_usage: Uso de CPU atual (0-1) informado pelo CpuAffinityManager
            cpu_budget: Teto de budget de CPU do agente (default 25%)

        Returns:
            float: Novo IVM calculado
        """
        # Obtém ou cria métricas
        if agent_name not in self._metricas:
            self._metricas[agent_name] = IVMMetrics()
            self._historico[agent_name] = AgentIVMRecord(agent_name=agent_name)

        metricas = self._metricas[agent_name]

        # Atualiza produtividade
        metricas.tasks_completed += tasks_completed
        metricas.tasks_failed += tasks_failed
        total_tasks = metricas.tasks_completed + metricas.tasks_failed
        metricas.productivity_score = (
            metricas.tasks_completed / total_tasks if total_tasks > 0 else 0.0
        )

        # Atualiza eficiência de LATÊNCIA — SÓ quando há latência nova.
        # Chamadas apenas-CPU (reportar_uso_cpu) preservam o E de latência anterior.
        if tasks_completed > 0 and total_latency_ms > 0:
            metricas.total_latency_ms += total_latency_ms
            metricas.avg_latency_ms = metricas.total_latency_ms / metricas.tasks_completed
            latency_ratio = metricas.avg_latency_ms / self.latency_baseline_ms
            metricas.energy_efficiency_score = (
                min(1.0, 1.0 / latency_ratio) if latency_ratio > 0 else metricas.energy_efficiency_score
            )

        # Federação de sinais (unificação IVM): incorpora a eficiência de
        # orçamento de CPU (CpuAffinityManager, teto 25%) como dimensão do E.
        # NÃO sobrescreve o E de latência — os dois sinais são independentes.
        if cpu_usage is not None:
            budget = cpu_budget if cpu_budget else self.CPU_BUDGET_PADRAO
            metricas.cpu_usage_atual = max(0.0, min(1.0, cpu_usage))
            metricas.cpu_budget = budget
            metricas.cpu_efficiency_score = max(0.0, 1.0 - (metricas.cpu_usage_atual / budget) * 0.5)
            metricas.cpu_signal_ativo = True

        # E canônico composto: latência (0.7) + orçamento de CPU (0.3).
        # Se o sinal de CPU ainda não chegou, usa só latência (retrocompatível).
        e_final = metricas.energy_efficiency_score
        if metricas.cpu_signal_ativo:
            e_final = (
                self.PESO_E_LATENCIA * metricas.energy_efficiency_score
                + self.PESO_E_CPU * metricas.cpu_efficiency_score
            )

        # Atualiza cooperação
        metricas.skills_exchanged += skills_exchanged
        metricas.mhc_validation_score = mhc_validation_score
        # Cooperação = média entre skills exchanged (normalizado) e MHC score
        # Assuming 10 skills como referência para score máximo
        skills_score = min(1.0, metricas.skills_exchanged / 10.0)
        metricas.cooperation_score = (skills_score + metricas.mhc_validation_score) / 2.0

        # Calcula IVM com pesos base primeiro (para histórico)
        metricas.ivm = (
            metricas.productivity_score * self.PESO_PRODUTIVIDADE_BASE +
            e_final * self.PESO_EFICIENCIA_BASE +
            metricas.cooperation_score * self.PESO_COOPERACAO_BASE
        )

        metricas.last_updated = datetime.now(UTC)

        # Atualiza histórico (necessário antes do ajuste epigenético)
        self._historico[agent_name].update(metricas.ivm)

        # Ajusta pesos epigenéticos baseado no histórico do agente
        self._ajustar_pesos_epigeneticos(agent_name)

        # Recalcula IVM com pesos epigenéticos (por-agente)
        metricas.ivm = (
            metricas.productivity_score * metricas.productivity_weight +
            e_final * metricas.energy_weight +
            metricas.cooperation_score * metricas.cooperation_weight
        )

        # Detecta homocisteína (acúmulo de falhas sem reciclagem)
        homocysteine_alert = self._verificar_homocisteina(agent_name, tasks_completed, tasks_failed)

        # Verifica alertas de degradação
        await self._verificar_alerta(agent_name, metricas.ivm)

        # Se homocisteína detectada, registra no vault Obsidian
        if homocysteine_alert:
            await self._registrar_homocisteina_obsidian(agent_name, homocysteine_alert)

        # Salva estado na memória de curto prazo (persistência automática)
        self._persistir_apos_atualizacao(agent_name)

        logger.info(
            "[IVMAxiom] Métricas atualizadas | agent=%s | IVM=%.3f | P=%.3f E=%.3f C=%.3f | pesos=[P=%.2f E=%.2f C=%.2f]",
            agent_name,
            metricas.ivm,
            metricas.productivity_score,
            metricas.energy_efficiency_score,
            metricas.cooperation_score,
            metricas.productivity_weight,
            metricas.energy_weight,
            metricas.cooperation_weight,
        )

        return metricas.ivm

    def _persistir_apos_atualizacao(self, agent_name: str) -> None:
        """Persiste estado atualizado na memória de curto prazo."""
        if not self._stm:
            return

        try:
            # Prepara dados de métricas
            metricas_data = {
                agent: metricas.to_dict()
                for agent, metricas in self._metricas.items()
            }

            # Prepara dados de histórico
            historico_data = {
                agent: record.to_dict()
                for agent, record in self._historico.items()
            }

            # Salva métricas
            self._salvar_estado(self.STM_KEY_METRICAS, metricas_data)

            # Salva histórico
            self._salvar_estado(self.STM_KEY_HISTORICO, historico_data)

            # ✓ NOVO: Adiciona entrada individual no STM para cada atualização
            # Isso permite que o REM Sleep Engine consolide atualizações individuais
            metricas = self._metricas.get(agent_name)
            if metricas:
                entrada_individual = {
                    "agent_name": agent_name,
                    "current_ivm": metricas.ivm,
                    "productivity": metricas.productivity_score,
                    "efficiency": metricas.energy_efficiency_score,
                    "cooperation": metricas.cooperation_score,
                    "tasks_completed": metricas.tasks_completed,
                    "tasks_failed": metricas.tasks_failed,
                    "latency_ms": metricas.total_latency_ms,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                
                chave_entrada = f"ivm_update_{agent_name}_{datetime.now(UTC).timestamp()}"
                self._stm.add(entrada_individual, metadata={
                    "chave": chave_entrada,
                    "tipo": "ivm_update",
                    "agent_name": agent_name,
                    "current_ivm": metricas.ivm,
                    "trend": self.get_classificacao(metricas.ivm),
                })
                
                logger.debug(
                    "[IVMAxiom] Entrada individual persistida | agent=%s | IVM=%.3f",
                    agent_name, metricas.ivm,
                )

            logger.debug(
                "[IVMAxiom] Estado persistido | agents=%d | db=%s",
                len(self._metricas),
                self.db_path,
            )
        except Exception as e:
            logger.error("[IVMAxiom] Falha ao persistir estado: %s", e)

    def calcular_reward(self, agent_name: str) -> float:
        """Calcula reward para BanditPolicy baseado no IVM.

        Reward = IVM normalizado (0-1)
        Agents com IVM alto recebem reward alto (Lei da Compensação).

        Args:
            agent_name: Nome do agent

        Returns:
            float: Reward (0-1)
        """
        if agent_name not in self._metricas:
            return 0.0

        return self._metricas[agent_name].ivm

    def get_classificacao(self, ivm: float) -> str:
        """Classifica IVM em categorias."""
        if ivm >= self.IVM_EXCELENTE:
            return "excelente"
        elif ivm >= self.IVM_BOM:
            return "bom"
        elif ivm >= self.IVM_REGULAR:
            return "regular"
        elif ivm >= self.IVM_CRITICO:
            return "crítico"
        else:
            return "falha"

    def get_ivm(self, agent_name: str) -> float:
        """Obtém IVM atual de um agent."""
        if agent_name not in self._metricas:
            return 0.0
        return self._metricas[agent_name].ivm

    def get_todas_metricas(self) -> Dict[str, Dict[str, Any]]:
        """Obtém métricas de todos os agents."""
        return {
            agent: metricas.to_dict()
            for agent, metricas in self._metricas.items()
        }

    def get_ranking(self) -> List[Dict[str, Any]]:
        """Retorna ranking de agents por IVM."""
        ranking = []
        for agent_name, record in self._historico.items():
            ranking.append({
                "agent_name": agent_name,
                "current_ivm": record.current_ivm,
                "peak_ivm": record.peak_ivm,
                "trend": record.trend,
                "classificacao": self.get_classificacao(record.current_ivm),
            })

        # Ordena por IVM decrescente
        ranking.sort(key=lambda x: x["current_ivm"], reverse=True)
        return ranking

    async def _verificar_alerta(self, agent_name: str, ivm: float) -> None:
        """Verifica se deve disparar alerta de degradação."""
        if ivm < self._alert_threshold:
            classificacao = self.get_classificacao(ivm)
            logger.warning(
                "[IVMAxiom] 🚨 ALERTA DE DEGRADAÇÃO | agent=%s | IVM=%.3f | classificacao=%s",
                agent_name,
                ivm,
                classificacao,
            )
            self._alerts_triggered += 1

            # TODO: Enviar notificação para dashboard / webhook

    def _ajustar_pesos_epigeneticos(self, agent_name: str) -> None:
        """Ajusta pesos do IVM epigeneticamente baseado nas métricas do agente.

        Se o agente tem alta latência, reduz peso de eficiência e aumenta
        peso de produtividade. Se tem baixa cooperação, reduz peso desse
        fator. Isso permite que o IVM se adapte ao perfil do agente sem
        alterar o código genético (pesos base).

        AGORA por-agente: cada `IVMMetrics` carrega seus próprios pesos,
        eliminando o split-brain onde um agente com alta latência desviava
        os pesos de TODOS os outros.
        """
        metrics = self._metricas.get(agent_name)
        if not metrics or metrics.tasks_completed < 1:
            metrics.productivity_weight = self.PESO_PRODUTIVIDADE_BASE
            metrics.energy_weight = self.PESO_EFICIENCIA_BASE
            metrics.cooperation_weight = self.PESO_COOPERACAO_BASE
            return

        peso_prod = self.PESO_PRODUTIVIDADE_BASE
        peso_efi = self.PESO_EFICIENCIA_BASE
        peso_coop = self.PESO_COOPERACAO_BASE

        latency_ratio = metrics.avg_latency_ms / self.latency_baseline_ms if self.latency_baseline_ms > 0 else 1.0
        if latency_ratio > 2.0:
            shift = min(0.1, (latency_ratio - 2.0) * 0.02)
            peso_efi = max(0.2, self.PESO_EFICIENCIA_BASE - shift)
            peso_prod = min(0.6, self.PESO_PRODUTIVIDADE_BASE + shift)

        # Se cooperação consistentemente baixa (< 0.3), reduz peso
        if metrics.cooperation_score < 0.3 and metrics.tasks_completed > 5:
            peso_coop = max(0.05, self.PESO_COOPERACAO_BASE - 0.1)
            peso_prod = min(0.6, peso_prod + 0.05)

        metrics.productivity_weight = round(peso_prod, 3)
        metrics.energy_weight = round(peso_efi, 3)
        metrics.cooperation_weight = round(peso_coop, 3)

    def _verificar_homocisteina(
        self,
        agent_name: str,
        tasks_completed: int,
        tasks_failed: int,
    ) -> Optional[Dict[str, Any]]:
        """Detecta acúmulo de homocisteína — falhas sem reciclagem.

        O ciclo de metilação produz homocisteína como subproduto.
        Quando falhas se acumulam sem sucessos (reciclagem),
        a homocisteína sobe e indica toxicidade sistêmica.
        """
        pool = self._homocysteine_pool.setdefault(agent_name, {
            "failed_since_last_success": 0,
            "last_success": None,
            "consecutive_failures": 0,
            "peak_fail_ratio": 0.0,
        })

        if tasks_completed > 0:
            pool["failed_since_last_success"] = 0
            pool["consecutive_failures"] = 0
            pool["last_success"] = datetime.now(UTC).isoformat()
            return None

        if tasks_failed > 0:
            pool["failed_since_last_success"] += tasks_failed
            pool["consecutive_failures"] += tasks_failed

        total_tasks = tasks_completed + tasks_failed
        if total_tasks == 0:
            return None

        fail_ratio = tasks_failed / total_tasks
        if fail_ratio > pool["peak_fail_ratio"]:
            pool["peak_fail_ratio"] = fail_ratio

        # Verifica se ultrapassou threshold
        record = self._historico.get(agent_name)
        total_history = len(record.history) if record else 0

        if (pool["consecutive_failures"] >= self.HOMOCYSTEINE_MIN_RECENT_TASKS
                and pool["failed_since_last_success"] >= self.HOMOCYSTEINE_MIN_RECENT_TASKS
                and fail_ratio >= self.HOMOCYSTEINE_MAX_FAIL_RATIO):

            logger.warning(
                "[IVMAxiom] HOMOCISTEINA ELEVADA | agent=%s | falhas_sem_reciclagem=%d | "
                "consecutivas=%d | taxa_falha=%.2f",
                agent_name,
                pool["failed_since_last_success"],
                pool["consecutive_failures"],
                fail_ratio,
            )
            return {
                "agent_name": agent_name,
                "failed_since_last_success": pool["failed_since_last_success"],
                "consecutive_failures": pool["consecutive_failures"],
                "fail_ratio": fail_ratio,
                "total_history": total_history,
            }

        return None

    async def _registrar_homocisteina_obsidian(self, agent_name: str, alert_data: Dict[str, Any]) -> None:
        """Registra alerta de homocisteína no vault Obsidian."""
        try:
            from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
            sub = SubconsciousAPI()
            conteudo = (
                f"## Alerta de Homocisteína - {agent_name}\n\n"
                f"- **Agente**: {agent_name}\n"
                f"- **Falhas sem reciclagem**: {alert_data['failed_since_last_success']}\n"
                f"- **Falhas consecutivas**: {alert_data['consecutive_failures']}\n"
                f"- **Taxa de falha**: {alert_data['fail_ratio']:.2%}\n"
                f"- **Total no histórico**: {alert_data['total_history']}\n"
                f"- **Timestamp**: {datetime.now(UTC).isoformat()}\n\n"
                f"### Recomendação\n\n"
                f"O agente {agent_name} está acumulando falhas sem reciclagem bem-sucedida. "
                f"Considere: autofagia do agente, revisão de configuração, ou aumento do "
                f"threshold de alerta.\n"
            )
            await sub.escrever_curto_prazo(
                nome=f"homocisteina_{agent_name}_{datetime.now(UTC).timestamp():.0f}",
                conteudo=conteudo,
                tags=["#homocisteina", f"#{agent_name}", "#alerta"],
            )
            logger.info("[IVMAxiom] Alerta de homocisteína registrado no Obsidian | agent=%s", agent_name)
        except Exception as e:
            logger.warning("[IVMAxiom] Falha ao registrar homocisteína no Obsidian: %s", e)

    def get_homocysteine_status(self) -> Dict[str, Any]:
        """Retorna status do pool de homocisteína."""
        agents_em_homocisteina = sum(
            1 for p in self._homocysteine_pool.values()
            if p["failed_since_last_success"] >= self.HOMOCYSTEINE_MIN_RECENT_TASKS
        )
        return {
            "agents_monitored": len(self._homocysteine_pool),
            "agents_em_homocisteina": agents_em_homocisteina,
            "pool": dict(self._homocysteine_pool),
        }

    def get_status(self) -> Dict[str, Any]:
        """Retorna status atual do IVMAxiom."""
        agents_ativos = len(self._metricas)
        agents_excelentes = sum(
            1 for m in self._metricas.values() if m.ivm >= self.IVM_EXCELENTE
        )
        agents_criticos = sum(
            1 for m in self._metricas.values() if m.ivm < self.IVM_CRITICO
        )

        return {
            "agents_ativos": agents_ativos,
            "agents_excelentes": agents_excelentes,
            "agents_criticos": agents_criticos,
            "alerts_triggered": self._alerts_triggered,
            "latency_baseline_ms": self.latency_baseline_ms,
            "weights": {
                "productivity_base": self.PESO_PRODUTIVIDADE_BASE,
                "energy_efficiency_base": self.PESO_EFICIENCIA_BASE,
                "cooperation_base": self.PESO_COOPERACAO_BASE,
                "por_agente": True,
            },
            "thresholds": {
                "excelente": self.IVM_EXCELENTE,
                "bom": self.IVM_BOM,
                "regular": self.IVM_REGULAR,
                "critico": self.IVM_CRITICO,
            },
            "persistencia": {
                "ativa": self._stm is not None,
                "db_path": str(self.db_path) if self.db_path else None,
                "stm_status": self._stm.swap_status() if self._stm else None,
            },
        }

    async def get_detalhes_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Obtém detalhes completos de um agent."""
        if agent_name not in self._metricas:
            return None

        metricas = self._metricas[agent_name]
        historico = self._historico[agent_name]

        return {
            "metricas_atuais": metricas.to_dict(),
            "historico": {
                "peak_ivm": historico.peak_ivm,
                "min_ivm": historico.min_ivm,
                "trend": historico.trend,
                "amostras": len(historico.history),
            },
            "classificacao": self.get_classificacao(metricas.ivm),
            "reward_bandit": self.calcular_reward(agent_name),
        }

    def limpar_memoria(self) -> None:
        """Limpa memória de curto prazo (apenas se persistência estiver ativa)."""
        if self._stm:
            self._stm.clear()
            logger.info("[IVMAxiom] Memória de curto prazo limpa")

    def obter_status_memoria(self) -> Optional[Dict[str, Any]]:
        """Obtém status da memória de curto prazo."""
        if self._stm:
            return self._stm.swap_status()
        return None


# Singleton global
ivm_axiom: Optional[IVMAxiom] = None
_init_lock: threading.Lock = threading.Lock()


def get_ivm_axiom() -> IVMAxiom:
    """Retorna singleton do IVMAxiom.

    Se o núcleo Chappie já registrou uma instância canônica (persistida) via
    ``_set_chappie(ivm=...)``, ela é preferida. Isso garante que os Agentes
    (escritores de telemetria) e os Observadores (leitores, ex.: no_system_analysis,
    ivm_compliance) compartilhem o MESMO pool de IVM. Sem essa unicidade o sistema
    desenvolve split-brain metabólico: os agentes alimentam um singleton em memória
    que nenhum observador lê, enquanto os observadores leem um pool vazio persistido
    em disco (ver ARCHITECTURE §12 — "IVM cego").
    """
    global ivm_axiom
    if ivm_axiom is None:
        with _init_lock:
            if ivm_axiom is None:
                # Tenta reaproveitar a instância canônica registrada no Chappie.
                try:
                    from iaglobal.chappie import _get_chappie
                    registered = _get_chappie().get("ivm")
                    if isinstance(registered, IVMAxiom):
                        ivm_axiom = registered
                        return ivm_axiom
                except Exception:
                    pass
                ivm_axiom = IVMAxiom()
    return ivm_axiom


def init_ivm_axiom_com_persistencia(
    db_path: Optional[Path] = None,
    latency_baseline_ms: float = 1000.0,
    stm_max_size: int = 1000,
    stm_ttl_seconds: Optional[int] = 86400,
) -> IVMAxiom:
    """Inicializa IVMAxiom singleton com persistência em disco.

    Se db_path for relativo, é normalizado para PACKAGE_DIR.

    Args:
        db_path: Caminho para banco de dados SQLite (default: PACKAGE_DIR / "memory" / "ivm.db")
        latency_baseline_ms: Latência de referência (ms)
        stm_max_size: Tamanho máximo da memória de curto prazo
        stm_ttl_seconds: TTL das entradas (default: 24h)

    Returns:
        IVMAxiom: Singleton inicializado
    """
    global ivm_axiom

    if db_path is None:
        db_path = PACKAGE_DIR / "memory" / "ivm.db"
    elif not db_path.is_absolute():
        db_path = PACKAGE_DIR / db_path

    with _init_lock:
        ivm_axiom = IVMAxiom(
            latency_baseline_ms=latency_baseline_ms,
            db_path=db_path,
            stm_max_size=stm_max_size,
            stm_ttl_seconds=stm_ttl_seconds,
        )
    # Registra como instância canônica do Chappie para unificar escrita (agentes)
    # e leitura (observadores) de telemetria IVM — elimina o split-brain metabólico.
    try:
        from iaglobal.chappie import _set_chappie
        _set_chappie(ivm=ivm_axiom)
    except Exception:
        pass
    logger.info(
        "[IVMAxiom] Singleton inicializado com persistência | db=%s",
        db_path,
    )
    return ivm_axiom