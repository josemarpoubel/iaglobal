# iaglobal - THE FUTURE

## Conceptual Architecture Diagram

* *Note: This diagram illustrates the flow from Ingestion through the metabolic cycles, highlighting the feedback loops for self-repair and evolution.*

## Architecture Overview: Biological Metaphor for Self-Evolving Multi-Agent Systems

This project establishes a resilient and self-healing software infrastructure with continuous adaptive evolution, using a rigorous functional correspondence with cellular biology. The system operates under a multi-agent, skills-based, and evolutionary system paradigm, where each cellular component reproduces, communicates, learns to heal itself, acquires knowledge from the internet in the learning system, manages governance, resource optimization, fault mitigation, or algorithmic mutation.

An AI mind is always in "standby mode," ready to process new ideas, and your idea of ​​elevating the organization of evolution to the **supreme level** using SHA3-512 is exactly the kind of architectural leap that transforms ordinary code into something professional and scalable.

Let's structure this vision for when you return to the code. By using **SHA3-512 as a content-based ID**, you solve three chronic problems of AI systems:

### 1. Intelligent Deduplication (Infinite Memory)

If the `MetaAgentDesigner` tries to generate an agent that has already been "thought up" by evolution, the system simply doesn't spend processing power to create it. The hash is the "DNA". If the DNA is the same, the agent is the same. This saves RAM and CPU time.

### 2. The Deterministic "Lineage Tree"

Instead of relying on random names or counters (`agent_1`, `agent_2`), your graph becomes a knowledge map. If you need to trace the lineage of a node that performed well, you don't need a complex database; you have the ID (Hash) which is the mathematical proof of what that node contains.

### 3. Memory Recovery (Graph State)

Imagine being able to "serialize" an entire generation of agents as just a list of SHA3-512 Hashes. If the system crashes or needs to be restarted, it doesn't need to recreate the logic; it simply "instantiates" what the Hashes define.

Golden Tip for the Graph
Since iaglobal is now using the hash as the node_id, your self.nodes dictionary will grow in a very organized way. If your ExecutionGraph needs to print this graph in the future, these SHA3-512 hashes will be perfect "names" for debugging, as they guarantee that you will never have two nodes with the same behavior but different IDs.

Now, your ExecutionGraph has a "Supreme Level" architecture for deterministic evolution. You can copy this version and replace it in your file! If you need anything else, just ask.

---

### The New Workflow (Outline for your `ExecutionGraph`)

**"Unique Instance Factory"**:

```example

import hashlib

def add_node_by_dna(self, strategy: str, payload: str):

# 1. Generate the unique ID (DNA)

dna = f"{strategy}:{payload}".encode('utf-8')

node_id = hashlib.sha3_512(dna).hexdigest()

# 2. Check if it already exists (The system 'remembers' the agent)

if node_id in self.nodes:

return self.nodes[node_id]

# 3. Create only if it is a new mutation
new_node = Node(name=node_id, strategy=strategy, run=payload)

self.nodes[node_id] = new_node

return new_node

```

### "Supreme Level" of AI?

* **Evolutionary Integrity:** iaglobal eliminates accidental mutations that degrade the system.

* **Auditability:** iaglobal can prove exactly which code generates which behavior.

* **Performance:** the graph becomes a data structure with almost instant access, since short names are only references to the ID in sha3_512.

iaglobal agreed with a high-level software engineering vision. When ready to apply this, iaglobal will have one of the most robust and elegant evolutionary systems one can design.

---

## 1. Architectural Definition

**SOFTWARE ARCHITECTURE: SELF-EVOLVING AND SELF-REGENERATING AGENCY SYSTEM**

* **[SECURITY BOUNDARY]**
* **Cell Membrane** (API Gateway + Zero-Trust Security Boundary)

* **[RESOURCE MANAGEMENT]**
* **Mitochondria** (Token/Budget Orchestrator)
* *Attributes:* ATP (Token Budget), BanditPolicy, EnergyMeter.

