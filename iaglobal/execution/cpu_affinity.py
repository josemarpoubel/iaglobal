# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/execution/cpu_affinity.py
#
# Weight-based CPU Budget Scheduler (Assíncrono)
#
# Em vez de fixar agentes em núcleos específicos (core pinning), cada agente
# recebe um budget de CPU (padrão: 25%). O ResourceManager distribui a carga
# por prioridade, não por localização física.
#
# Princípios:
# - Cross-platform (sem chamadas de SO — roda em Linux, Windows, macOS)
# - Teto de 25% por agente (homeostase de rede)
# - IVM (Índice de Viabilidade Metabólica) para monitoramento interno
# - Modo de sobrevivência (redução temporária para 10%)
# - Sistema de pontuação (fitness_score) no genome.json
# - Auto-crítica de eficiência energética
# - Totalmente assíncrono (asyncio)

import os
import hashlib
import time
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from iaglobal.utils.logger import logger


# =========================================================================
# CONSTANTES DO SISTEMA
# =========================================================================

BUDGET_PADRAO = 0.25        # 25% — teto homeostático por agente
BUDGET_SOBREVIVENCIA = 0.10 # 10% — modo nômade / sobrevivência
BUDGET_DEEP_SLEEP = 0.05    # 5% — ciclo de repouso / estase
BUDGET_ADRENALINA = 0.50    # 50% — modo burst para emergências
IVM_THRESHOLD_CRITICO = 0.3
IVM_THRESHOLD_EXCELENCIA = 0.8
FITNESS_DECAY = 0.95        # decaimento temporal do fitness a cada ciclo
FLUSH_INTERVAL = 5.0         # intervalo (s) entre persists em lote do fitness
FLUSH_MAX_BATCH = 50         # max registros no buffer antes de flush forçado


# =========================================================================
# DATACLASSES DE METADADOS
# =========================================================================

@dataclass
class AgentCpuMetrics:
    """Métricas de CPU e recursos por agente."""
    agent_id: str
    cpu_budget: float = BUDGET_PADRAO
    cpu_usage_atual: float = 0.0       # 0.0 a 1.0
    tasks_completadas: int = 0
    tasks_falhas: int = 0
    uptime_inicio: float = field(default_factory=time.time)
    obsidian_notes_escritas: int = 0
    fitness_score: float = 0.5
    ivm_atual: float = 0.5
    em_modo_sobrevivencia: bool = False
    ultimo_ajuste: float = field(default_factory=time.time)

    @property
    def uptime(self) -> float:
        return time.time() - self.uptime_inicio

    @property
    def produtividade(self) -> float:
        total = self.tasks_completadas + self.tasks_falhas
        if total == 0:
            return 0.5
        return self.tasks_completadas / total

    @property
    def eficiencia_energetica(self) -> float:
        """E = inverso do uso de CPU. Se usa menos de 25%, E aumenta."""
        if self.cpu_usage_atual <= 0.01:
            return 1.0
        ratio = self.cpu_usage_atual / self.cpu_budget
        if ratio <= 1.0:
            return 1.0 - (ratio * 0.5)
        return max(0.0, 1.0 - ratio)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "cpu_budget": self.cpu_budget,
            "cpu_usage_atual": self.cpu_usage_atual,
            "tasks_completadas": self.tasks_completadas,
            "tasks_falhas": self.tasks_falhas,
            "uptime": round(self.uptime, 1),
            "obsidian_notes_escritas": self.obsidian_notes_escritas,
            "fitness_score": round(self.fitness_score, 3),
            "ivm_atual": round(self.ivm_atual, 3),
            "produtividade": round(self.produtividade, 3),
            "eficiencia_energetica": round(self.eficiencia_energetica, 3),
            "em_modo_sobrevivencia": self.em_modo_sobrevivencia,
        }


# =========================================================================
# RESOURCE MANAGER — distribuição por prioridade
# =========================================================================

