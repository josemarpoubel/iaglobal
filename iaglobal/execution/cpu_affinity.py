# iaglobal/execution/cpu_affinity.py
#
# Weight-based CPU Budget Scheduler
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

import os
import hashlib
import time
import threading
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
IVM_THRESHOLD_CRITICO = 0.3
IVM_THRESHOLD_EXCELENCIA = 0.8
FITNESS_DECAY = 0.95        # decaimento temporal do fitness a cada ciclo


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
        self._lock = threading.Lock()
        self._agents_por_prioridade: Dict[str, float] = {}

    def alocar(self, agentes: List[Tuple[str, float]]) -> Dict[str, float]:
        """Distribui budgets proporcionalmente à prioridade de cada agente.

        Args:
            agentes: Lista de (agent_id, prioridade) onde prioridade é 0-1.

        Returns:
            Dict mapeando agent_id -> budget (0.0-1.0)
        """
        if not agentes:
            return {}

        with self._lock:
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

    def obter_prioridade(self, agent_id: str) -> float:
        return self._agents_por_prioridade.get(agent_id, 0.5)


# =========================================================================
# CPU AFFINITY MANAGER — nova versão cross-platform
# =========================================================================

class CpuAffinityManager:
    """Gerenciador de budget de CPU por agente (Weight-based Scheduler).

    Remove dependência de os.sched_setaffinity e sys.platform.
    Cada agente recebe um budget de CPU (padrão 25%) e o ResourceManager
    distribui a carga com base em prioridade e fitness.

    Métodos legados (assign_core_deterministic, pin_to_hash, pin_current)
    continuam funcionando mas não fixam mais o processo em núcleos —
    retornam apenas um core lógico para logging/monitoramento.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._total_cores: int = os.cpu_count() or 1
        self._agents: Dict[str, AgentCpuMetrics] = {}
        self._budgets: Dict[str, float] = {}
        self._last_agent_map: Dict[str, int] = {}
        self.resource_manager = ResourceManager()

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
        if agent_id not in self._agents:
            self._agents[agent_id] = AgentCpuMetrics(agent_id=agent_id)
        return self._agents[agent_id]

    # ==============================================================
    # MÉTODOS LEGADOS (backward-compatible)
    # ==============================================================

    def assign_core_deterministic(self, agent_id: str) -> int:
        """Atribui um core lógico baseado no hash (para compatibilidade).

        Não fixa o processo — apenas retorna o core para logging.
        """
        core = self._core_from_hash(agent_id)
        with self._lock:
            self._last_agent_map[agent_id] = core
            self._get_or_create_metrics(agent_id)
            if agent_id not in self._budgets:
                self._budgets[agent_id] = BUDGET_PADRAO
        return core

    def pin_to_hash(self, agent_id: str) -> int:
        """Cross-platform: não fixa mais o processo. Retorna core lógico.

        Antigamente chamava os.sched_setaffinity — agora apenas registra.
        """
        core = self._core_from_hash(agent_id)
        with self._lock:
            self._last_agent_map[agent_id] = core
            self._get_or_create_metrics(agent_id)
        return core

    def pin_current(self, agent_id: str):
        """Cross-platform: não fixa mais o processo. Apenas registra.

        Retorna o core lógico derivado do hash para compatibilidade com
        chamadas existentes (ex: bootstrap.py espera um valor).
        """
        core = self.pin_to_hash(agent_id)
        return core

    def map_balanced(self, agents: List[str]) -> Dict[str, int]:
        """Distribui budgets de CPU igualmente entre todos os agentes.

        Retorna dict agent_id -> core lógico (para compatibilidade).
        """
        if not agents:
            return {}

        assignment = {}
        with self._lock:
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

    def dispersion_report(self) -> dict:
        """Relatório de distribuição de budgets e métricas IVM.

        Compatível com o formato esperado por status.py e orchestrator.py.
        """
        with self._lock:
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
                # Compatibilidade com status.py
                "total_cores": self._total_cores,
                "agents_mapped": total_agents,
                "max_load": max_load,
                "min_load": min_load,
                "imbalance": round(imbalance, 2),
                "efficiency": round(1.0 - abs(imbalance) * 0.1, 3),
                "per_core": {str(k): v for k, v in per_core.items()},
                "distribution": counts,
                # Novas métricas IVM
                "ivm_medio": round(ivm_medio, 3),
                "fitness_medio": round(fitness_medio, 3),
                "total_agents": total_agents,
                "budgets": budgets,
                "agentes_em_sobrevivencia": agentes_em_sobrevivencia,
                "total_budget_alocado": round(sum(budgets.values()), 3) if budgets else 0,
            }

    def rebalance_if_needed(self, *args, **kwargs):
        """Verifica e rebalanceia budgets se a distribuição estiver desigual.

        Aceita *args e **kwargs para compatibilidade com chamadas existentes
        que podem passar argumentos posicionais ou nomeados.
        """
        with self._lock:
            if not self._budgets:
                return False

            budgets_list = list(self._budgets.values())
            if not budgets_list:
                return False

            max_budget = max(budgets_list)
            min_budget = min(budgets_list)
            agents_list = list(self._budgets.keys())

            if max_budget - min_budget > 0.1 and len(agents_list) > 1:
                self.map_balanced(agents_list)
                logger.info("[CPU] Rebalanceamento automático de budgets concluído.")
                return True
            return False

    # ==============================================================
    # NOVOS MÉTODOS — Budget de CPU
    # ==============================================================

    def set_cpu_budget(self, agent_id: str, budget: float) -> None:
        """Define o budget de CPU para um agente (0.0 a 1.0 = 0% a 100%).

        Respeita o teto de 25% (BUDGET_PADRAO).
        """
        budget = max(0.0, min(BUDGET_PADRAO, budget))
        with self._lock:
            self._budgets[agent_id] = round(budget, 3)
            metrics = self._get_or_create_metrics(agent_id)
            metrics.cpu_budget = round(budget, 3)
            metrics.ultimo_ajuste = time.time()

    def get_cpu_budget(self, agent_id: str) -> float:
        """Retorna o budget de CPU atual do agente."""
        with self._lock:
            return self._budgets.get(agent_id, BUDGET_PADRAO)

    def get_all_budgets(self) -> Dict[str, float]:
        """Retorna todos os budgets atuais."""
        with self._lock:
            return dict(self._budgets)

    def survival_mode(self, agent_id: str) -> None:
        """Ativa modo de sobrevivência: reduz budget para 10%.

        Usado quando o nó está sob carga pesada ou quando um agente
        nômade entra em um nó já ocupado.
        """
        self.set_cpu_budget(agent_id, BUDGET_SOBREVIVENCIA)
        with self._lock:
            metrics = self._get_or_create_metrics(agent_id)
            metrics.em_modo_sobrevivencia = True
        logger.info("[CPU] Agente %s em modo de sobrevivência: budget=10%%", agent_id)

    def restore_budget(self, agent_id: str) -> None:
        """Restaura o budget ao padrão (25%), saindo do modo sobrevivência."""
        self.set_cpu_budget(agent_id, BUDGET_PADRAO)
        with self._lock:
            metrics = self._get_or_create_metrics(agent_id)
            metrics.em_modo_sobrevivencia = False
        logger.info("[CPU] Agente %s restaurado ao budget padrão: 25%%", agent_id)

    # ==============================================================
    # IVM — Índice de Viabilidade Metabólica
    # ==============================================================

    def calcular_ivm(self, agent_id: str,
                     produtividade: Optional[float] = None,
                     cpu_usage: Optional[float] = None,
                     obsidian_notes: Optional[int] = None) -> float:
        """Calcula o IVM (Índice de Viabilidade Metabólica) de um agente.

        Fórmula:
            IVM = (P × 0.4) + (E × 0.4) + (C × 0.2)

        Onde:
            P = Produtividade (taxa de conclusão de tarefas)
            E = Eficiência Energética (inverso do uso de CPU)
            C = Cooperação (notas registradas no Obsidian)
        """
        metrics = self._get_or_create_metrics(agent_id)

        p = produtividade if produtividade is not None else metrics.produtividade
        cpu = cpu_usage if cpu_usage is not None else metrics.cpu_usage_atual

        if cpu <= 0.01:
            e = 1.0
        else:
            ratio = cpu / metrics.cpu_budget
            if ratio <= 1.0:
                e = 1.0 - (ratio * 0.5)
            else:
                e = max(0.0, 1.0 - ratio)

        notes = obsidian_notes if obsidian_notes is not None else metrics.obsidian_notes_escritas
        c = min(1.0, notes / 10.0)

        ivm = (p * 0.4) + (e * 0.4) + (c * 0.2)
        ivm = max(0.0, min(1.0, ivm))

        with self._lock:
            metrics.ivm_atual = ivm

        return ivm

    def monitorar_metabolismo(self, agent_id: str) -> dict:
        """Monitora o IVM do agente e retorna ação evolutiva recomendada.

        Returns:
            dict com acao, motivo, ivm, e métricas do agente.
        """
        metrics = self._get_or_create_metrics(agent_id)
        ivm = self.calcular_ivm(agent_id)

        if ivm < IVM_THRESHOLD_CRITICO:
            acao = "apoptose"
            motivo = "baixa_viabilidade_metabolica"
        elif ivm > IVM_THRESHOLD_EXCELENCIA:
            acao = "mitose"
            motivo = "replicacao_de_sucesso"
        else:
            acao = "monitorar"
            motivo = "dentro_do_esperado"

        return {
            "acao": acao,
            "motivo": motivo,
            "ivm": round(ivm, 3),
            "agente": agent_id,
            "metrics": metrics.to_dict(),
        }

    # ==============================================================
    # FITNESS SCORE — Sistema de Pontuação
    # ==============================================================

    def update_fitness(self, agent_id: str,
                       trabalho_realizado: float = 0.0,
                       custo_cpu: float = 0.0,
                       uptime_segundos: float = 0.0,
                       obsidian_notes: int = 0) -> float:
        """Atualiza o fitness score do agente no genome.json.

        Componentes:
        - Eficiência Energética: Score += (Trabalho Realizado / Custo de CPU)
        - Confiabilidade: Score += (Tempo de Uptime sem Apoptose)
        - Contribuição Imunológica: Score += (Notas registradas no Obsidian)
        """
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

        with self._lock:
            metrics.fitness_score = score
            if obsidian_notes:
                metrics.obsidian_notes_escritas += obsidian_notes

        self._persist_fitness(agent_id, score)
        return score

    def get_fitness(self, agent_id: str) -> float:
        """Retorna o fitness score atual do agente."""
        with self._lock:
            metrics = self._agents.get(agent_id)
            return metrics.fitness_score if metrics else 0.5

    def _persist_fitness(self, agent_id: str, score: float) -> None:
        """Persiste o fitness score no genome.json do agente."""
        genome_path = self._resolve_genome_path(agent_id)
        if not genome_path:
            return
        try:
            genome_path.parent.mkdir(parents=True, exist_ok=True)
            if genome_path.exists():
                data = json.loads(genome_path.read_text())
            else:
                data = {"agent_id": agent_id, "genome": {}}
            data["fitness_score"] = round(score, 3)
            data["ultima_atualizacao"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            genome_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug("[CPU] Não foi possível persistir fitness: %s", e)

    @staticmethod
    def _resolve_genome_path(agent_id: str) -> Optional[Path]:
        """Resolve o caminho do genome.json para o agente."""
        try:
            from iaglobal._paths import JSON_DIR
            return JSON_DIR / f"genome_{agent_id}.json"
        except Exception:
            return None

    # ==============================================================
    # AUTO-CRÍTICA — Monitoramento de Eficiência
    # ==============================================================

    def auto_critica(self, agent_id: str) -> dict:
        """Analisa a eficiência do consumo de recursos do agente.

        Retorna diagnóstico sugerindo ações corretivas se o agente
        estiver consumindo mais CPU do que o necessário para o resultado.
        """
        metrics = self._get_or_create_metrics(agent_id)
        ivm = self.calcular_ivm(agent_id)

        diagnosticos = []
        if metrics.cpu_usage_atual > metrics.cpu_budget * 0.8:
            diagnosticos.append("consumo_de_cpu_elevado")
        if metrics.produtividade < 0.3 and metrics.cpu_usage_atual > 0.1:
            diagnosticos.append("baixa_produtividade_com_alto_cpu")
        if ivm < 0.4:
            diagnosticos.append("ivm_critico_risco_de_apoptose")
        if metrics.em_modo_sobrevivencia and metrics.cpu_usage_atual < 0.05:
            diagnosticos.append("modo_sobrevivencia_ativo_mas_ocioso")

        return {
            "agent_id": agent_id,
            "ivm": round(ivm, 3),
            "cpu_usage": round(metrics.cpu_usage_atual, 3),
            "cpu_budget": metrics.cpu_budget,
            "produtividade": round(metrics.produtividade, 3),
            "eficiencia": round(metrics.eficiencia_energetica, 3),
            "fitness": round(metrics.fitness_score, 3),
            "diagnosticos": diagnosticos,
            "recommendacao": self._gerar_recomendacao(ivm, metrics),
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

    def reportar_uso_cpu(self, agent_id: str, uso: float) -> None:
        """Registra o uso atual de CPU do agente (0.0 a 1.0)."""
        with self._lock:
            metrics = self._get_or_create_metrics(agent_id)
            metrics.cpu_usage_atual = max(0.0, min(1.0, uso))

    def registrar_tarefa(self, agent_id: str, sucesso: bool) -> None:
        """Registra a conclusão de uma tarefa (sucesso ou falha)."""
        with self._lock:
            metrics = self._get_or_create_metrics(agent_id)
            if sucesso:
                metrics.tasks_completadas += 1
            else:
                metrics.tasks_falhas += 1

    def get_metrics(self, agent_id: str) -> Optional[dict]:
        """Retorna todas as métricas de um agente."""
        with self._lock:
            metrics = self._agents.get(agent_id)
            return metrics.to_dict() if metrics else None

    def get_all_metrics(self) -> Dict[str, dict]:
        """Retorna métricas de todos os agentes."""
        with self._lock:
            return {aid: m.to_dict() for aid, m in self._agents.items()}


# =========================================================================
# Instância global
# =========================================================================

cpu_affinity = CpuAffinityManager()
