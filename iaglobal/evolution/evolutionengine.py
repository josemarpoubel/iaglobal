# iaglobal/evolution/evolutionengine.py

import copy
import hashlib
import secrets
import logging
import time
from typing import Dict, Optional, List

from iaglobal.graphs.node import Node
from iaglobal.graphs.workdir import WorkDir
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.canonical_graph import canonicalize, compute_graph_hash
from iaglobal.evolution.execution_registry import registry as exec_registry
from iaglobal.evolution.skills.skill_executor import skill_executor
from iaglobal.evolution.skills.skill_registry import skill_registry
from iaglobal.evolution.skills.skill import ExecutionPolicy, Skill
from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
from iaglobal.events import DecisionEvent
from iaglobal.models.event_bus import bus, EventType

logger = logging.getLogger(__name__)

MAX_NODE_NAME = 120


def _short_name(*parts: str) -> str:
    """Generate a node name that never exceeds MAX_NODE_NAME.

    Joins parts with underscores then hashes when the result would overflow.
    Uses an 8-char hex hash of the full concatenation.
    """
    candidate = "_".join(str(p) for p in parts)
    if len(candidate) <= MAX_NODE_NAME:
        return candidate
    h = hashlib.sha256(candidate.encode()).hexdigest()[:8]
    # Find the shortest prefix that fits with hash
    for i in range(1, len(parts)):
        prefix = "_".join(str(p) for p in parts[:i])
        result = f"{prefix}_{h}"
        if len(result) <= MAX_NODE_NAME:
            return result
    # Last resort: just hash
    return h


