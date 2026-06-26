# iaglobal/evolution/evolutionengine.py

import copy
import hashlib
import secrets
import logging
import time
import asyncio
from typing import Dict, Optional, List, Tuple, Any

from iaglobal.graphs.node import Node, LineageEntry
from iaglobal.graphs.workdir import WorkDir
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution import darwin_harness as darwin
from iaglobal.evolution.darwin_harness import DarwinHarness, EvolutionMetrics, SimulationRecorder
from iaglobal.evolution.canonical_graph import canonicalize, compute_graph_hash
from iaglobal.evolution.execution_registry import registry as exec_registry
from iaglobal.evolution.skills.skill_executor import skill_executor
from iaglobal.evolution.skills.skill_registry import skill_registry
from iaglobal.evolution.skills.skill import ExecutionPolicy, Skill
from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
from iaglobal.events import DecisionEvent
from iaglobal.models.event_bus import bus, EventType
from iaglobal.evolution.execution_context import ExecutionContext
from iaglobal.events import dispatcher
from iaglobal.utils.hash_utils import LineageID
from iaglobal.utils.helpers import run_async_safe
from iaglobal.evolution.evolutionruntime import EvolutionStrategy, FastEvolutionStrategy
from iaglobal.core.law_engine import law_compliance_engine, ComplianceStatus

logger = logging.getLogger(__name__)

