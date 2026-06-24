# iaglobal/evolution/evolution_replay.py

"""
📊 Evolution Replay — Caixa Negra e Máquina do Tempo do Ecossistema.

Reconstrói snapshots populacionais a partir dos dados históricos de linhagem,
permitindo auditoria de mutações, curvas de fitness e análise de árvores genealógicas.
Otimizado para evitar vazamentos de memória (OOM) e travamento de CPU.
"""

import copy
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Set, Any
from iaglobal.utils.logger import logger


CORE_NODE_NAMES = {
    "prompt_intake", "requirements", "pm", "architect", "planner",
    "execution_plan", "coder", "reviewer", "validator", "tester",
}


@dataclass(frozen=True)  # Tornar imutável previne mutações colaterais e dispensa deepcopy profundo
class ReplayNode:
    name: str
    strategy: str
    fitness: float
    event_type: str          # "seed", "mutation", "crossover", "core"
    parents: List[str]       # Ancestrais diretos vindo da linhagem
    created_at: int          # Geração em que o nó nasceu
    node_type: str = "general"
    seed_id: str = ""


@dataclass
class ReplaySnapshot:
    generation: int
    nodes: Dict[str, ReplayNode] = field(default_factory=dict)
    evo_count: int = 0
    core_count: int = 0
    mean_fitness: float = 0.0
    strategy_diversity: float = 0.0
    strategy_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class GenerationDiff:
    gen_a: int
    gen_b: int
    added: List[str]
    removed: List[str]
    mutated: List[str]


class EvolutionReplay:
    """
    Motor de inspeção analítica da árvore genealógica de agentes do iaglobal.
    Otimizado para alta performance em grandes volumes de gerações.
    """

    def __init__(self, engine: Any):
        self.engine = engine  # Referência ao EvolutionEngine ou DB de Linhagem

    def reconstruct_snapshots(self, target_generation: int) -> Dict[int, ReplaySnapshot]:
        """
        Reconstrói o estado total da população até a geração alvo de forma performática.
        Substitui deepcopies caros por dicionários de referências imutáveis.
        """
        snapshots: Dict[int, ReplaySnapshot] = {}
        current_nodes: Dict[str, ReplayNode] = {}

        # Busca histórico bruto de mutações ordenados cronologicamente por geração
        history: List[Any] = self.engine.get_lineage_history() if hasattr(self.engine, 'get_lineage_history') else []
        history_by_gen: Dict[int, List[Any]] = {}
        
        for item in history:
            gen = item.get("generation", 1)
            history_by_gen.setdefault(gen, []).append(item)

        for gen in range(1, target_generation + 1):
            # Processa as alterações genéticas que nasceram exclusivamente nesta geração
            if gen in history_by_gen:
                for item in history_by_gen[gen]:
                    node_name = item["name"]
                    current_nodes[node_name] = ReplayNode(
                        name=node_name,
                        strategy=item.get("strategy", "general"),
                        fitness=float(item.get("fitness", 0.0)),
                        event_type=item.get("event_type", "mutation"),
                        parents=list(item.get("parents", [])),
                        created_at=gen,
                        node_type=item.get("node_type", "general"),
                        seed_id=item.get("seed_id", "")
                    )

            # Métricas Populacionais da Geração Atual
            all_nodes = list(current_nodes.values())
            total_count = len(all_nodes)
            
            evo_nodes = [n for n in all_nodes if n.event_type != "core"]
            core_nodes = [n for n in all_nodes if n.event_type == "core"]
            
            uniq_strategies: Set[str] = {n.strategy for n in evo_nodes}
            
            # Contagem de diversidade com proteção defensiva contra divisão por zero
            strat_counts: Dict[str, int] = {}
            for n in evo_nodes:
                strat_counts[n.strategy] = strat_counts.get(n.strategy, 0) + 1

            div_score = len(uniq_strategies) / len(evo_nodes) if evo_nodes else 0.0
            avg_fit = (sum(n.fitness for n in all_nodes) / total_count) if total_count > 0 else 0.0

            # 🔥 OTIMIZAÇÃO CRÍTICA: Como ReplayNode é frozen=True, podemos passar um dict plano (.copy())
            # em vez de deepcopy(). Isto poupa até 90% de uso de CPU e RAM no loop!
            snapshots[gen] = ReplaySnapshot(
                generation=gen,
                nodes=current_nodes.copy(), 
                evo_count=len(evo_nodes),
                core_count=len(core_nodes),
                mean_fitness=avg_fit,
                strategy_diversity=div_score,
                strategy_counts=strat_counts
            )

        return snapshots

    def diff(self, gen_a: int, gen_b: int) -> GenerationDiff:
        """Compara o delta genético entre duas eras do ecossistema."""
        snaps = self.reconstruct_snapshots(max(gen_a, gen_b))
        snap_a = snaps.get(gen_a)
        snap_b = snaps.get(gen_b)

        if not snap_a or not snap_b:
            return GenerationDiff(gen_a, gen_b, [], [], [])

        set_a = set(snap_a.nodes.keys())
        set_b = set(snap_b.nodes.keys())

        added = sorted(list(set_b - set_a))
        removed = sorted(list(set_a - set_b))
        
        # Deteta mutações (nós sobreviventes que alteraram a nota de fitness)
        intersect = set_a & set_b
        mutated = sorted([
            nid for nid in intersect 
            if snap_a.nodes[nid].fitness != snap_b.nodes[nid].fitness
        ])

        return GenerationDiff(gen_a, gen_b, added, removed, mutated)