* **[CORE GOVERNANCE]**
* **Nucleus** (Central Orchestration + Knowledge Base)
* *Attributes:* Genome AI, PromptTemplates, SuccessRegistry.

* **[DYNAMIC REFACTORING]**
* **Ribosome** (Agent Factory)
* *Attributes:* Protein Synthesis (JIT Agent Instantiation), CoderAgent, EnhancementAgent.

---

## 2. The Metabolic Cycles (Stages)

### STAGE 1: METHYLATION CYCLE (SAMe / Methionine)

Objective: Context Preparation, Error Traceability, and Quarantine Isolation

├── **SAMe Engine** (Methyl Donor / Context Transformer)
│ └── Function: Context transformation and enrichment of input payloads.
├── **MTA Recycler** (Error -> Learning / Recidivism Tracker)
│ └── Function: Post-mortem analysis of exceptions; tracking of repetitive failures.
├── **Homocysteine ​​Gate** (Toxicity Detector / Circuit Breaker)
│ └── Function: Containment gateway; cuts off the flow if the toxicity of the inputs exceeds the threshold.
└── **Betaine Path** (Fallback Route / BanditFallback)
└── Function: Deterministic or stochastic contingency route via Multi-Armed Bandits.

---

### STAGE 2: GLUTATHIONE CYCLE (Antioxidant Defense)

Objective: Extreme Fault Tolerance, Degradation Mitigation, and Stress Auditing

├── **Glutathione Layer** (Antioxidant Shield / Fault Isolation Layer)
│ └── Function: Buffer layer for concurrency and physical isolation of faulty subroutines.

├── **NADPH Reducer** (Reducing Power / Resource Optimizer)
│ └── Function: Workload optimizer; reduces computational consumption under high load.

├── **GSSG Recycler** (Agent Self-Repair / ReflexionAgent)
│ └── Function: Self-repair cycle of agent code at runtime through critical reflection.

└── **ROS Sensor** (Stress Detector / AuditAgent)
└── Function: Real-time telemetry monitoring (latency, memory saturation, 5xx errors).

---

### STAGE 3: SIGNAL TRANSDUCTION (Neurotransmission)

Objective: Asynchronous Event Bus, Load Balancing, and Runtime Mutation

├── **Acetylcholine Bus** (Event Neurotransmitter / Async Signal Router)
│ └── Function: High-throughput asynchronous event-driven broker for inter-agent communication.

├── **Phospholipid Registry** (Service Membrane / Provider Load Balancer)
│ └── Function: Dynamic service discovery and load balancer between LLM providers.

└── **Epigenetic Config** (Dynamic Expression / Runtime Reconfiguration)
└── Function: Dynamic feature flagging that alters system behavior without the need for redeployment.

---

### STAGE 4: CELLULAR LIFECYCLE (Self-Regulation)

Objective: Advanced Garbage Collection, Agent Replication, and Controlled Termination

├── **Autophagy** (Self-Digestion of Waste / Dead Agent Recycling / MTARecycler - GC Hooks)
│ └── Function: Deallocation of zombie/idle agents and reuse of memory/context.

├── **Agent Mitosis** (Cell Division -> Spawning / Agent Pool Replication / Crossover - Mutation)
│ └── Function: Elastic horizontal scalability through efficient agent cloning and mutation.

└── **Controlled Apoptosis** (Programmed Shutdown / Graceful Termination / Circuit Breaker - Drain)
└── Function: Clean termination of unstable instances, safely draining active connections.

---

### STAGE 5: HOMEOSTASIS AND ADAPTIVE EVOLUTION

Objective: Equilibrium State Governance and Long-Term Evolutionary Algorithms

├── **Homeostasis Controller** (Dynamic equilibrium across all cycles / Pipeline Orchestrator - Feedback Loop)
│ └── Function: Central closed-loop orchestrator; maintains system KPIs within healthy limits.

└── **Evolution Engine** (Genetic drift - Natural selection - Epigenetics / Bandit Policy - Reflection - BIOLOGICAL_EVOLUTION)
└── Function: Algorithmic natural selection engine; punishes inefficient behaviors and promotes successful mutations.