class ResourceManager:
    """Distribui budget de CPU entre agentes com base em prioridade e fitness.

    Agentes com fitness alto podem requisitar mais CPU.
    Agentes em background operam com 5%.
    """

    BUDGET_MINIMO = 0.05   # 5% — mínimo vital
    BUDGET_PRIORIDADE = 0.35  # 35% — para agentes de alta prioridade

    def __init__(self):
        self._lock = None
        self._agents_por_prioridade: Dict[str, float] = {}

    @property
    def lock(self):
        """Lazy initialization para evitar erros de event loop no import."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def alocar(self, agentes: List[Tuple[str, float]]) -> Dict[str, float]:
        """Distribui budgets proporcionalmente à prioridade de cada agente."""
        if not agentes:
            return {}

        async with self.lock:
            total_prioridade = sum(p for _, p in agentes) or 1.0
            budgets = {}
            for agent_id, prioridade in agentes:
                share = prioridade / total_prioridade
                raw = share * len(agentes) * BUDGET_PADRAO
                budget = max(self.BUDGET_MINIMO, min(BUDGET_PADRAO, raw))
                if prioridade >= 0.8:
                    budget = max(budget, self.BUDGET_PRIORIDADE)
                    budget = min(budget, BUDGET_PADRAO)
                budgets[agent_id] = round(budget, 3)
                self._agents_por_prioridade[agent_id] = prioridade
            return budgets

    async def obter_prioridade(self, agent_id: str) -> float:
        async with self.lock:
            return self._agents_por_prioridade.get(agent_id, 0.5)


# =========================================================================
# CPU AFFINITY MANAGER — nova versão cross-platform
# =========================================================================

class CpuAffinityManager:
    """Gerenciador de budget de CPU por agente (Weight-based Scheduler)."""

    def __init__(self):
        self._lock = None
        self._total_cores: int = os.cpu_count() or 1
        self._agents: Dict[str, AgentCpuMetrics] = {}
        self._budgets: Dict[str, float] = {}
        self._last_agent_map: Dict[str, int] = {}
        self.resource_manager = ResourceManager()
        self._metabolic_state = "NORMAL" # NORMAL, DEEP_SLEEP, ADRENALINE
        self._adrenaline_expiry = 0.0
        self._fitness_buffer: Dict[str, float] = {}
        self._flush_task: Optional[asyncio.Task] = None

    @property
    def lock(self):
        """Lazy initialization para evitar erros de event loop no import."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    # ==============================================================
    # UTILITÁRIOS INTERNOS
    # ==============================================================

    @staticmethod
    def _hash_agent(agent_id: str) -> str:
        """Hash determinístico do ID do agente."""
        try:
            int(agent_id[:8], 16)
            return agent_id[:8]
        except ValueError:
            return hashlib.sha256(agent_id.encode()).hexdigest()[:8]

    def _core_from_hash(self, agent_id: str) -> int:
        """Deriva um core lógico do hash (sem fixação real)."""
        return int(self._hash_agent(agent_id), 16) % self._total_cores

    def _get_or_create_metrics(self, agent_id: str) -> AgentCpuMetrics:
        # Nota: Assume-se que esta função seja chamada DENTRO do lock
        if agent_id not in self._agents:
            self._agents[agent_id] = AgentCpuMetrics(agent_id=agent_id)
        return self._agents[agent_id]

    # ==============================================================
    # MÉTODOS LEGADOS (backward-compatible)
    # ==============================================================

    async def assign_core_deterministic(self, agent_id: str) -> int:
        core = self._core_from_hash(agent_id)
        async with self.lock:
            self._last_agent_map[agent_id] = core
            self._get_or_create_metrics(agent_id)
            if agent_id not in self._budgets:
                self._budgets[agent_id] = BUDGET_PADRAO
        return core

    async def pin_to_hash(self, agent_id: str) -> int:
        core = self._core_from_hash(agent_id)
        async with self.lock:
            self._last_agent_map[agent_id] = core
            self._get_or_create_metrics(agent_id)
        return core

    async def pin_current(self, agent_id: str):
        core = await self.pin_to_hash(agent_id)
        return core

    async def map_balanced(self, agents: List[str]) -> Dict[str, int]:
        if not agents:
            return {}

        assignment = {}
        async with self.lock:
            budget = min(BUDGET_PADRAO, 1.0 / max(len(agents), 1))
            for agent in agents:
                self._budgets[agent] = round(budget, 3)
                core = self._core_from_hash(agent)
                self._last_agent_map[agent] = core
                metrics = self._get_or_create_metrics(agent)
                metrics.cpu_budget = round(budget, 3)
                assignment[agent] = core

        logger.info(
            "[CPU] Distribuição balanceada: %d agentes, %.0f%% budget cada, %d cores",
            len(agents), budget * 100, self._total_cores,
        )
        return assignment

    async def dispersion_report(self) -> dict:
        async with self.lock:
            total_agents = len(self._agents)
            per_core: Dict[int, List[str]] = {}
            for agent_id in self._agents:
                core = self._last_agent_map.get(agent_id, self._core_from_hash(agent_id))
                per_core.setdefault(core, []).append(agent_id)

            counts = {c: len(agents) for c, agents in per_core.items()}
            for c in range(self._total_cores):
                counts.setdefault(c, 0)

            total_mapped = sum(counts.values()) or 1
            max_load = max(counts.values())
            min_load = min(counts.values())
            imbalance = (max_load - total_mapped / self._total_cores) / (total_mapped / self._total_cores) if total_mapped else 0

            budgets = dict(self._budgets)
            ivm_medio = 0.0
            fitness_medio = 0.0
            agentes_em_sobrevivencia = 0
            if self._agents:
                ivm_medio = sum(m.ivm_atual for m in self._agents.values()) / len(self._agents)
                fitness_medio = sum(m.fitness_score for m in self._agents.values()) / len(self._agents)
                agentes_em_sobrevivencia = sum(1 for m in self._agents.values() if m.em_modo_sobrevivencia)

            return {
                "total_cores": self._total_cores,
                "agents_mapped": total_agents,
                "max_load": max_load,
                "min_load": min_load,
                "imbalance": round(imbalance, 2),
                "efficiency": round(1.0 - abs(imbalance) * 0.1, 3),
                "per_core": {str(k): v for k, v in per_core.items()},
                "distribution": counts,
                "ivm_medio": round(ivm_medio, 3),
                "fitness_medio": round(fitness_medio, 3),
                "total_agents": total_agents,
                "budgets": budgets,
                "agentes_em_sobrevivencia": agentes_em_sobrevivencia,
                "total_budget_alocado": round(sum(budgets.values()), 3) if budgets else 0,
            }

    async def rebalance_if_needed(self, *args, **kwargs) -> bool:
        """Corrige desequilíbrio de budget redistribuindo por prioridade/fitness
        (via ResourceManager), em vez de achatar todos os agentes para o mesmo
        valor. Antes, esta função chamava map_balanced() e apagava o próprio
        sinal de fitness_score que update_fitness() vinha calculando."""
        async with self.lock:
            if not self._budgets:
                return False

            budgets_list = list(self._budgets.values())
            if not budgets_list:
                return False

            max_budget = max(budgets_list)
            min_budget = min(budgets_list)
            agents_list = list(self._budgets.keys())

            # Snapshot de fitness sob o mesmo lock — evita ler métricas de um
            # agente que está sendo mutado por outra coroutine ao mesmo tempo.
            prioridades = [
                (agent_id, self._agents[agent_id].fitness_score if agent_id in self._agents else 0.5)
                for agent_id in agents_list
            ]

        if max_budget - min_budget <= 0.1 or len(agents_list) <= 1:
            return False

        # resource_manager tem seu próprio asyncio.Lock — chamado fora do
        # self.lock para evitar contenção cruzada entre os dois locks.
        novos_budgets = await self.resource_manager.alocar(prioridades)

        async with self.lock:
            for agent_id, budget in novos_budgets.items():
                self._budgets[agent_id] = budget
                metrics = self._get_or_create_metrics(agent_id)
                metrics.cpu_budget = budget
                metrics.ultimo_ajuste = time.time()

        logger.info(
            "[CPU] Rebalanceamento por prioridade/fitness concluído (%d agentes).",
            len(agents_list),
        )
        return True

    # ==============================================================
    # NOVOS MÉTODOS — Budget de CPU
    # ==============================================================

    async def set_cpu_budget(self, agent_id: str, budget: float) -> None:
        teto = BUDGET_ADRENALINA if self._metabolic_state == "ADRENALINE" else BUDGET_PADRAO
        budget = max(0.0, min(teto, budget))
        async with self.lock:
            self._budgets[agent_id] = round(budget, 3)
            metrics = self._get_or_create_metrics(agent_id)
            metrics.cpu_budget = round(budget, 3)
            metrics.ultimo_ajuste = time.time()

    async def entrar_estase(self):
        async with self.lock:
            self._metabolic_state = "DEEP_SLEEP"
            for agent_id in self._budgets:
                self._budgets[agent_id] = BUDGET_DEEP_SLEEP
                metrics = self._get_or_create_metrics(agent_id)
                metrics.cpu_budget = BUDGET_DEEP_SLEEP
        logger.info("[CPU] 🌙 Entrando em DEEP SLEEP: Ritmo metabólico reduzido para 5%%.")

    async def disparar_adrenalina(self, agent_id: str, duracao: float = 30.0):
        async with self.lock:
            self._metabolic_state = "ADRENALINE"
            self._adrenaline_expiry = time.time() + duracao
        await self.set_cpu_budget(agent_id, BUDGET_ADRENALINA)
        logger.warning("[CPU] ⚡ ADRENALINA: Agente %s em Burst Mode (50%% CPU) por %.1fs", agent_id, duracao)

    async def atualizar_estado_metabolico(self):
        async with self.lock:
            if self._metabolic_state == "ADRENALINE" and time.time() > self._adrenaline_expiry:
                self._metabolic_state = "NORMAL"
                logger.info("[CPU] 📉 Adrenalina esgotada. Retornando à homeostase normal.")

    async def get_cpu_budget(self, agent_id: str) -> float:
        async with self.lock:
            return self._budgets.get(agent_id, BUDGET_PADRAO)

    async def get_all_budgets(self) -> Dict[str, float]:
        async with self.lock:
            return dict(self._budgets)

    async def survival_mode(self, agent_id: str) -> None:
        await self.set_cpu_budget(agent_id, BUDGET_SOBREVIVENCIA)
        async with self.lock:
            metrics = self._get_or_create_metrics(agent_id)
            metrics.em_modo_sobrevivencia = True
        logger.info("[CPU] Agente %s em modo de sobrevivência: budget=10%%", agent_id)

    async def restore_budget(self, agent_id: str) -> None:
        await self.set_cpu_budget(agent_id, BUDGET_PADRAO)
        async with self.lock:
            metrics = self._get_or_create_metrics(agent_id)
            metrics.em_modo_sobrevivencia = False
        logger.info("[CPU] Agente %s restaurado ao budget padrão: 25%%", agent_id)

    # ==============================================================
    # PRIVILÉGIO DE PROCESSAMENTO DINÂMICO — Boost de Prioridade
    # ==============================================================

    async def set_priority_boost(self, agent_ids: List[str], boost_percent: int = 50) -> None:
        """Aumenta temporariamente o budget de agentes específicos em um batch crítico.
        
        Args:
            agent_ids: Lista de IDs dos agentes que receberão o boost
            boost_percent: Percentual de CPU budget (default: 50% = BUDGET_ADRENALINA)
        """
        # Converte para decimal e limita ao teto de adrenalina
        boost = min(BUDGET_ADRENALINA, boost_percent / 100.0)
        async with self.lock:
            for aid in agent_ids:
                metrics = self._agents.get(aid)
                if metrics:
                    metrics.cpu_budget = boost
                    metrics.ultimo_ajuste = time.time()
                    self._budgets[aid] = boost
                    logger.info(
                        "[CPU] ⚡ Boost de prioridade aplicado: %s → %.0f%%",
                        aid, boost * 100
                    )
                else:
                    logger.debug("[CPU] Agente %s não registrado para boost", aid)
        
        logger.info(
            "[CPU] 🚀 Batch crítico com %d agentes em modo de alta prioridade (%.0f%% CPU)",
            len(agent_ids), boost * 100
        )

    async def reset_budgets(self) -> None:
        """Reseta todos os agentes para o padrão de 25% (homeostase)."""
        async with self.lock:
            for agent_id in self._budgets:
                self._budgets[agent_id] = BUDGET_PADRAO
                metrics = self._get_or_create_metrics(agent_id)
                metrics.cpu_budget = BUDGET_PADRAO
                metrics.ultimo_ajuste = time.time()
                metrics.em_modo_sobrevivencia = False
        logger.info("[CPU] 📉 Homeostase restaurada: todos os agentes em 25%% CPU")

    # ==============================================================
    # CONTEXT MANAGER — Boost Temporário para Batches
    # ==============================================================

    async def enter_critical_batch(self, agent_ids: List[str], boost_percent: int = 60) -> Dict[str, float]:
        """
        Entra em modo de batch crítico: salva budgets anteriores, aplica boost.
        Retorna dict `{agent_id: budget_anterior}` para restore seletivo.

        Exemplo:
            saved = await cpu_affinity.enter_critical_batch(['critic', 'reviewer'])
            try:
                resultado = await processar_batch()
            finally:
                await cpu_affinity.exit_critical_batch(saved)
        """
        saved = {}
        async with self.lock:
            for aid in agent_ids:
                if aid in self._budgets:
                    saved[aid] = self._budgets[aid]
                else:
                    metrics = self._agents.get(aid)
                    saved[aid] = metrics.cpu_budget if metrics else BUDGET_PADRAO
        await self.set_priority_boost(agent_ids, boost_percent)
        return saved

    async def exit_critical_batch(self, saved_budgets: Dict[str, float]) -> None:
        """
        Restaura APENAS os agents incluídos em `saved_budgets` para seus
        budgets anteriores. Não afeta agents não relacionados.
        """
        async with self.lock:
            for aid, prev_budget in saved_budgets.items():
                self._budgets[aid] = prev_budget
                metrics = self._agents.get(aid)
                if metrics:
                    metrics.cpu_budget = prev_budget
                    metrics.ultimo_ajuste = time.time()

    # ==============================================================
    # IVM — Índice de Viabilidade Metabólica
    # ==============================================================
    # DEPRECATED: este IVM é de uso interno do scheduler (feedback de
    # sobrevivência/mitose). O IVM CANÔNICO do sistema é IVMAxiom
    # (iaglobal.chappie.ivm_axiom), que agora também consome o sinal de
    # CPU deste módulo via reportar_uso_cpu. Não use para rankings de
    # agentes, relatórios ou rewards do BanditPolicy.

    async def calcular_ivm(self, agent_id: str,
                           produtividade: Optional[float] = None,
                           cpu_usage: Optional[float] = None,
                           obsidian_notes: Optional[int] = None) -> float:
        
        async with self.lock:
            metrics = self._get_or_create_metrics(agent_id)
            
            # Realiza cópias locais dentro do lock para evitar race conditions no cálculo
            p = produtividade if produtividade is not None else metrics.produtividade
            cpu = cpu_usage if cpu_usage is not None else metrics.cpu_usage_atual
            budget = metrics.cpu_budget
            notes = obsidian_notes if obsidian_notes is not None else metrics.obsidian_notes_escritas

        if cpu <= 0.01:
            e = 1.0
        else:
            ratio = cpu / budget
            if ratio <= 1.0:
                e = 1.0 - (ratio * 0.5)
            else:
                e = max(0.0, 1.0 - ratio)

        c = min(1.0, notes / 10.0)

        ivm = (p * 0.4) + (e * 0.4) + (c * 0.2)
        ivm = max(0.0, min(1.0, ivm))

        async with self.lock:
            metrics.ivm_atual = ivm

        return ivm

    async def monitorar_metabolismo(self, agent_id: str) -> dict:
        async with self.lock:
            metrics = self._get_or_create_metrics(agent_id)
            metrics_dict = metrics.to_dict()

        # IVM canônico via IVMAxiom (fallback para métrica local)
        ivm = metrics.ivm_atual
        try:
            from iaglobal.chappie import _get_chappie
            ivm_inst = _get_chappie().get("ivm")
            if ivm_inst is not None:
                ivm = ivm_inst.get_ivm(agent_id)
        except Exception:
            pass

        if ivm < IVM_THRESHOLD_CRITICO:
            acao = "apoptose"
            motivo = "baixa_viabilidade_metabolica"
            try:
                from iaglobal.evolution.epigenetic import epigenetic_memory
                await asyncio.to_thread(epigenetic_memory.gravar_cicatriz, agent_id, motivo, 0.1)
            except Exception as e:
                logger.debug("[CPU] Falha ao gravar marca epigenética: %s", e)
        elif ivm > IVM_THRESHOLD_EXCELENCIA:
            acao = "mitose"
            motivo = "replicacao_de_sucesso"
        else:
            acao = "monitorar"
            motivo = "dentro_do_esperado"

        async with self.lock:
            metrics.ivm_atual = ivm

        return {
            "acao": acao,
            "motivo": motivo,
            "ivm": round(ivm, 3),
            "agente": agent_id,
            "metrics": metrics_dict,
        }

    # ==============================================================
    # FITNESS SCORE — Sistema de Pontuação
    # ==============================================================

    async def update_fitness(self, agent_id: str,
                             trabalho_realizado: float = 0.0,
                             custo_cpu: float = 0.0,
                             uptime_segundos: float = 0.0,
                             obsidian_notes: int = 0) -> float:
        
        async with self.lock:
            metrics = self._get_or_create_metrics(agent_id)
            score = metrics.fitness_score * FITNESS_DECAY

            if custo_cpu > 0:
                eficiencia = trabalho_realizado / custo_cpu
                score += eficiencia * 0.2

            confiabilidade = min(1.0, uptime_segundos / 3600.0)
            score += confiabilidade * 0.15

            contribuicao = min(1.0, obsidian_notes / 20.0)
            score += contribuicao * 0.15

            score = max(0.0, min(1.0, score))

            metrics.fitness_score = score
            if obsidian_notes:
                metrics.obsidian_notes_escritas += obsidian_notes

        await self._persist_fitness(agent_id, score)
        return score

    async def get_fitness(self, agent_id: str) -> float:
        async with self.lock:
            metrics = self._agents.get(agent_id)
            return metrics.fitness_score if metrics else 0.5

    async def _start_flush_loop(self) -> None:
        """Inicia o loop de flush de fundo se ainda não estiver rodando."""
        if self._flush_task is not None and not self._flush_task.done():
            return
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def _flush_loop(self) -> None:
        """Loop de fundo que persiste o buffer em lote a cada FLUSH_INTERVAL."""
        while True:
            await asyncio.sleep(FLUSH_INTERVAL)
            async with self.lock:
                batch = self._fitness_buffer.copy()
                self._fitness_buffer.clear()
            await self._flush_batch(batch)

    async def _flush_batch(self, batch: Dict[str, float]) -> None:
        """Escreve um lote de fitness scores em disco em paralelo (1 thread por arquivo)."""
        if not batch:
            return
        tasks = []
        for agent_id, score in batch.items():
            tasks.append(self._write_single_fitness(agent_id, score))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _write_single_fitness(self, agent_id: str, score: float) -> None:
        """Escreve um único genome.json em disco (executado em thread pool)."""
        genome_path = self._resolve_genome_path(agent_id)
        if not genome_path:
            return
        try:
            await asyncio.to_thread(genome_path.parent.mkdir, parents=True, exist_ok=True)
            if genome_path.exists():
                raw_data = await asyncio.to_thread(genome_path.read_text)
                data = json.loads(raw_data)
            else:
                data = {"agent_id": agent_id, "genome": {}}
            data["fitness_score"] = round(score, 3)
            data["ultima_atualizacao"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            await asyncio.to_thread(genome_path.write_text, json_str)
        except Exception as e:
            logger.debug("[CPU] Não foi possível persistir fitness: %s", e)

    async def _persist_fitness(self, agent_id: str, score: float) -> None:
        """Bufferiza fitness em memória. Flush em lote via _flush_loop."""
        await self._start_flush_loop()
        async with self.lock:
            self._fitness_buffer[agent_id] = score
            if len(self._fitness_buffer) >= FLUSH_MAX_BATCH:
                batch = self._fitness_buffer.copy()
                self._fitness_buffer.clear()
        # flush forçado fora do lock para evitar deadlock
        if batch:
            await self._flush_batch(batch)

    @staticmethod
    def _resolve_genome_path(agent_id: str) -> Optional[Path]:
        try:
            from iaglobal._paths import JSON_DIR
            return JSON_DIR / f"genome_{agent_id}.json"
        except Exception:
            return None

    # ==============================================================
    # AUTO-CRÍTICA — Monitoramento de Eficiência
    # ==============================================================

    async def auto_critica(self, agent_id: str) -> dict:
        async with self.lock:
            metrics = self._get_or_create_metrics(agent_id)
            cpu_usage = metrics.cpu_usage_atual
            budget = metrics.cpu_budget
            produtividade = metrics.produtividade
            em_modo = metrics.em_modo_sobrevivencia
            eficiencia = metrics.eficiencia_energetica
            fitness = metrics.fitness_score
            metrics_copy = metrics

        ivm = await self.calcular_ivm(agent_id)

        diagnosticos = []
        if cpu_usage > budget * 0.8:
            diagnosticos.append("consumo_de_cpu_elevado")
        if produtividade < 0.3 and cpu_usage > 0.1:
            diagnosticos.append("baixa_produtividade_com_alto_cpu")
        if ivm < 0.4:
            diagnosticos.append("ivm_critico_risco_de_apoptose")
        if em_modo and cpu_usage < 0.05:
            diagnosticos.append("modo_sobrevivencia_ativo_mas_ocioso")

        return {
            "agent_id": agent_id,
            "ivm": round(ivm, 3),
            "cpu_usage": round(cpu_usage, 3),
            "cpu_budget": budget,
            "produtividade": round(produtividade, 3),
            "eficiencia": round(eficiencia, 3),
            "fitness": round(fitness, 3),
            "diagnosticos": diagnosticos,
            "recommendacao": self._gerar_recomendacao(ivm, metrics_copy),
        }

    @staticmethod
    def _gerar_recomendacao(ivm: float, metrics: AgentCpuMetrics) -> str:
        if ivm < IVM_THRESHOLD_CRITICO:
            return (f"Agente consumindo {metrics.cpu_usage_atual:.0%} de CPU "
                    f"para produtividade de {metrics.produtividade:.0%}. "
                    "Recomendado: trigger de apoptose graceful ou redução de budget.")
        if ivm > IVM_THRESHOLD_EXCELENCIA:
            return (f"Alta viabilidade metabólica (IVM={ivm:.2f}). "
                    "Recomendado: replicação (mitose) para expandir a colônia.")
        if metrics.cpu_usage_atual > metrics.cpu_budget * 0.8:
            return ("Consumo de CPU elevado. Considere ativar modo de sobrevivência "
                    "ou distribuir subtarefas para agentes ociosos.")
        return "Operação normal. Nenhuma ação necessária."

    async def reportar_uso_cpu(self, agent_id: str, uso: float) -> None:
        async with self.lock:
            metrics = self._get_or_create_metrics(agent_id)
            metrics.cpu_usage_atual = max(0.0, min(1.0, uso))
            budget = metrics.cpu_budget

        # Revive a telemetria morta e federa o sinal de CPU para o IVM canônico
        # (IVMAxiom). Unificação: o CpuAffinityManager é um scheduler de budget,
        # não um índice IVM concorrente — delega E_cpu para o IVMAxiom.
        try:
            from iaglobal.chappie import _get_chappie
            ivm = _get_chappie().get("ivm")
            if ivm is not None:
                await ivm.atualizar_metricas(agent_id, cpu_usage=uso, cpu_budget=budget)
        except Exception as e:
            logger.debug("[CPU] IVMAxiom indisponível para telemetria de CPU: %s", e)

    async def registrar_tarefa(self, agent_id: str, sucesso: bool) -> None:
        async with self.lock:
            metrics = self._get_or_create_metrics(agent_id)
            if sucesso:
                metrics.tasks_completadas += 1
            else:
                metrics.tasks_falhas += 1

    async def get_metrics(self, agent_id: str) -> Optional[dict]:
        async with self.lock:
            metrics = self._agents.get(agent_id)
            return metrics.to_dict() if metrics else None

    async def get_all_metrics(self) -> Dict[str, dict]:
        async with self.lock:
            return {aid: m.to_dict() for aid, m in self._agents.items()}


# =========================================================================
# Instância global
# =========================================================================

cpu_affinity = CpuAffinityManager()