MAX_NODE_NAME = 120
MAX_HYBRIDS_PER_GENERATION = 7

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

    # Nomes dos nós core que NÃO devem ser evoluídos/selecionados
    CORE_NODE_NAMES: List[str] = [
        "agentmailbox", "prompt_intake", "prompt_improver", "enhancement",
        "orchestrator_agent", "pm", "requirements",
        "domain_analysis", "business_rules", "local_knowledge", "search",
        "knowledge", "knowledge_analyzer", "prompt_builder", "dependency",
        "technology_selection", "architect", "system_design", "api_design",
        "database_design", "security_design", "threat_modeling",
        "performance_design", "observability_design", "architecture_validator",
        "planner", "task_breakdown", "execution_plan",
        "coder", "code_executor", "frontend_builder", "backend_builder",
        "database_builder", "api_builder",
        "test_generator", "integrator", "reviewer", "semantic_validator",
        "security_audit", "performance_audit", "compliance_audit",
        "qa", "tester", "debugger", "validator", "fix_validator", "debug_coder",
        "documentation", "deployment_plan", "release", "metrics", "optimization",
        "retrospective", "result_agent", "critic", "memory_writer", "memory_cleaner",
        "evaluator", "gap_analyzer", "skill_generator", "sandbox_validator",
        "evolution_committee", "pipeline_updater", "evolution_trigger",
        "multi_coder",
    ]

    def __init__(
            self,
            graph: ExecutionGraph,
            mutation_rate: float = 0.1,
            strategies: Optional[List[str]] = None,
            strategy_mutation_rates: Optional[Dict[str, float]] = None,
            meta_designer: Optional[MetaAgentDesigner] = None # ⬅️ ADICIONADO PARA TESTABILIDADE
        ):
            self.graph = graph
            self.adversarial = darwin.DynamicAdversarialEnvironment(seed=secrets.randbelow(2**32))
            self.evolution_metrics = darwin.EvolutionMetrics()
            self.simulation_recorder = darwin.SimulationRecorder()
            self.generation = graph.generation
            self._last_graph_hash = getattr(graph, '_graph_hash', "")

            self.mutation_rate = mutation_rate

            self.strategies = strategies or [
                "coding",
                "research",
                "fast",
                "explore"
            ]

            # 🎯 MUTATION RATE POR ESTRATÉGIA
            self.strategy_mutation_rates = strategy_mutation_rates or {
                "coding": 0.15,
                "research": 0.20,
                "fast": 0.30,
                "explore": 0.40,
                "general": 0.15,
                "reflection": 0.20,
                "debug": 0.25,
            }

            # 🏗️ MetaAgentDesigner (arquiteta a equipe para cada task)
            # Se um designer for injetado (via teste), usa ele; senão, cria um novo.
            self.designer: MetaAgentDesigner = meta_designer or MetaAgentDesigner(graph)

            # 🎯 Task-aware attributes
            self.current_task: str = ""
            self.task_strategies: set = set()
            self.task_technologies: set = set()
            self.task_type: str = "general"
            self._task_agents_created: bool = False

    def _create_task_agents(self):
        """Agentes especialistas são criados via MetaAgentDesigner (instruções, não nós).
        Este método é mantido apenas para compatibilidade — não cria mais nós no DAG."""
        self._task_agents_created = True

    def register_lineage(self, node, event_type: str, parent_name: str, parent_fitness: float = 0.0):
        """Wrapper público para o registro de linhagem."""
        self._record_lineage(
            node=node, 
            event_type=event_type, 
            parent_name=parent_name, 
            parent_fitness=parent_fitness
        )

    def _finalize_cycle(self):
        """Finaliza o ciclo, atualiza o hash do grafo e salva o estado persistente."""
        # 1. Recalcula o hash do grafo para garantir integridade
        if hasattr(self.graph, 'recalculate_hash'):
            self.graph.recalculate_hash()
        elif hasattr(self.graph, '_compute_graph_hash'):
            self.graph._graph_hash = self.graph._compute_graph_hash()
            
        # 2. Salva o estado em disco
        self._save_state()
        
        # 3. Incrementa a geração
        self.generation += 1
        
        logger.info("🏁 Ciclo de evolução %d finalizado com sucesso.", self.generation - 1)

    async def set_task_async(self, task: str):
        """Versão assíncrona para não bloquear o loop durante a análise."""
        if task == self.current_task:
            return
            
        self.current_task = task
        self._task_agents_created = False
        
        # Assume que o TaskAnalyzer pode ter um método async
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        # Encapsula em thread se o método ainda for síncrono
        analysis = await asyncio.to_thread(TaskAnalyzer.analyze, task)
        
        self.task_strategies = set(analysis.get("strategies", []))
        self.task_technologies = set(analysis.get("technologies", []))
        self.task_type = analysis.get("task_type", "general")
        
        # Atualiza estratégias de forma atômica
        for s in self.task_strategies:
            if s not in self.strategies:
                self.strategies.append(s)
                self.strategy_mutation_rates[s] = 0.25
                
        logger.info("[TASK] Task registrada: type=%s", self.task_type)

        # 🏗️ MetaAgentDesigner assíncrono
        try:
            # Garante que o design também rode em thread se for pesado
            design = await asyncio.to_thread(self.designer.design_team, task)
            logger.info(
                "[TASK] MetaAgentDesigner: %d estratégias, %d gaps detectados",
                len(design.get("strategies", [])),
                len(design.get("lacunas_detectadas", []))
            )
        except Exception as e:
            logger.error("[TASK] Falha crítica no MetaAgentDesigner: %s", e)
            # Aqui, ao invés de fallback síncrono, talvez disparar um evento no bus
            bus.publish(EventType.TASK_INIT_FAILED, {"error": str(e)})

    def set_task(self, task: str):
        """Sync wrapper for set_task_async - called via asyncio.to_thread."""
        return run_async_safe(lambda: self.set_task_async(task))

    # --------------------------------------------------
    # SYNC WRAPPERS (called via asyncio.to_thread from evolve_async)
    # --------------------------------------------------

    def _run_evolution_step(self, step_fn):
        """Executa um passo evolutivo (wrapper para compatibilidade)."""
        result = step_fn()
        if result is not None:
            import asyncio
            if asyncio.iscoroutine(result):
                return run_async_safe(lambda: result)

    def _perform_canonicalize(self):
        """Canonicaliza o grafo (dedup, ordenação, consolidação)."""
        from iaglobal.evolution.canonical_graph import canonicalize, compute_graph_hash
        self.graph._graph_hash = compute_graph_hash(self.graph.nodes)
        canonicalize(self.graph.nodes)
        logger.info("[EVO] Grafo canonicalizado: hash=%s", self.graph._graph_hash[:16] if self.graph._graph_hash else "N/A")

    def _save_state(self):
        """Persiste o estado evolutivo em disco."""
        try:
            import json
            from iaglobal._paths import CACHE_DB
            state_path = CACHE_DB / "evolution_state.json"
            state = {
                "generation": self.generation,
                "graph_hash": self._last_graph_hash,
                "mutation_rate": self.mutation_rate,
                "timestamp": time.time(),
                "node_count": len(self.graph.nodes),
            }
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(state_path, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning("[EVO] Falha ao salvar estado: %s", e)

    def _seed_evo_population(self):
        """Sync wrapper para seed_evo_population_async."""
        return run_async_safe(lambda: self.seed_evo_population_async())

    def _mutate_nodes(self):
        """Sync wrapper para mutate_nodes_async."""
        return run_async_safe(lambda: self.mutate_nodes_async())

    def _crossover_phase(self):
        """Sync wrapper para _crossover_phase_async."""
        return run_async_safe(lambda: self._crossover_phase_async())

    def _finalize_evolution_step(self):
        """Finaliza o passo evolutivo — consolida e gera relatório."""
        self._finalize_cycle()
        evo_count = sum(1 for n in self.graph.nodes if n not in self.CORE_NODE_NAMES)
        logger.info("[EVO] Passo finalizado: %d nós evo ativos, geração %d", evo_count, self.generation)

    # --------------------------------------------------
    # CORE GENETIC OPERATORS
    # --------------------------------------------------

    def _crossover(self, parent_a: Node, parent_b: Node) -> Tuple[Node, dict]:
        """Operador de crossover: combina dois pais para gerar um filho híbrido.

        Retorna (child_node, stats_dict).
        """
        stats = {
            "parent_a": parent_a.name,
            "parent_b": parent_b.name,
            "strategy": None,
            "model_hint": None,
        }

        child = copy.deepcopy(parent_a)
        child_name = _short_name(parent_a.name, "x", parent_b.name, str(self.generation))
        child.name = child_name
        child.node_type = "hybrid"
        child.seed_id = ""
        child.mutation_id = _short_name("cx", str(self.generation), secrets.token_hex(4))

        # Estratégia: herda do pai mais fit (ou aleatório se sem fitness)
        fa = parent_a.fitness() if hasattr(parent_a, 'fitness') and callable(parent_a.fitness) else 0.0
        fb = parent_b.fitness() if hasattr(parent_b, 'fitness') and callable(parent_b.fitness) else 0.0
        fittest = parent_a if fa >= fb else parent_b
        child.strategy = fittest.strategy
        stats["strategy"] = child.strategy

        # Model hint: 50% chance de herdar de cada pai
        child.model_hint = secrets.choice([parent_a.model_hint, parent_b.model_hint])
        stats["model_hint"] = child.model_hint

        # Taxa de mutação: média dos pais
        child.mutation_rate = (getattr(parent_a, 'mutation_rate', 0.1) + getattr(parent_b, 'mutation_rate', 0.1)) / 2

        # Linhagem: registra ambos os pais
        parent_a_lid = parent_a.lineage[-1].lineage_id if parent_a.lineage else ""
        parent_a_marker = parent_a.lineage[-1].lineage_marker if parent_a.lineage else ""
        parent_b_lid = parent_b.lineage[-1].lineage_id if parent_b.lineage else ""
        parent_b_marker = parent_b.lineage[-1].lineage_marker if parent_b.lineage else ""

        # Usa o marcador do pai mais fit
        fittest_marker = parent_a_marker if fa >= fb else parent_b_marker
        self._record_lineage(
            child, "crossover",
            parent_name=f"{parent_a.name} x {parent_b.name}",
            parent_lineage_id=parent_a_lid,
            parent_lineage_marker=fittest_marker,
            strategy=child.strategy,
        )

        logger.info(
            "🧬 Crossover: '%s' = %s x %s (strategy=%s)",
            child.name, parent_a.name, parent_b.name, child.strategy,
        )

        return child, stats

    # --------------------------------------------------
    # ASYNC EVOLUTION CYCLE
    # --------------------------------------------------

    async def evolve_async(self, strategy: Optional[EvolutionStrategy] = None):
        """Versão assíncrona do ciclo evolutivo.
        
        Args:
            strategy: Estratégia de evolução (Fast, Deep, etc).
                      Se None, usa FastEvolutionStrategy como padrão.
        """
        return await self._evolve_impl(strategy=strategy)

    async def evolve(self, strategy: Optional[EvolutionStrategy] = None):
        """Alias para evolve_async — compatibilidade."""
        return await self._evolve_impl(strategy=strategy)

    async def _evolve_impl(self, strategy: Optional[EvolutionStrategy] = None):
        """Implementação compartilhada do ciclo evolutivo.
        
        Args:
            strategy: Estratégia de evolução que controla mutation_rate,
                     crossover_rate, selection_pressure e exploration_rate.
        """
        strategy = strategy or FastEvolutionStrategy()
        logger.info("🧬 [ASYNC] Iniciando ciclo de evolução: gen=%d, strategy=%s",
                    self.generation, strategy.name)
        
        # ── VALIDAÇÃO DAS LEIS UNIVERSAIS (ANTES DA EVOLUÇÃO) ──────────────
        proposal_data = {
            "reasoning": f"Ciclo evolutivo da geração {self.generation} com estratégia {strategy.name}",
            "generation": self.generation,
            "strategy": strategy.name,
            "mutation_rate": strategy.mutation_rate,
            "parent_version": f"gen_{self.generation - 1}" if self.generation > 0 else "genesis",
            "performance_metrics": {
                "latency_ms": getattr(self, '_last_latency_ms', 0),
            },
            "resource_usage": {
                "nadph_reserve": getattr(self, '_nadph_reserve', 1.0),
            },
        }
        
        compliance_report = law_compliance_engine.validate_proposal(
            proposal_type="mutation",
            proposal_data=proposal_data,
            contexto={
                "agent_id": "evolution_engine",
                "generation": self.generation,
                "task": self.current_task.get("prompt", "") if self.current_task else "",
            },
        )
        
        if compliance_report.status == ComplianceStatus.REJECTED:
            logger.error(
                "❌ [LEIS UNIVERSAIS] Evolução REJEITADA | proposta=%s | score=%.2f | violações=%d",
                compliance_report.proposal_id,
                compliance_report.score_conformidade,
                len(compliance_report.violations),
            )
            for violacao in compliance_report.violations:
                logger.error(
                    "  ⚠️ Violação: %s (severidade %d) - %s",
                    violacao.lei, violacao.severidade, violacao.descricao,
                )
            logger.info("  💡 Orientação OmniMind: %s", compliance_report.orientacao_omnimind)
            raise RuntimeError(
                f"Evolução bloqueada pelo LawComplianceEngine: {len(compliance_report.violations)} violações detectadas. "
                f"Score: {compliance_report.score_conformidade:.2f}. "
                f"Orientação: {compliance_report.orientacao_omnimind}"
            )
        
        if compliance_report.status == ComplianceStatus.REQUIRES_REVISION:
            logger.warning(
                "⚠️ [LEIS UNIVERSAIS] Evolução requer revisão | proposta=%s | score=%.2f | violações=%d",
                compliance_report.proposal_id,
                compliance_report.score_conformidade,
                len(compliance_report.violations),
            )
            for violacao in compliance_report.violations:
                logger.warning(
                    "  🔧 Correção sugerida: %s - %s",
                    violacao.lei, violacao.sugestao_correcao,
                )
            # Continua mas com logging detalhado
        
        logger.info(
            "✅ [LEIS UNIVERSAIS] Evolução APROVADA | proposta=%s | score=%.2f",
            compliance_report.proposal_id,
            compliance_report.score_conformidade,
        )
        # ── FIM DA VALIDAÇÃO ────────────────────────────────────────────────
        
        # Ajusta mutation_rate com base na estratégia
        original_mutation_rate = self.mutation_rate
        self.mutation_rate = strategy.mutation_rate
        
        # 1. Canonicalização (CPU Bound - roda em thread para não travar o loop)
        self._perform_canonicalize()
        self._run_evolution_step(lambda: None)
        
        # 2. Seed e População (I/O + CPU)
        await self.set_task_async(self.current_task)
        self._seed_evo_population()
        self._create_task_agents()
        
        # 3. Seleção, Mutação e Crossover com parâmetros da estratégia
        self._select_survivors(pressure=strategy.selection_pressure)
        self._mutate_nodes()
        self._crossover_phase()
        await self.run_darwin_harness_async()
        
        # 3b. Evolução de handlers (geração de código via AST)
        await self._evolve_handlers()
        
        # 4. Finalização
        self._finalize_evolution_step()
        
        # Restaura mutation_rate original
        self.mutation_rate = original_mutation_rate
        
        logger.info("✅ [ASYNC] Ciclo evolutivo concluído com sucesso (strategy=%s).", strategy.name)

    async def run_darwin_harness_async(self) -> Dict[str, Any]:
        """Executa o harness Darwin de métricas, adversidade e invariantes."""
        snapshot = darwin.snapshot_graph(self.graph)
        previous = getattr(self, "_last_darwin_snapshot", snapshot)
        distance = darwin.structural_distance(previous, snapshot)
        task_info = self.adversarial.next_generation()
        task = darwin.generate_adversarial_task(
            min(1.0, self.adversarial.adversarial_pressure),
        )
        hard_violations = darwin.check_hard_invariants(self.graph)
        soft_warnings = darwin.check_soft_invariants(self.graph)
        survivor_ok = darwin.check_survivor_fitness_invariant(self, [], [])
        crossover_ok, crossover_issues = darwin.check_crossover_invariant(self.graph)
        diversity_ok = darwin.check_diversity_invariant(self.graph)
        trend_scores = [s.mean_fitness for s in self.evolution_metrics.snapshots]
        trend_ok = darwin.check_trend_invariant(trend_scores)
        strict_trend = self.evolution_metrics.is_strictly_improving()
        cumulative = self.evolution_metrics.cumulative_gain()
        convergence = self.evolution_metrics.convergence_rate()
        collapsed = self.evolution_metrics.diversity_collapsed()
        task_has_constraints = task_info.has_adversarial
        output_eval = darwin.evaluate_output("", "")
        fitness_values = [
            node.fitness()
            for node in self.graph.nodes.values()
            if node.name not in self.CORE_NODE_NAMES
        ]
        first_evo = next(
            (node for node in self.graph.nodes.values() if node.name not in self.CORE_NODE_NAMES),
            None,
        )
        core_node_count = len(self.core_nodes)
        lineage_history = self.fitness_history(first_evo.name) if first_evo else []
        lineage_text = self.lineage_report(first_evo.name) if first_evo else ""
        if first_evo and first_evo.lineage:
            self.register_lineage(
                first_evo,
                "evolution_cycle",
                parent_name=first_evo.name,
                parent_fitness=first_evo.fitness(),
            )
        if fitness_values:
            self.evolution_metrics.record(
                darwin.GenerationSnapshot(
                    gen=self.generation,
                    fitness_values=fitness_values,
                    population_size=len(self.graph.nodes),
                    diversity=distance,
                    error_count=len(hard_violations) + len(soft_warnings),
                )
            )
        recorder_snapshot = self.simulation_recorder.record(
            self.graph,
            self,
            fitness_values,
        )
        reference = getattr(self, "_last_darwin_reference", {})
        regressions = self.simulation_recorder.detect_regression(reference)
        self._last_darwin_snapshot = snapshot
        self._last_darwin_reference = self.simulation_recorder.snapshot()
        return {
            "generation": self.generation,
            "task": task_info.prompt,
            "adversarial_task": task,
            "adversarial_pressure": self.adversarial.adversarial_pressure,
            "structural_distance": distance,
            "snapshot": snapshot,
            "hard_violations": hard_violations,
            "soft_warnings": soft_warnings,
            "survivor_ok": survivor_ok,
            "crossover_ok": crossover_ok,
            "crossover_issues": crossover_issues,
            "diversity_ok": diversity_ok,
            "trend_ok": trend_ok,
            "strict_trend": strict_trend,
            "cumulative_gain": cumulative,
            "convergence_rate": convergence,
            "task_has_constraints": task_has_constraints,
            "diversity_collapsed": collapsed,
            "output_eval": output_eval,
            "regressions": regressions,
            "recorder_snapshot": recorder_snapshot,
            "core_node_count": core_node_count,
            "lineage_history": lineage_history,
            "lineage_report_text": lineage_text,
            "metrics_generations": self.evolution_metrics.generations,
        }

    def _is_evo_cloneable(self, name: str) -> bool:
        """
        Valida se um nó é elegível para replicação evolutiva.
        """
        if not name:
            return False
            
        node = self.graph.nodes.get(name)
        if not node:
            logger.warning("[EVO] Tentativa de checar clone de nó inexistente: %s", name)
            return False

        # Determina a skill correspondente
        skill_name = node.node_type if node.node_type != "general" else name
        
        # Validação do Executor
        if not skill_executor.can_execute(skill_name):
            return False
            
        # Validação de Política de Execução
        skill = skill_executor.registry.get(skill_name)
        if skill and skill.execution_policy == ExecutionPolicy.SINGLE_RUN:
            logger.debug("[EVO] Nó '%s' ignorado: policy=SINGLE_RUN", name)
            return False
            
        return True

    async def seed_evo_population_async(self):
        """Versão assíncrona que isola I/O de disco do loop principal."""
        from iaglobal.evolution.skill_quarantine import quarantine
        
        # 1. Filtra nós candidatos (processamento de memória - Rápido)
        candidates = [
            (name, node) for name, node in self.graph.nodes.items()
            if name in self.CORE_NODE_NAMES
        ]

        seeds = {}
        for name, node in candidates:
            skill_name = node.node_type if node.node_type != "general" else name
            
            # Validações rápidas
            if quarantine.is_quarantined(skill_name) or \
               not skill_executor.can_execute(skill_name) or \
               not self._is_evo_cloneable(name):
                continue

            seed_name = f"evo_{name}_seed_{self.generation}"
            if seed_name in self.graph.nodes:
                continue

            # 2. Criação do clone (Deepcopy é CPU-bound)
            seed = await asyncio.to_thread(copy.deepcopy, node)
            seed.name = seed_name
            seed.node_type = skill_name
            seed.seed_id = seed_name
            seed.mutation_id = ""
            seed.version = "v1"

            # Herda lineage_id e marker do progenitor
            parent_lid = node.lineage[-1].lineage_id if node.lineage else ""
            parent_marker = node.lineage[-1].lineage_marker if node.lineage else ""
            
            await asyncio.to_thread(
                self._record_lineage, seed, "seed",
                parent_name=name,
                parent_lineage_id=parent_lid,
                parent_lineage_marker=parent_marker,
                strategy=seed.strategy,
            )
            
            # O I/O de disco é delegada para o threadpool
            self._initialize_seed_workdir(seed_name, skill_name)
            
            seeds[seed_name] = seed

        # 3. Atualiza o grafo de forma atômica
        if seeds:
            self.graph.nodes.update(seeds)
            logger.info("🌱 %d novo(s) agente(s) adicionados ao grafo.", len(seeds))
        else:
            self._create_synthetic_evo_seeds()

    def _initialize_seed_workdir(self, name: str, skill: str):
        """Helper isolado para I/O síncrono com tratamento de erros."""
        try:
            # Garante a criação do diretório e registro de log
            wd = WorkDir(name, "evo_init")
            wd.ensure()
            wd.append_log(f"evo seed criado de skill={skill}")
        except Exception as e:
            # Logger crítico, pois I/O de arquivos é um ponto comum de falha em servidores
            logger.error("[EVO] Falha ao inicializar WorkDir para '%s': %s", name, str(e))
            # O sistema continua, pois a falta de log não deve abortar a criação do agente

    def _create_synthetic_evo_seeds(self):
        """Wrapper compatível para _create_synthetic_evo_seeds_async."""
        return run_async_safe(lambda: self._create_synthetic_evo_seeds_async())

    async def _create_synthetic_evo_seeds_async(self):
        """Versão assíncrona para criação de seeds sintéticos."""
        from iaglobal.graphs.workdir import WorkDir
        
        gen = self.generation
        synths = {}
        base_nodes = [
            ("prompt_intake", "coding"), ("architect", "research"),
            ("planner", "explore"), ("coder", "fast"),
            ("reviewer", "reflection"), ("debug_coder", "debug"),
        ]

        for src_name, strategy in base_nodes:
            src = self.graph.nodes.get(src_name)
            if not src:
                continue
                
            seed_name = f"evo_{strategy}_seed_{gen}"
            if seed_name in self.graph.nodes:
                continue

            # 1. Criação (CPU Bound isolada)
            seed = await asyncio.to_thread(copy.deepcopy, src)
            seed.name = seed_name
            seed.node_type = "general"
            seed.seed_id = seed_name
            seed.mutation_id = ""
            seed.strategy = strategy
            seed.version = "v1"
            
            # 2. Linhagem e Registro com propagação de marker
            src_node = self.graph.nodes.get(src_name)
            parent_lid = src_node.lineage[-1].lineage_id if src_node and src_node.lineage else ""
            parent_marker = src_node.lineage[-1].lineage_marker if src_node and src_node.lineage else ""
            await asyncio.to_thread(
                self._record_lineage, seed, "seed",
                parent_name=src_name,
                parent_lineage_id=parent_lid,
                parent_lineage_marker=parent_marker,
                strategy=strategy,
            )
            
            # Registro de skill assíncrono
            if not skill_executor.can_execute(seed_name):
                await asyncio.to_thread(skill_registry.register, Skill(
                    name=seed_name,
                    version="v1",
                    description=f"Evolvable synthetic seed ({strategy})"
                ))
            
            # 3. I/O Isolado
            await asyncio.to_thread(self._initialize_seed_workdir, seed_name, f"sintetico_{strategy}")
            
            synths[seed_name] = seed
            logger.info("🌱 EVO sintético: '%s' (strategy=%s)", seed_name, strategy)

        if synths:
            self.graph.nodes.update(synths)
            logger.info("🌱 %d EVO seed(s) sintético(s) adicionados!", len(synths))

    @property
    def core_nodes(self):
        """Referência dinâmica aos nós core registrados no grafo."""
        return getattr(
            self.graph,
            "core_nodes_registry",
            {
                name: node
                for name, node in self.graph.nodes.items()
                if name in self.CORE_NODE_NAMES
            },
        )

    def _record_lineage(self, node: Node, event_type: str, *,
                        parent_name: str = "",
                        parent_lineage_id: str = "",
                        parent_lineage_marker: str = "",
                        parent_fitness: float = 0.0,
                        strategy: str = ""):
        """Registro de linhagem com ID SHA3-512 + marcador hereditário."""
        from iaglobal.events import dispatcher
        
        parent_lid = parent_lineage_id or (node.lineage[-1].lineage_id if node.lineage else "")
        parent_marker = parent_lineage_marker or (node.lineage[-1].lineage_marker if node.lineage else "")
        
        lineage_id, lineage_marker = LineageID.compute(
            entity_type="node",
            name=node.name,
            parent_lineage_id=parent_lid,
            generation=self.generation,
            metadata=f"{event_type}:{strategy or node.strategy}",
        )
        # Se há progenitor, herda o marcador; senão, o compute já gerou um novo
        if parent_marker:
            lineage_marker = parent_marker
        
        entry = LineageEntry(
            generation=self.generation,
            event_type=event_type,
            parent_name=parent_name,
            parent_fitness=parent_fitness,
            strategy=strategy or node.strategy,
            fitness_delta=node.fitness() - parent_fitness if parent_fitness > 0 else 0.0,
            timestamp=time.time(),
            lineage_id=lineage_id,
            lineage_marker=lineage_marker,
        )
        
        node.lineage.append(entry)
        
        logger.debug("[LINEAGE] Registrado: %s → %s (marker=%s)", node.name, event_type, lineage_marker[:8])

    def _select_survivors(self, pressure: Optional[float] = None):
        """
        Seleção por Truncamento. A taxa de sobrevivência é controlada
        pela estratégia (pressure = fração que sobrevive).
        
        Args:
            pressure: Fração de sobreviventes (ex: 0.3 = top 30%).
                      Se None, usa 0.5 (50% padrão).
        """
        pressure = pressure if pressure is not None else 0.5
        # Separação eficiente
        core_nodes = {}
        evo_nodes = []
        
        for name, node in self.graph.nodes.items():
            if name in self.CORE_NODE_NAMES:
                core_nodes[name] = node
            else:
                evo_nodes.append(node)

        if not evo_nodes:
            self.graph.nodes = core_nodes
            logger.info("🧬 Nenhum agente evolutivo para selecionar.")
            return

        # Ordenação por fitness
        evo_sorted = sorted(evo_nodes, key=lambda n: n.fitness(), reverse=True)
        
        # Seleção baseada na pressão da estratégia
        cutoff = max(1, int(len(evo_sorted) * pressure))
        survivors = evo_sorted[:cutoff]
        eliminated = evo_sorted[cutoff:]

        logger.info("🧬 Seleção (pressure=%.1f): %d candidatos | %d sobreviventes | %d eliminados.",
                    pressure, len(evo_nodes), len(survivors), len(eliminated))

        # Reconstrução atômica
        survivors_dict = {n.name: n for n in survivors}
        self.graph.nodes = {**core_nodes, **survivors_dict}

    async def mutate_nodes_async(self):
        """Versão assíncrona do motor de mutação."""
        mutated = {}
        evo_targets = [n for n in self.graph.nodes.values() if n.name not in self.CORE_NODE_NAMES]
        
        logger.info("🔀 Iniciando mutação adaptativa para %d agentes...", len(evo_targets))

        # Processa cada mutação em thread separada para não travar o loop
        for node in evo_targets:
            # _mutate_node deve ser uma função pura (ou delegada)
            new_node, stats = self._mutate_node(node)
            
            # Lógica de prevenção de extinção (mantida em thread)
            if not (stats.get("strategy_shifted") or stats.get("model_drifted")) and len(evo_targets) <= 2:
                new_node.strategy = secrets.choice(["coding", "research", "fast", "explore", "general"])
                stats["strategy_shifted"] = True

            if stats.get("strategy_shifted") or stats.get("model_drifted"):
                # Garante nome único
                if new_node.name in self.graph.nodes:
                    new_node.name = _short_name(node.name, "mut", str(self.generation), str(secrets.randbelow(9000) + 1000))
                
                mutated[new_node.name] = new_node
                logger.info("🔀 Variação criada: '%s' (estratégia: %s)", new_node.name, new_node.strategy)

        # Atualização atômica
        if mutated:
            self.graph.nodes.update(mutated)
            logger.info("🔀 %d nova(s) variação(ões) adicionada(s)!", len(mutated))

    def _mutate_node(self, node: Node) -> tuple:
        """
        Versão pura (CPU-bound) do mutate_node. 
        Removemos I/O síncrono daqui.
        """
        stats = {"skill_blocked": False, "strategy_shifted": False, "model_drifted": False}
        new_node = copy.deepcopy(node)
        new_node.name = _short_name(node.name, "mut", str(self.generation))
        
        # 1. Ajuste de Estratégia (Baseado em probabilidade)
        base_rate = self.strategy_mutation_rates.get(node.strategy, self.mutation_rate)
        # O ajuste do effective_rate deve ser calculado antes de entrar na thread
        # (Passamos o valor calculado como parâmetro se necessário)
        
        if secrets.randbelow(1000000) < int(base_rate * 1000000):
            candidates = list(self.task_strategies) if self.task_strategies else self.strategies
            new_node.strategy = secrets.choice(candidates)
            stats["strategy_shifted"] = True

        # 2. Model Drift (usa self.mutation_rate que foi ajustado pela estratégia)
        effective_rate = self.strategy_mutation_rates.get(node.strategy, self.mutation_rate)
        if secrets.randbelow(1000000) < int(effective_rate * 1000000):
            from iaglobal.providers.provider_config import ProviderConfig
            new_node.model_hint = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
            stats["model_drifted"] = True

        return new_node, stats

    async def _crossover_phase_async(self):
        """Versão assíncrona do Crossover."""
        evo_nodes = [node for node in self.graph.nodes.values() if node.name not in self.CORE_NODE_NAMES]
        logger.info("🧬 Iniciando fase de Crossover para %d agentes...", len(evo_nodes))

        results = []
        for i in range(len(evo_nodes)):
            if len(results) >= MAX_HYBRIDS_PER_GENERATION:
                break
            for j in range(i + 1, len(evo_nodes)):
                if len(evo_nodes) > 2 and secrets.randbelow(100) > 30:
                    continue
                child, stats = self._crossover(evo_nodes[i], evo_nodes[j])
                results.append((child, stats))
                if len(results) >= MAX_HYBRIDS_PER_GENERATION:
                    break
        
        # Atualização atômica do Grafo
        new_nodes = {child.name: child for child, stats in results if child.name not in self.graph.nodes}
        self.graph.nodes.update(new_nodes)
        
        if new_nodes:
            logger.info("🧬 %d híbrido(s) adicionado(s)!", len(new_nodes))

    async def _evolve_handlers(self):
        """Evolui handlers no nível de código-fonte via mutation/crossover AST."""
        try:
            from iaglobal.evolution.handler_evolution import HandlerEvolver
            evolver = HandlerEvolver(engine=self, generation=self.generation)
            stats = await asyncio.to_thread(evolver.evolve)
            if stats["registered"]:
                logger.info(
                    "[EVO] Handler evolution: %d mutações, %d crossovers, %d registrados",
                    stats["mutations"], stats["crossovers"], stats["registered"],
                )
        except Exception as exc:
            logger.warning("[EVO] Handler evolution error (non-fatal): %s", exc)

    # --------------------------------------------------
    # LINEAGE ANALYSIS
    # --------------------------------------------------

    def lineage_graph(self) -> Dict[str, List[str]]:
        """Reconstrói o grafo de linhagem de forma otimizada."""
        dag: Dict[str, List[str]] = {}
        for name, node in self.graph.nodes.items():
            if not node.lineage:
                continue
            
            parents = set() # Use set para evitar duplicatas acidentais
            for entry in node.lineage:
                if entry.event_type in ("seed", "mutation"):
                    parents.add(entry.parent_name)
                elif entry.event_type == "crossover":
                    # Extração robusta dos pais
                    p_list = [p.strip() for p in entry.parent_name.split(" x ") if p.strip()]
                    parents.update(p_list)
            
            dag[name] = list(parents)
        return dag

    def fitness_history(self, node_name: str) -> List[float]:
        """Retorna o histórico de fitness extraído dos dados já registrados."""
        node = self.graph.nodes.get(node_name)
        if not node or not node.lineage:
            return []
        
        # Otimização: ler o fitness a partir do registro de linhagem, 
        # sem chamar node.fitness() repetidamente
        history = []
        current_f = node.fitness() 
        # Reverte o fitness_delta para obter o valor histórico
        for entry in reversed(node.lineage):
            history.insert(0, current_f)
            current_f -= entry.fitness_delta
        return history

    def lineage_report(self, node_name: str) -> str:
        """Generate a human-readable ancestry report for a node."""
        node = self.graph.nodes.get(node_name)
        if not node:
            return f"Node '{node_name}' not found."
        lines = [f"=== Lineage Report: {node_name} ==="]
        lines.append(f"Strategy: {node.strategy}  |  Fitness: {node.fitness():.4f}")
        lines.append(f"Seed ID: {node.seed_id}  |  Mutation: {node.mutation_id}")
        if node.lineage:
            marker = node.lineage[-1].lineage_marker
            lines.append(f"Lineage Marker: {marker}")
            # Contar quantos nós compartilham o mesmo marker
            same_family = sum(
                1 for n in self.graph.nodes.values()
                if n.lineage and n.lineage[-1].lineage_marker == marker
            )
            lines.append(f"Family size (same marker): {same_family}")
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
                    f"strategy={entry.strategy} | "
                    f"marker={entry.lineage_marker[:8]}..."
                )
        lines.append("")
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