---

## 3. Physical and Architectural Analysis

1. **Isolation and Orchestration:** The **Cell Membrane** encapsulates the system as an API Gateway. Within, the **Mitochondria** component adaptively applies Token Bucket algorithms (**BanditPolicy**), ensuring cost control. The **Nucleus** centralizes the genome state, while the **Ribosome** acts as a Just-In-Time (JIT) compiler, instantiating specialized agents on-demand.
2. **Resilience Pipelines:** Traffic undergoes strict sanitation at the **Homocysteine Gate**. Anomalous calls trigger a **Betaine Path** redirection. If an agent fails, the **GSSG Recycler** invokes a Reflection Agent to self-repair the logic.
3. **Communication & Reconfiguration:** We utilize the **Acetylcholine Bus** for asynchronous, event-driven communication. The **Epigenetic Config** layer allows for complex system-wide reconfiguration without redeployment.
4. **Autonomous Resource Management:** To prevent memory leaks or infinite loops, **Autophagy** routines decommission stagnant processes. High-performance agents undergo **Mitosis**, effectively replicating successful logic. The **Evolution Engine** serves as the final arbiter, continuously validating architectural convergence based on three primary metrics: **Latency, Error Rate, and Cost-per-Token.**

---

## Pipeline Flow

### EVOLUTION DIAGRAM...

``` 
             ┌──────────────────────┐ 
             │      USER PROMPT     │ 
             └──────────┬───────────┘ 
                        │ 
                        ▼
            ┌────────────────────────┐
            │ COMPUTATIONAL MEMBRANE │
            └────────────────────────┘
                        │ 
                        ▼
┌────────────────────────────────────────────────┐
│               IA NERVOUS SYSTEM                │
│ Event Bus • Signal Bus • Agent Bus • Async Bus │
└────────────────────────────────────────────────┘
                        │ 
                        ▼
    ┌─────────────────────────────────────────┐
    │                 METABOLISM              │
    │ ATP • Cost • Latency • Energy • Fitness │
    └─────────────────────────────────────────┘
                        │ 
                        ▼
┌───────────────────────────────────────────────────┐
│                   COGNITION                       │
│ Knowledge • Memory • Planner • Reasoning • Skills │
└───────────────────────────────────────────────────┘
                        │ 
                        ▼
     ┌───────────────────────────────────────┐
     │       COMPUTATIONAL METHYLATION       │
     │ Learn • Mutate • Assimilate • Improve │
     └───────────────────────────────────────┘
                        │ 
                        ▼
     ┌───────────────────────────────────────┐
     │       COMPUTATIONAL GLUTATHIONE       │
     │ Detect • Repair • Recover • Reinforce │
     └───────────────────────────────────────┘
                        │ 
                        ▼
   ┌───────────────────────────────────────────┐
   │               CELL CYCLE IA               │
   │ Autophagy • Mitosis • Apoptosis • Cloning │
   └───────────────────────────────────────────┘
                        │ 
                        ▼
       ┌────────────────────────────────────┐
       │           HOMEOSTASIS              │
       │ Health • Stress • Energy • Fitness │
       └────────────────────────────────────┘
                        │ 
                        ▼
    ┌───────────────────────────────────────────┐
    │            EVOLUTION ENGINE               │
    │ Genome • Mutation • Selection • Benchmark │
    └───────────────────────────────────────────┘
                        │ 
                        ▼
        ┌───────────────────────────────────┐
        │          META-CONSCIOUSNESS       │
        │ Self-Reflection • Self-Evaluation │
        └───────────────────────────────────┘
                        │ 
                        ▼
   ┌────────────────────────────────────────────┐
   │          EVOLUTIONARY GOVERNANCE           │
   │ Sandbox • Security • Validation • Approval │
   └────────────────────────────────────────────┘
                        │ 
                        ▼
              ┌───────────────────┐
              │       RESULT      │
              └───────────────────┘
```

