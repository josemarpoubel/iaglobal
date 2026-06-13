# iaglobal/evolution/evolutionengine.py

import copy
import hashlib
import secrets
import logging
import time
import asyncio
from typing import Dict, Optional, List, Tuple

from iaglobal.graphs.node import Node, LineageEntry
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
from iaglobal.evolution.execution_context import ExecutionContext
from iaglobal.events import dispatcher
from iaglobal.utils.hash_utils import LineageID

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

    # --------------------------------------------------
    # SYNC WRAPPERS (called via asyncio.to_thread from evolve_async)
    # --------------------------------------------------

    def _run_evolution_step(self, step_fn):
        """Executa um passo evolutivo (wrapper para compatibilidade)."""
        result = step_fn()
        if result is not None:
            import asyncio
            if asyncio.iscoroutine(result):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(result)
                finally:
                    loop.close()

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
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.seed_evo_population_async())
        finally:
            loop.close()

    def _mutate_nodes(self):
        """Sync wrapper para mutate_nodes_async."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.mutate_nodes_async())
        finally:
            loop.close()

    def _crossover_phase(self):
        """Sync wrapper para _crossover_phase_async."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._crossover_phase_async())
        finally:
            loop.close()

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

    async def evolve_async(self):
        """Versão assíncrona do ciclo evolutivo."""
        logger.info("🧬 [ASYNC] Iniciando ciclo de evolução: gen=%d", self.generation)
        
        # 1. Canonicalização (CPU Bound - roda em thread para não travar o loop)
        await asyncio.to_thread(self._run_evolution_step, self._perform_canonicalize)
        
        # 2. Seed e População (I/O + CPU)
        await asyncio.to_thread(self._seed_evo_population)
        await asyncio.to_thread(self._create_task_agents)
        
        # 3. Seleção, Mutação e Crossover
        # Essas fases de IA devem rodar isoladas do loop principal
        await asyncio.to_thread(self._select_survivors)
        await asyncio.to_thread(self._mutate_nodes)
        await asyncio.to_thread(self._crossover_phase)
        
        # 4. Finalização
        await asyncio.to_thread(self._finalize_evolution_step)
        
        logger.info("✅ [ASYNC] Ciclo evolutivo concluído com sucesso.")

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
            await asyncio.to_thread(self._initialize_seed_workdir, seed_name, skill_name)
            
            seeds[seed_name] = seed

        # 3. Atualiza o grafo de forma atômica
        if seeds:
            self.graph.nodes.update(seeds)
            logger.info("🌱 %d novo(s) agente(s) adicionados ao grafo.", len(seeds))
        else:
            await asyncio.to_thread(self._create_synthetic_evo_seeds)

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

    async     def _create_synthetic_evo_seeds(self):
        """Sync wrapper para _create_synthetic_evo_seeds_async."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._create_synthetic_evo_seeds_async())
        finally:
            loop.close()

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
        return self.graph.core_nodes_registry

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

    def _select_survivors(self):
        """
        Seleção por Truncamento (50% de taxa de sobrevivência).
        """
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
        # DICA: Se node.fitness() for caro, cacheie o valor antes em um dict: {n.name: n.fitness()}
        evo_sorted = sorted(evo_nodes, key=lambda n: n.fitness(), reverse=True)
        
        # Seleção
        cutoff = max(1, len(evo_sorted) // 2)
        survivors = evo_sorted[:cutoff]
        eliminated = evo_sorted[cutoff:]

        logger.info("🧬 Seleção: %d candidatos | %d sobreviventes | %d eliminados.",
                    len(evo_nodes), len(survivors), len(eliminated))

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
            new_node, stats = await asyncio.to_thread(self._mutate_node, node)
            
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

        # 2. Model Drift
        if secrets.randbelow(1000000) < int(base_rate * 1000000):
            from iaglobal.providers.provider_config import ProviderConfig
            new_node.model_hint = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
            stats["model_drifted"] = True

        return new_node, stats

    async def _crossover_phase_async(self):
        """Versão assíncrona do Crossover."""
        evo_nodes = [node for node in self.graph.nodes.values() if node.name not in self.CORE_NODE_NAMES]
        logger.info("🧬 Iniciando fase de Crossover para %d agentes...", len(evo_nodes))

        # Gerar híbridos em paralelo (CPU-bound via threadpool)
        tasks = []
        for i in range(len(evo_nodes)):
            if len(tasks) >= MAX_HYBRIDS_PER_GENERATION:
                break
            for j in range(i + 1, len(evo_nodes)):
                if len(evo_nodes) > 2 and secrets.randbelow(100) > 30:
                    continue
                # Delegamos a criação pesada para threads
                tasks.append(asyncio.to_thread(self._crossover, evo_nodes[i], evo_nodes[j]))
        
        results = await asyncio.gather(*tasks)
        
        # Atualização atômica do Grafo
        new_nodes = {child.name: child for child, stats in results if child.name not in self.graph.nodes}
        self.graph.nodes.update(new_nodes)
        
        if new_nodes:
            logger.info("🧬 %d híbrido(s) adicionado(s)!", len(new_nodes))

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