class EvolutionEngine:
    """
    🧬 Advanced Evolution Engine

    Agora com:
    - DAG Canonicalization (dedup, consolida, ordena)
    - Execution Registry (idempotência)
    - Mutation rate por estratégia
    - Seleção fitness-aware
    - Crossover controlado
    - Task-aware: cria agentes especialistas com base no prompt da tarefa
    """

    def __init__(
        self,
        graph: ExecutionGraph,
        mutation_rate: float = 0.1,
        strategies: Optional[List[str]] = None,
        strategy_mutation_rates: Optional[Dict[str, float]] = None
    ):
        self.graph = graph
        self.generation = graph.generation
        self._last_graph_hash = graph._graph_hash if hasattr(graph, '_graph_hash') else ""

        self.mutation_rate = mutation_rate

        self.strategies = strategies or [
            "coding",
            "research",
            "fast",
            "explore"
        ]

        # 🎯 MUTATION RATE POR ESTRATÉGIA
        self.strategy_mutation_rates = strategy_mutation_rates or {
            "coding": 0.15,     # mais estável
            "research": 0.20,   # equilibrado
            "fast": 0.30,       # mais agressivo
            "explore": 0.40,    # altamente mutável
            "general": 0.15,
            "reflection": 0.20,
            "debug": 0.25,
        }

        # 🏗️ MetaAgentDesigner (arquiteta a equipe para cada task)
        self.designer: MetaAgentDesigner = MetaAgentDesigner(graph)

        # 🎯 Task-aware attributes
        self.current_task: str = ""
        self.task_strategies: set = set()
        self.task_technologies: set = set()
        self.task_type: str = "general"
        self._task_agents_created: bool = False

    def set_task(self, task: str):
        """Define a tarefa atual para criação de agentes especializados."""
        if task == self.current_task:
            return
        self.current_task = task
        self._task_agents_created = False
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        analysis = TaskAnalyzer.analyze(task)
        self.task_strategies = analysis["strategies"]
        self.task_technologies = analysis["technologies"]
        self.task_type = analysis["task_type"]
        if self.task_strategies:
            for s in self.task_strategies:
                if s not in self.strategies:
                    self.strategies.append(s)
                    self.strategy_mutation_rates[s] = 0.25
            logger.info(
                "[TASK] Task registrada: type=%s strategies=%s techs=%s",
                self.task_type, self.task_strategies, self.task_technologies
            )
        # 🏗️ Usa MetaAgentDesigner para projetar a equipe ideal
        try:
            design = self.designer.design_team(task)
            instr_count = len(design.get("specialization_instructions", {}))
            gaps = design.get("lacunas_detectadas", [])
            strategies = design.get("strategies", [])
            logger.info(
                "[TASK] MetaAgentDesigner: %d estrategias, %d gaps, %d instrucoes de especializacao geradas",
                len(strategies), len(gaps), instr_count
            )
        except Exception as e:
            logger.warning("[TASK] MetaAgentDesigner falhou: %s — fallback para TaskAgentFactory", e)
            self._create_task_agents()

    # --------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------

    def evolve(self):
        import time as _time
        phase_times = {}
        t0 = _time.time()
        logger.info("🧬 ===== EVOLUTION CYCLE START | gen=%d =====", self.generation)
        logger.info("📊 Nodes before: %d | mutation_rate=%.2f | strategies=%s",
                    len(self.graph.nodes), self.mutation_rate, self.strategies)

        # 🔒 Canonicaliza antes de evoluir (remove duplicatas)
        t1 = _time.time()
        original_count = len(self.graph.nodes)
        removed_count = original_count
        self.graph.nodes = canonicalize(self.graph.nodes)
        removed_count -= len(self.graph.nodes)
        phase_times["canonicalize"] = round(_time.time() - t1, 3)

        current_hash = compute_graph_hash(self.graph.nodes)
        if current_hash != self._last_graph_hash:
            logger.info("🔧 organizando agentes: %d → %d (%d duplicatas removidas)", 
                        original_count, len(self.graph.nodes), removed_count)
            self._last_graph_hash = current_hash
            self.graph._graph_hash = current_hash
        else:
            logger.info("🔧 [FASE 1/5] Canonicalização: %d nós (sem mudanças) | %.3fs",
                        len(self.graph.nodes), phase_times["canonicalize"])

        # 🌱 Seed population + Task-specific agents
        t1 = _time.time()
        pop_before = len([n for n in self.graph.nodes.values() if n.name not in self.CORE_NODE_NAMES])
        self._seed_evo_population()
        self._create_task_agents()
        pop_after = len([n for n in self.graph.nodes.values() if n.name not in self.CORE_NODE_NAMES])
        phase_times["seed"] = round(_time.time() - t1, 3)
        logger.info("🌱 [FASE 2/5] População EVO: %d → %d seeds | %.3fs",
                    pop_before, pop_after, phase_times["seed"])

        # 🧬 Selection
        t1 = _time.time()
        self._select_survivors()
        phase_times["selection"] = round(_time.time() - t1, 3)
        core_count = len([n for n in self.graph.nodes.values() if n.name in self.CORE_NODE_NAMES])
        evo_count = len([n for n in self.graph.nodes.values() if n.name not in self.CORE_NODE_NAMES])
        logger.info("🧬 [FASE 3/5] Seleção: %d core + %d evo sobreviventes | %.3fs",
                    core_count, evo_count, phase_times["selection"])

        # 🔀 Mutation
        t1 = _time.time()
        evo_before_mut = len([n for n in self.graph.nodes.values() if n.name not in self.CORE_NODE_NAMES])
        self._mutate_nodes()
        evo_after_mut = len([n for n in self.graph.nodes.values() if n.name not in self.CORE_NODE_NAMES])
        phase_times["mutation"] = round(_time.time() - t1, 3)
        new_mutants = evo_after_mut - evo_before_mut
        logger.info("🔀 [FASE 4/5] Mutação: %d novos mutantes (evo: %d → %d) | %.3fs",
                    new_mutants, evo_before_mut, evo_after_mut, phase_times["mutation"])

        # 🧬 Crossover
        t1 = _time.time()
        evo_before_x = len([n for n in self.graph.nodes.values() if n.name not in self.CORE_NODE_NAMES])
        self._crossover_phase()
        evo_after_x = len([n for n in self.graph.nodes.values() if n.name not in self.CORE_NODE_NAMES])
        phase_times["crossover"] = round(_time.time() - t1, 3)
        new_children = evo_after_x - evo_before_x
        logger.info("🧬 [FASE 5/5] Crossover: %d novos filhos (evo: %d → %d) | %.3fs",
                    new_children, evo_before_x, evo_after_x, phase_times["crossover"])

        self.generation += 1
        self.graph.generation = self.generation

        # 🔒 Canonicaliza após evolução (limpa duplicatas de crossover/mutation)
        t1 = _time.time()
        post_count = len(self.graph.nodes)
        self.graph.nodes = canonicalize(self.graph.nodes)
        post_dedup = len(self.graph.nodes)
        phase_times["post_canon"] = round(_time.time() - t1, 3)

        total = round(_time.time() - t0, 3)
        logger.info("✅ ===== EVOLUTION CYCLE COMPLETE | gen=%d =====", self.generation)
        logger.info("📊 Resumo: %d nós (%d core + %d evo) | canonicalize=%.3fs seed=%.3fs selection=%.3fs mutation=%.3fs crossover=%.3fs post-canon=%.3fs | TOTAL=%.3fs",
                    post_dedup, core_count, post_dedup - core_count,
                    phase_times.get("canonicalize", 0), phase_times.get("seed", 0),
                    phase_times.get("selection", 0), phase_times.get("mutation", 0),
                    phase_times.get("crossover", 0), phase_times.get("post_canon", 0), total)
        if post_count != post_dedup:
            logger.info("🧹 Pós-canonicalização removeu %d duplicatas (pós: %d → %d)",
                        post_count - post_dedup, post_count, post_dedup)

        # =====================================================================
        # 📝 EVOLUTION CHECK — DecisionEvent
        # =====================================================================
        evo_triggered = (new_mutants > 0 or new_children > 0 or pop_after > pop_before)
        if evo_triggered:
            reason = f"new_mutants={new_mutants} new_children={new_children} seeds_adicionados={pop_after - pop_before}"
        else:
            reason = "stable_performance"

        try:
            bus.publish(EventType.PIPELINE_STAGE, {
                "decision_event": DecisionEvent(
                    step="evolution_check",
                    execution_id=f"cycle_{self.generation}",
                    triggered=evo_triggered,
                    reason=reason,
                    metadata={
                        "generation": self.generation,
                        "total_nodes": post_dedup,
                        "core_nodes": core_count,
                        "evo_nodes": post_dedup - core_count,
                        "new_mutants": new_mutants,
                        "new_children": new_children,
                        "removed_duplicates": removed_count,
                        "total_time_s": total,
                    },
                ).to_dict(),
                "step": "evolution_check",
            }, source="evolution_engine")
        except Exception:
            pass

    def _is_evo_cloneable(self, name: str) -> bool:
        """
        Verifica se um nó core pode ser clonado como EVO seed.
        Skills SINGLE_RUN nunca são clonadas porque executam apenas uma vez
        por task — o EVO clone seria sempre pulado e o resultado do core
        seria sobrescrito pelo fallback LLM, corrompendo o pipeline.
        Skills de infraestrutura (artifact_writer, reflexion, etc.) também
        não devem ser clonadas por dependerem de resultados completos.
        """
        skill_name = None
        node = self.graph.nodes.get(name)
        if node:
            skill_name = node.node_type if node.node_type != "general" else name
        if not skill_name or not skill_executor.can_execute(skill_name):
            return False
        skill = skill_executor.registry.get(skill_name)
        if skill and skill.execution_policy == ExecutionPolicy.SINGLE_RUN:
            return False
        return True

    def _seed_evo_population(self):
        """Cria nós EVO iniciais (clones dos core) se não houver população evolutiva."""
        evo_nodes = [
            n for n in self.graph.nodes.values()
            if n.name not in self.CORE_NODE_NAMES
        ]
        if evo_nodes:
            logger.info("🌱 população evolutiva já existe (%d agentes)", len(evo_nodes))
            return

        import copy
        from iaglobal.graphs.workdir import WorkDir
        seeds = {}
        skipped_no_skill = 0
        skipped_not_cloneable = 0
        skipped_duplicate = 0
        core_available = 0

        logger.info("🌱 criando novos agentes a partir dos especialistas existentes ...")
        # Itera sobre cópia para evitar race condition com a pipeline principal
        for name, node in list(self.graph.nodes.items()):
            if name not in self.CORE_NODE_NAMES:
                continue
            core_available += 1
            skill_name = node.node_type if node.node_type != "general" else name
            if not skill_executor.can_execute(skill_name):
                logger.info("🌱 agente '%s' não pode ser clonado (skill '%s' não registrada)", name, skill_name)
                skipped_no_skill += 1
                continue
            if not self._is_evo_cloneable(name):
                skill_obj = skill_executor.registry.get(skill_name)
                policy = skill_obj.execution_policy.value if skill_obj else "?"
                logger.info("🌱 agente '%s' é SINGLE_RUN — não será clonado", name)
                skipped_not_cloneable += 1
                continue
            seed_name = f"evo_{name}_seed_{self.generation}"
            if seed_name in self.graph.nodes:
                logger.info("🌱 clone '%s' já existe", seed_name)
                skipped_duplicate += 1
                continue
            seed = copy.deepcopy(node)
            seed.name = seed_name
            seed.node_type = skill_name
            seed.seed_id = seed_name
            seed.mutation_id = ""
            seed.version = "v1"
            self._record_lineage(seed, "seed", parent_name=name,
                                 strategy=seed.strategy)
            seeds[seed.name] = seed
            WorkDir(seed.name, "evo_init").ensure().append_log("evo seed criado de skill=%s" % skill_name)
            logger.info("🌱 novo agente criado: '%s' (cópia de '%s')", seed_name, name)

        self.graph.nodes.update(seeds)
        if seeds:
            logger.info("🌱 %d novo(s) agente(s) adicionado(s) à população!", len(seeds))
        else:
            logger.info("🌱 todos os %d nós são SINGLE_RUN — criando EVO seeds sintéticos...", core_available)
            self._create_synthetic_evo_seeds()

    def _create_synthetic_evo_seeds(self):
        """Cria EVO seeds sintéticos quando todos os core nodes são SINGLE_RUN.
        Cada seed usa GENERAL node_type + uma estratégia de evolução diferente."""
        from iaglobal.graphs.workdir import WorkDir
        import copy
        gen = self.generation
        synths = {}
        base_nodes = [
            ("prompt_intake", "coding"),
            ("architect", "research"),
            ("planner", "explore"),
            ("coder", "fast"),
            ("reviewer", "reflection"),
            ("debug_coder", "debug"),
        ]
        for src_name, strategy in base_nodes:
            src = self.graph.nodes.get(src_name)
            if not src:
                continue
            seed_name = f"evo_{strategy}_seed_{gen}"
            if seed_name in self.graph.nodes:
                continue
            seed = copy.deepcopy(src)
            seed.name = seed_name
            seed.node_type = "general"
            seed.seed_id = seed_name
            seed.mutation_id = ""
            seed.strategy = strategy
            seed.version = "v1"
            self._record_lineage(seed, "seed", parent_name=src_name,
                                 strategy=strategy)
            synths[seed.name] = seed
            WorkDir(seed.name, "evo_init").ensure().append_log(
                "evo seed sintetico criado de %s strategy=%s" % (src_name, strategy))
            logger.info("🌱 EVO sintético: '%s' (strategy=%s, inspirado em '%s')",
                        seed_name, strategy, src_name)
            # Register a basic skill so mutate/crossover don't warn
            if not skill_executor.can_execute(seed_name):
                skill_registry.register(Skill(
                    name=seed_name,
                    description=f"Evolvable synthetic seed ({strategy})",
                ))
        self.graph.nodes.update(synths)
        if synths:
            logger.info("🌱 %d EVO seed(s) sintético(s) adicionado(s) à população!", len(synths))
        else:
            logger.info("🌱 nenhum EVO seed sintético foi criado")

    def _create_task_agents(self):
        """Agentes especialistas são criados via MetaAgentDesigner (instruções, não nós).
        Este método é mantido apenas para compatibilidade — não cria mais nós no DAG."""
        self._task_agents_created = True

    # --------------------------------------------------
    # LINEAGE TRACKING
    # --------------------------------------------------

    def _record_lineage(self, node: Node, event_type: str, *,
                        parent_name: str = "", parent_fitness: float = 0.0,
                        strategy: str = ""):
        """Record a lineage entry on a node."""
        from iaglobal.graphs.node import LineageEntry
        entry = LineageEntry(
            generation=self.generation,
            event_type=event_type,
            parent_name=parent_name,
            parent_fitness=parent_fitness,
            strategy=strategy or node.strategy,
            fitness_delta=node.fitness() - parent_fitness if parent_fitness > 0 else 0.0,
            timestamp=time.time(),
        )
        node.lineage.append(entry)

    # --------------------------------------------------
    # SELECTION
    # --------------------------------------------------

    # Nomes dos nós do pipeline DAG que nunca devem ser removidos
    # Nota: artifact_writer e reflexion são nós de infraestrutura que devem
    # ser preservados, mas NÃO clonados como EVO seeds (pois são SINGLE_RUN).
    # O seeding os ignora via _is_evo_cloneable().
    CORE_NODE_NAMES = {
        "prompt_intake", "enhancement", "orchestrator_agent",
        "pm", "requirements", "architect", "search", "knowledge",
        "dependency", "risk_analysis",
        "security_design", "performance_design",
        "planner", "coder",
        "reviewer", "semantic_validator",
        "security_audit", "performance_audit",
        "tester", "debug_coder",
        "documentation", "release",
        "metrics", "optimization",
        "result_agent",
    }

    def _select_survivors(self):
        core_nodes = {
            name: node for name, node in self.graph.nodes.items()
            if name in self.CORE_NODE_NAMES
        }
        evo_nodes = [
            node for name, node in self.graph.nodes.items()
            if name not in self.CORE_NODE_NAMES
        ]

        if evo_nodes:
            evo_sorted = sorted(evo_nodes, key=lambda n: n.fitness(), reverse=True)
            cutoff = max(1, len(evo_sorted) // 2)
            survivors = evo_sorted[:cutoff]
            eliminated = evo_sorted[cutoff:]

            logger.info("🧬 selecionando os mais aptos (%d candidatos, mantendo %d)...",
                        len(evo_nodes), len(survivors))
            if eliminated:
                logger.info("🧬 %d agente(s) eliminado(s) por baixo desempenho", len(eliminated))

            self.graph.nodes = {**core_nodes, **{n.name: n for n in survivors}}
        else:
            self.graph.nodes = core_nodes
            logger.info("🧬 nenhum agente evolutivo para selecionar")

    # --------------------------------------------------
    # MUTATION (ADAPTATIVA POR ESTRATÉGIA)
    # --------------------------------------------------

    def _mutate_nodes(self):
        mutated = {}
        strategy_shifts = 0
        model_drifts = 0
        skill_blocks = 0

        evo_targets = [n for n in self.graph.nodes.values() if n.name not in self.CORE_NODE_NAMES]
        logger.info("🔀 gerando variações genéticas de %d agente(s) ...", len(evo_targets))

        for node in evo_targets:
            new_node, stats = self._mutate_node(node)
            if stats.get("skill_blocked"):
                skill_blocks += 1

            realmente_mutou = stats.get("strategy_shifted") or stats.get("model_drifted")
            if not realmente_mutou and len(evo_targets) <= 2:
                # Força mutação quando há poucos agentes para evitar extinção
                new_node.strategy = secrets.choice(["coding", "research", "fast", "explore",
                                                   "web_development", "form_handling", "general"])
                stats["strategy_shifted"] = True
                realmente_mutou = True
                logger.debug("🔀 mutação forçada: strategy=%s (prevenção de extinção)", new_node.strategy)
            elif not realmente_mutou:
                continue

            if stats.get("strategy_shifted"):
                strategy_shifts += 1
            if stats.get("model_drifted"):
                model_drifts += 1

            if new_node.name not in self.graph.nodes:
                mutated[new_node.name] = new_node
                logger.info("🔀 variação criada: '%s' (estratégia: %s, origem: %s)",
                            new_node.name, new_node.strategy, node.name)
            else:
                new_node.name = _short_name(node.name, "mut", str(self.generation), str(secrets.randbelow(9000) + 1000))
                mutated[new_node.name] = new_node
                logger.info("🔀 variação criada: '%s' (renomeado para evitar conflito)", new_node.name)

        self.graph.nodes.update(mutated)

        if mutated:
            logger.info("🔀 %d nova(s) variação(ões) genética(s) adicionada(s)!", len(mutated))
        else:
            logger.info("🔀 nenhuma variação genética foi criada neste ciclo")

    def _mutate_node(self, node: Node) -> tuple:
        stats = {"skill_blocked": False, "strategy_shifted": False, "model_drifted": False}
        new_node = copy.deepcopy(node)
        new_node.name = _short_name(node.name, "mut", str(self.generation))

        skill_name = node.node_type if node.node_type != "general" else node.name

        if not skill_executor.can_execute(skill_name):
            if node.name.startswith("evo_"):
                # Synthetic EVO node — register skill for offspring silently
                skill_registry.register(Skill(
                    name=new_node.name,
                    description=f"Evolvable offpsring of {node.name}",
                ))
            else:
                logger.warning("⚠️ [MUTATE] Skill '%s' não registrada para '%s' — node_type rebaixado para 'general'",
                               skill_name, node.name)
            new_node.node_type = "general"
            stats["skill_blocked"] = True

        new_node.seed_id = node.seed_id or node.name
        new_node.mutation_id = f"mut_{self.generation}"
        new_node.version = f"v{self.generation}"

        base_rate = self.strategy_mutation_rates.get(node.strategy, self.mutation_rate)
        effective_rate = base_rate

        # Ajusta taxa de mutação com base no histórico de erros
        try:
            from iaglobal.memory.memory_error import load_errors
            error_history = load_errors()
            error_count = len(error_history)
            if error_count > 5:
                effective_rate = min(effective_rate * 1.5, 0.5)
        except Exception:
            pass

        if secrets.randbelow(1000000) < int(effective_rate * 1000000):
            # Prefere estratégias task-specific se disponíveis
            if self.task_strategies and secrets.randbelow(100) < 60:
                candidates = list(self.task_strategies)
            else:
                candidates = self.strategies
            new_strategy = secrets.choice(candidates)
            logger.info("🔀 [MUTATE] Strategy shift: %s → %s (rate=%.2f)", node.strategy, new_strategy, effective_rate)
            new_node.strategy = new_strategy
            stats["strategy_shifted"] = True
        else:
            logger.debug("[MUTATE] Sem strategy shift para %s (rate=%.2f)", node.name, effective_rate)

        if secrets.randbelow(1000000) < int(effective_rate * 1000000):
            from iaglobal.providers.provider_config import ProviderConfig
            fallback_model = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
            logger.info("🔀 [MUTATE] Model drift: %s → %s (rate=%.2f)", node.name, fallback_model, effective_rate)
            new_node.model_hint = fallback_model
            stats["model_drifted"] = True

        WorkDir(new_node.name, "evo_gen_%d" % self.generation).ensure().append_log("mutado de %s skill=%s" % (node.name, skill_name))

        self._record_lineage(
            new_node, "mutation", parent_name=node.name,
            parent_fitness=node.fitness(),
            strategy=new_node.strategy,
        )
        return new_node, stats

    # --------------------------------------------------
    # CROSSOVER (CONTROLADO)
    # --------------------------------------------------

    def _crossover_phase(self):
        evo_nodes = [
            node for node in self.graph.nodes.values()
            if node.name not in self.CORE_NODE_NAMES
        ]
        logger.info("🧬 cruzando %d agente(s) para criar híbridos ...", len(evo_nodes))

        pairs_considered = 0
        pairs_mated = 0
        new_nodes = {}
        skipped_duplicate = 0

        for i in range(len(evo_nodes)):
            for j in range(i + 1, len(evo_nodes)):
                pairs_considered += 1

                if len(evo_nodes) > 2 and secrets.randbelow(100) > 30:
                    continue

                child, stats = self._crossover(evo_nodes[i], evo_nodes[j])
                if child.name not in self.graph.nodes:
                    new_nodes[child.name] = child
                    pairs_mated += 1
                    logger.info("🧬 híbrido criado: '%s' (pais: %s x %s)", child.name,
                                evo_nodes[i].name, evo_nodes[j].name)
                else:
                    child.name = _short_name(evo_nodes[i].name, "x", evo_nodes[j].name,
                                             str(self.generation), str(secrets.randbelow(9000) + 1000))
                    new_nodes[child.name] = child
                    skipped_duplicate += 1
                    logger.info("🧬 híbrido criado: '%s' (renomeado)", child.name)

        self.graph.nodes.update(new_nodes)

        if new_nodes:
            logger.info("🧬 %d novo(s) híbrido(s) gerado(s)!", len(new_nodes))
        else:
            logger.info("🧬 nenhum híbrido foi gerado neste ciclo")

    def _crossover(self, a: Node, b: Node) -> tuple:
        stats = {"skill": "general"}
        child = copy.deepcopy(a)
        child.name = _short_name(a.name, "x", b.name, str(self.generation))

        skill_name = a.node_type if a.node_type != "general" else a.name

        if not skill_executor.can_execute(skill_name):
            skill_name = b.node_type if b.node_type != "general" else b.name
            if not skill_executor.can_execute(skill_name):
                if a.name.startswith("evo_") or b.name.startswith("evo_"):
                    skill_registry.register(Skill(
                        name=child.name,
                        description=f"Evolvable crossover of {a.name} x {b.name}",
                    ))
                else:
                    logger.warning("⚠️ [CROSSOVER] Nenhum dos pais tem skill registrada: a=%s(type=%s) b=%s(type=%s)",
                                   a.name, a.node_type, b.name, b.node_type)
                skill_name = "general"

        stats["skill"] = skill_name
        child.node_type = skill_name
        child.seed_id = a.seed_id or a.name
        child.mutation_id = _short_name("crossover", a.name, "x", b.name, str(self.generation))
        child.version = f"v{self.generation}"

        old_strategy = child.strategy
        child.strategy = a.strategy if secrets.randbelow(100) > 50 else b.strategy
        if child.strategy != old_strategy:
            logger.debug("[CROSSOVER] Strategy herdada: %s (de %s)", child.strategy,
                         "pai A" if child.strategy == a.strategy else "pai B")

        if child.strategy not in self.strategies:
            child.strategy = secrets.choice(self.strategies)
            logger.debug("[CROSSOVER] Strategy corrigida para: %s", child.strategy)

        child.model_hint = a.model_hint if secrets.randbelow(100) > 50 else b.model_hint

        WorkDir(child.name, "evo_gen_%d" % self.generation).ensure().append_log("crossover %s x %s skill=%s" % (a.name, b.name, skill_name))

        self._record_lineage(
            child, "crossover", parent_name=f"{a.name} x {b.name}",
            parent_fitness=(a.fitness() + b.fitness()) / 2,
            strategy=child.strategy,
        )
        return child, stats

    # --------------------------------------------------
    # LINEAGE ANALYSIS
    # --------------------------------------------------

    def lineage_graph(self) -> Dict[str, List[str]]:
        """Reconstruct the full causal DAG from all EVO nodes' lineage entries.

        Returns a dict mapping each node name to its list of parent names,
        forming a directed acyclic graph of evolutionary history.
        """
        dag: Dict[str, List[str]] = {}
        for name, node in self.graph.nodes.items():
            if not node.lineage:
                continue
            parents = []
            for entry in node.lineage:
                if entry.event_type == "seed":
                    parents.append(entry.parent_name)
                elif entry.event_type == "mutation":
                    parents.append(entry.parent_name)
                elif entry.event_type == "crossover":
                    # parent_name is "a x b" — split into two parents
                    for p in entry.parent_name.split(" x "):
                        p = p.strip()
                        if p:
                            parents.append(p)
            dag[name] = parents
        return dag

    def fitness_history(self, node_name: str) -> List[float]:
        """Return per-generation fitness values for a node based on its lineage."""
        node = self.graph.nodes.get(node_name)
        if not node or not node.lineage:
            return []
        return [node.fitness() for _ in node.lineage]

    def lineage_report(self, node_name: str) -> str:
        """Generate a human-readable ancestry report for a node."""
        node = self.graph.nodes.get(node_name)
        if not node:
            return f"Node '{node_name}' not found."
        lines = [f"=== Lineage Report: {node_name} ==="]
        lines.append(f"Strategy: {node.strategy}  |  Fitness: {node.fitness():.4f}")
        lines.append(f"Seed ID: {node.seed_id}  |  Mutation: {node.mutation_id}")
        lines.append("")
        if not node.lineage:
            lines.append("  (no lineage entries — core or standalone node)")
        else:
            lines.append("  Events:")
            for i, entry in enumerate(node.lineage):
                lines.append(
                    f"  [{i+1}] gen={entry.generation} | {entry.event_type.upper():12s} | "
                    f"parent={entry.parent_name:30s} | "
                    f"fitness_delta={entry.fitness_delta:+.4f} | "
                    f"strategy={entry.strategy}"
                )
        lines.append("")
        # Causal ancestors
        dag = self.lineage_graph()
        ancestors = []
        def _collect(n: str, seen: set):
            for p in dag.get(n, []):
                if p not in seen:
                    seen.add(p)
                    ancestors.append(p)
                    _collect(p, seen)
        _collect(node_name, {node_name})
        if ancestors:
            lines.append(f"  Ancestors ({len(ancestors)}): {', '.join(ancestors)}")
        else:
            lines.append("  (no ancestors — root seed)")
        return "\n".join(lines)