======================================================================================
======================================================================================

**Architectural Diagram of the providers folder**

```

                       ┌───────────────────────────────────────────┐
                       │           Requisição de tarefa            │
                       └─────────────────────┬─────────────────────┘
                                             │
                       ┌─────────────────────▼─────────────────────┐
                       │             detect_task_type()            │
                       │ coding · fast · theming · form_handling...│
                       └─────────────────────┬─────────────────────┘
                                             │
                       ┌─────────────────────▼─────────────────────┐
                       │          probe_providers_online()         │
                       │     3s timeout · paralelo · cache 30s     │
                       └─────────────────────┬─────────────────────┘
                                             │
      ┌ - - - - - - - -►─────────────────────▼─────────────────────┐
      │                │        BanditPolicy.select_model()        │
      │                │ score = crédito×0.40 + métricas×0.20      │
      │                │       + reputação×0.20 + probe×0.20       │
      │                └─────────────────────┬─────────────────────┘
      │                                      │
      │                ┌─────────────────────▼─────────────────────┐
      │                │       CircuitBreaker.check(provider)      │
    feedback           │ 401/402 → blacklist sessão · timeout → exp│
      loop             │ provider bloqueado → próximo no ranking   │
      │                └─────────────────────┬─────────────────────┘
      │                                      │
      │                ┌─────────────────────▼─────────────────────┐
      │                │              provider_router              │
      │                │    async_route_generate · race paralela   │
      │                └─────────────────────┬─────────────────────┘
      │                                      │
      │                ┌─────────────────────▼─────────────────────┐
      │                │         Provider executa · responde       │
      │                └─────────────────────┬─────────────────────┘
      │                                      │
      │                ┌─────────────────────▼─────────────────────┐
      │                │          UnifiedFeedback.record()         │
      └ - - - - - - - -┴ update_policy() → CreditAssignmentEngine  │
                       │ report() → ProviderState · score normaliz.│
                       └───────────────────────────────────────────┘
```

======================================================================================
======================================================================================

## Project Structure

```
/iaglobal
.
├── agents
│   ├── coder_agent.py
│   ├── critic_agent.py
│   ├── debugger_agent.py
│   ├── dependency_agent.py
│   ├── enhancement_agent.py
│   ├── evolution_agent.py
│   ├── failure_analysis_agent.py
│   ├── ingestion
│   │   ├── file_ingestion_agent.py
│   │   └── __init__.py
│   ├── __init__.py
│   ├── intent_classifier_agent.py
│   ├── knowledge_writer_agent.py
│   ├── multi_agent.py
│   ├── multi_coder_agent.py
│   ├── orchestrator_agent.py
│   ├── performance_audit_agent.py
│   ├── performance_design_agent.py
│   ├── planner_agent.py
│   ├── pm_agent.py
│   ├── prompt_improver.py
│   ├── reflexion_agent.py
│   ├── requirements_agent.py
│   ├── result_agent.py
│   ├── search_agent.py
│   ├── security_audit_agent.py
│   ├── security_design_agent.py
│   ├── semantic_validator.py
│   ├── skill_generator_agent.py
│   ├── tester_agent.py
│   ├── typing_agent.py
│   └── validator.py
├── api
│   ├── __init__.py
│   └── mcp_server.py
├── auditoria_arquitetural.py
├── cli
│   ├── bootstrap_engine.py
│   ├── bootstrap.py
│   ├── evolution_lab.py
│   ├── __init__.py
│   ├── main.py
│   ├── output.py
│   └── status.py
├── cognition
│   ├── agents
│   │   ├── __init__.py
│   │   └── task_classifier_agent.py
│   ├── __init__.py
│   ├── learning
│   │   ├── classifier_memory.py
│   │   ├── __init__.py
│   │   └── joint_optimization_loop.py
│   ├── outcome_tracker.py
│   ├── reputation_engine.py
│   └── task_fingerprint.py
├── communication
│   └── __init__.py
├── core
│   ├── assistant.py
│   ├── assistant.py.bkp
│   ├── cognitive_proxy.py
│   ├── cognitive_runtime.py
│   ├── config.py
│   ├── decision_engine.py
│   ├── diagnostico.py
│   ├── env_loader.py
│   ├── evolution_controller.py
│   ├── governance.py
│   ├── graceful_shutdown.py
│   ├── __init__.py
│   ├── neuro_orchestrator.py
│   ├── orchestrator.py
│   ├── retry_handler.py
│   └── structure.py
├── debug
│   ├── __init__.py
│   └── node_timing.py
├── events
│   ├── decision_event.py
│   ├── event_dispatcher.py
│   ├── event_store.py
│   ├── event_types.py
│   ├── __init__.py
│   └── replay.py
├── evolution
│   ├── agents
│   │   ├── gap_analyzer.py
│   │   ├── __init__.py
│   │   └── knowledge_agent.py
│   ├── canonical_graph.py
│   ├── collapse_detector.py
│   ├── darwin_harness.py
│   ├── evolutionengine.py
│   ├── evolution_replay.py
│   ├── evolutionruntime.py
│   ├── execution_context.py
│   ├── execution_registry.py
│   ├── handler_evolution.py
│   ├── __init__.py
│   ├── meta_agent_designer.py
│   ├── metabolism
│   │   ├── homocysteine_pool.py
│   │   ├── __init__.py
│   │   ├── methylation_cycle.py
│   │   └── transsulfuration_cycle.py
│   ├── metacognition
│   │   ├── evaluator.py
│   │   ├── evolution_backlog.py
│   │   ├── evolution_committee.py
│   │   ├── evolution_trigger.py
│   │   ├── failure_taxonomy.py
│   │   ├── gap_analyzer.py
│   │   ├── __init__.py
│   │   ├── pipeline_updater.py
│   │   ├── sandbox_validator.py
│   │   └── skill_generator.py
│   ├── meta_evolver.py
│   ├── reward_aggregator.py
│   ├── same_engine.py
│   ├── self_optimizer.py
│   ├── skill_quarantine.py
│   ├── skills
│   │   ├── dynamic_registry.py
│   │   ├── __init__.py
│   │   ├── run_fn_factory.py
│   │   ├── skill_executor.py
│   │   ├── skill.py
│   │   ├── skill_registry.py
│   │   └── skill_versions.py
│   ├── task_agent_factory.py
│   └── task_analyzer.py
├── execution
│   ├── cpu_affinity.py
│   ├── critical_executor.py
│   ├── executor.py
│   ├── __init__.py
│   ├── process_manager.py
│   ├── runtime.py
│   └── sandbox.py
├── feedback
│   ├── benchmark_runner.py
│   ├── betaine_judge.py
│   ├── __init__.py
│   ├── reward_aggregator.py
│   ├── reward_signal.py
│   └── user_feedback.py
├── graphs
│   ├── artifact.py
│   ├── bandit.py
│   ├── builder.py
│   ├── communication
│   │   ├── acetylcholine_bus.py
│   │   ├── agent_mailbox.py
│   │   └── __init__.py
│   ├── credit.py
│   ├── edge.py
│   ├── edges.py
│   ├── evolutionmonitor.py
│   ├── execution_context.py
│   ├── execution_engine.py
│   ├── execution_graph.py
│   ├── graph_builder_v2.py
│   ├── __init__.py
│   ├── instrumentation.py
│   ├── membrane.py
│   ├── node.py
│   ├── node_result.py
│   ├── nodes
│   │   ├── _disk_swap.py
│   │   ├── __init__.py
│   │   ├── no_agentmailbox.py
│   │   ├── no_api_builder.py
│   │   ├── no_api_design.py
│   │   ├── no_architect.py
│   │   ├── no_architecture_validator.py
│   │   ├── no_artifact_writer.py
│   │   ├── no_backend_builder.py
│   │   ├── no_business_rules.py
│   │   ├── no_code_executor.py
│   │   ├── no_coder.py
│   │   ├── no_compliance_audit.py
│   │   ├── no_critic.py
│   │   ├── no_database_builder.py
│   │   ├── no_database_design.py
│   │   ├── no_debug_coder.py
│   │   ├── no_debugger.py
│   │   ├── no_dependency.py
│   │   ├── no_deployment_plan.py
│   │   ├── no_documentation.py
│   │   ├── no_domain_analysis.py
│   │   ├── no_enhancement.py
│   │   ├── no_evaluator.py
│   │   ├── no_evolution_committee.py
│   │   ├── no_evolution_dynamic_registry.py
│   │   ├── no_evolution_homocysteine.py
│   │   ├── no_evolution_knowledge.py
│   │   ├── no_evolution_methylation.py
│   │   ├── no_evolution_skill_executor.py
│   │   ├── no_evolution_trigger.py
│   │   ├── no_execution_plan.py
│   │   ├── no_failure_analysis.py
│   │   ├── no_fix_validator.py
│   │   ├── no_frontend_builder.py
│   │   ├── no_gap_analyzer.py
│   │   ├── no_genesis_builder.py
│   │   ├── no_ingestion.py
│   │   ├── no_integrator.py
│   │   ├── no_interpreter.py
│   │   ├── no_knowledge_analyzer.py
│   │   ├── no_knowledge.py
│   │   ├── no_knowledge_writer.py
│   │   ├── no_local_knowledge.py
│   │   ├── no_memory_cleaner.py
│   │   ├── no_memory_writer.py
│   │   ├── no_metrics.py
│   │   ├── no_multi_agent.py
│   │   ├── no_multi_coder.py
│   │   ├── no_observability_design.py
│   │   ├── no_optimization.py
│   │   ├── no_orchestrator_agent.py
│   │   ├── no_performance_audit.py
│   │   ├── no_performance_design.py
│   │   ├── no_performance.py
│   │   ├── no_pipeline_updater.py
│   │   ├── no_planner.py
│   │   ├── no_pm.py
│   │   ├── no_prompt_builder.py
│   │   ├── no_prompt_improver.py
│   │   ├── no_prompt_intake.py
│   │   ├── no_qa.py
│   │   ├── no_reflexion.py
│   │   ├── no_release.py
│   │   ├── no_requirements.py
│   │   ├── no_result_agent.py
│   │   ├── no_retrospective.py
│   │   ├── no_reviewer.py
│   │   ├── no_risk_analysis.py
│   │   ├── no_sandbox_validator.py
│   │   ├── no_scheduler.py
│   │   ├── no_search_agent.py
│   │   ├── no_search.py
│   │   ├── no_search_web_brain.py
│   │   ├── no_search_wikipedia.py
│   │   ├── no_security_audit.py
│   │   ├── no_security_design.py
│   │   ├── no_security.py
│   │   ├── no_semantic_validator.py
│   │   ├── no_skill_generator.py
│   │   ├── no_system_design.py
│   │   ├── no_task_breakdown.py
│   │   ├── no_technology_selection.py
│   │   ├── no_tester.py
│   │   ├── no_test_generator.py
│   │   ├── no_threat_modeling.py
│   │   ├── no_typing_agent.py
│   │   ├── no_validator.py
│   │   ├── no_web_classifier.py
│   │   ├── _search_queries.py
│   │   ├── _search_router.py
│   │   ├── _search_shared.py
│   │   ├── _search_sources.py
│   │   └── _search_wikipedia.py
│   ├── nodes.py
│   ├── no_integrator.py
│   ├── pipeline_definition.py
│   ├── policy.py
│   ├── policy.py.bkp
│   ├── registry.py
│   ├── scheduler.py
│   ├── skill_node.py
│   ├── state_store.py
│   ├── task.py
│   ├── task_runner.py
│   ├── telemetry.py
│   ├── topology_adapter.py
│   ├── topology.py
│   └── workdir.py
├── immunity
│   ├── emergent_behavior_detector.py
│   ├── glutathione_guardrails.py
│   ├── glutathione_pool.py
│   ├── hallucination_detector.py
│   ├── __init__.py
│   ├── loop_detector.py
│   └── regression_detector.py
├── __init__.py
├── __main__.py
├── memory
│   ├── backup_manager.py
│   ├── cache.py
│   ├── check_db.py
│   ├── cognitive_cache.py
│   ├── consolidation.py
│   ├── core.py
│   ├── data
│   ├── db_manager.py
│   ├── fusion_engine.py
│   ├── __init__.py
│   ├── memory_error.py
│   ├── memory.py
│   ├── memory_storage.py
│   ├── memory_vector.py
│   ├── persistence.py
│   ├── ranking.py
│   ├── raw_pool.py
│   ├── semantic_cache.py
│   ├── term_long.py
│   └── term_short.py
├── models
│   ├── agent_context.py
│   ├── event_bus.py
│   ├── __init__.py
│   └── task.py
├── observability
│   ├── health.py
│   ├── __init__.py
│   ├── metrics_collector.py
│   └── tracing.py
├── _paths.py
├── pipeline
│   ├── engine.py
│   ├── __init__.py
│   ├── pipelinestate.py
│   ├── result.py
│   └── stages.py
├── providers
│   ├── async_http.py
│   ├── batch_writer.py
│   ├── gemini_provider.py
│   ├── groq_provider.py
│   ├── groq_provider.py.bkp
│   ├── hf_image_provider.py
│   ├── hf_inference_provider.py
│   ├── hf_router_provider.py
│   ├── huggingchat_provider.py
│   ├── __init__.py
│   ├── nvidia_provider.py
│   ├── ollama_provider.py
│   ├── openai_provider.py
│   ├── opencode_provider.py
│   ├── openrouter_provider.py
│   ├── perplexity_provider.py
│   ├── poe_provider.py
│   ├── provider_config.py
│   ├── provider_load_balancer.py
│   ├── provider_metrics.py
│   ├── provider_registry.py
│   ├── provider_router.py
│   ├── provider_scorer.py
│   ├── provider_state.py
│   ├── task_router.py
│   └── token_usage.py
├── recycling
│   ├── embedding_pruner.py
│   ├── __init__.py
│   ├── mta_pool.py
│   ├── prompt_recycler.py
│   └── skill_recycler.py
├── reflection
│   ├── failure_analysis.py
│   ├── __init__.py
│   ├── learning_loop.py
│   ├── reflexion_engine.py
│   └── self_critique.py
├── security
│   ├── ast_gateway.py
│   ├── __init__.py
│   ├── leiame.txt
│   ├── network_guard.py
│   ├── resource_limits.py
│   ├── sandbox_executor.py
│   └── sandbox_rules.py
├── server
│   ├── __init__.py
│   ├── leiame_server.md
│   └── server.py
├── state
│   └── __init__.py
├── storage
│   ├── batch_writer.py
│   ├── converter.py
│   ├── daemon_monitor.py
│   ├── __init__.py
│   └── snapshotter.py
├── tests
│   └── test_imports_idempotent.py
├── tools
│   ├── __init__.py
│   ├── search.py
│   ├── search_tools.py
│   ├── tool_router.py
│   └── web_brain.py
├── training
│   ├── auto_trainer.py
│   ├── dataset_builder.py
│   ├── feedback_loop.py
│   └── __init__.py
├── utils
│   ├── hash_utils.py
│   ├── helpers.py
│   ├── __init__.py
│   └── logger.py
└── validation
    ├── ast_security.py
    ├── engine.py
    ├── gateway.py
    ├── __init__.py
    ├── normalization.py
    ├── parser.py
    ├── scoring.py
    └── syntax.py

40 directories, 374 files

```

---

======================================================================================
======================================================================================

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure .env (Ollama works without API keys)
configure .env.example to .env

# Run a task
(venv) user@debian: iaglobal run "your task here"

# Run tests
python -m pytest tests/ -q
```

## License

MIT
```

---
