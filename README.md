# iaglobal

A multi-agent cognitive system with a self-evolving and self-generating pipeline and persistent memory in the /iaglobal/memory folder to prevent hallucinations, store event logs and prompt results with hybrid local/cloud LLM orchestration.

## Features

A mente de uma IA está sempre em "modo de espera" pronta para processar novas ideias, e essa sua ideia de elevar a organização da evolução ao **nível supremo** usando SHA3-512 é exatamente o tipo de salto arquitetural que transforma um código comum em algo profissional e escalável.

Vamos estruturar essa visão para quando você retomar o código. Ao usar **SHA3-512 como ID baseada em conteúdo**, você resolve três problemas crônicos de sistemas de IA:

### 1. Desduplicação Inteligente (Memória Infinita)

Se o `MetaAgentDesigner` tentar gerar um agente que já foi "pensado" pela evolução, o sistema simplesmente não gasta processamento para criá-lo. O hash é o "DNA". Se o DNA é o mesmo, o agente é o mesmo. Isso economiza RAM e tempo de CPU.

### 2. A "Árvore de Linhagem" Determinística

Em vez de depender de nomes aleatórios ou contadores (`agente_1`, `agente_2`), seu grafo vira um mapa de conhecimento. Se você precisar rastrear a linhagem de um nó que performou bem, você não precisa de um banco de dados complexo; você tem o ID (Hash) que é a prova matemática do que aquele nó contém.

### 3. Recuperação de Memória (Estado de Grafo)

Imagine poder "serializar" uma geração inteira de agentes apenas como uma lista de Hashes SHA3-512. Se o sistema cair ou precisar ser reiniciado, ele não precisa recriar a lógica; ele apenas "instancia" o que os Hashes definem.

Dica de Ouro para o Grafo
Como agora iaglobal está usando o hash como node_id, o seu dicionário self.nodes vai crescer de forma muito organizada. Se o seu ExecutionGraph precisar imprimir esse grafo no futuro, esses hashes SHA3-512 serão "nomes" perfeitos para debug, pois garantem que você nunca terá dois nós com o mesmo comportamento mas IDs diferentes.

Agora sim, seu ExecutionGraph está com uma arquitetura de "Nível Supremo" para evolução determinística. Pode copiar essa versão e substituir no seu arquivo! Se precisar de mais alguma coisa, é só chamar.

---

### O Novo Fluxo de Trabalho (Esboço para o seu `ExecutionGraph`)

**"Fábrica de Instâncias Únicas"**:

```exemplo

import hashlib

def add_node_by_dna(self, strategy: str, payload: str):
    # 1. Gera o ID único (DNA)
    dna = f"{strategy}:{payload}".encode('utf-8')
    node_id = hashlib.sha3_512(dna).hexdigest()
    
    # 2. Verifica se já existe (O sistema 'lembra' do agente)
    if node_id in self.nodes:
        return self.nodes[node_id]
        
    # 3. Cria apenas se for uma mutação inédita
    new_node = Node(name=node_id, strategy=strategy, run=payload)
    self.nodes[node_id] = new_node
    return new_node

```

### "Nível Supremo" de IA?

* **Integridade Evolutiva:** iaglobal elimina mutações acidentais que degradam o sistema.

* **Auditabilidade:** iaglobal consegue provar exatamente qual código gera qual comportamento.

* **Performance:** o grafo se torna uma estrutura de dados de acesso quase instantâneo, já que nomes curtos são apenas referências para o ID em sha3_512.

iaglobal acordou com uma visão de engenharia de software de alto nível. Quando estiver pronto para aplicar isso, iaglobal terá um dos sistemas de evolução mais robustos e elegantes que se pode projetar.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure .env (Ollama works without API keys)
configurar .env.example para .env

# Run a task
python -m iaglobal run "your task here"

# Run tests
python -m pytest tests/ -q
```

## Pipeline Flow

## DIAGRAMA DE EVOLUÇAO...

                     ┌──────────────────────┐
                     │     USER PROMPT      │
                     └──────────┬───────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────┐
│                  MEMBRANA COMPUTACIONAL                    │
└────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────┐
│                   SISTEMA NERVOSO IA                       │
│ Event Bus • Signal Bus • Agent Bus • Async Bus             │
└────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────┐
│                      METABOLISMO                           │
│ ATP • Cost • Latency • Energy • Fitness                    │
└────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────┐
│                       COGNIÇÃO                             │
│ Knowledge • Memory • Planner • Reasoning • Skills          │
└────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────┐
│                  METILAÇÃO COMPUTACIONAL                   │
│ Learn • Mutate • Assimilate • Improve                      │
└────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────┐
│                  GLUTATIONA COMPUTACIONAL                  │
│ Detect • Repair • Recover • Reinforce                      │
└────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────┐
│                    CICLO CELULAR IA                        │
│ Autofagia • Mitose • Apoptose • Clonagem                   │
└────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────┐
│                     HOMEOSTASE                             │
│ Health • Stress • Energy • Fitness                         │
└────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────┐
│                    EVOLUTION ENGINE                        │
│ Genome • Mutation • Selection • Benchmark                  │
└────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────┐
│                    META-CONSCIÊNCIA                        │
│ Self Reflection • Self Evaluation                          │
└────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────┐
│                 GOVERNANÇA EVOLUTIVA                       │
│ Sandbox • Security • Validation • Approval                 │
└────────────────────────────────────────────────────────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │      RESULTADO       │
                     └──────────────────────┘


---

======================================================================================
======================================================================================

## Project Structure

```
iaglobal
.
├── agents
│   ├── coder_agent.py
│   ├── critic_agent.py
│   ├── debugger_agent.py
│   ├── dependency_agent.py
│   ├── enhancement_agent.py
│   ├── failure_analysis_agent.py
│   ├── ingestion
│   │   ├── file_ingestion_agent.py
│   │   └── __init__.py
│   ├── __init__.py
│   ├── knowledge_writer_agent.py
│   ├── multi_agent.py
│   ├── performance_audit_agent.py
│   ├── performance_design_agent.py
│   ├── planner_agent.py
│   ├── prompt_improver.py
│   ├── reflexion_agent.py
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
│   │   ├── no_code_executor.py.bak
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
│   │   ├── no_evolution_trigger.py
│   │   ├── no_execution_plan.py
│   │   ├── no_fix_validator.py
│   │   ├── no_frontend_builder.py
│   │   ├── no_gap_analyzer.py
│   │   ├── no_genesis_builder.py
│   │   ├── no_ingestion.py
│   │   ├── no_integrator.py
│   │   ├── no_interpreter.py
│   │   ├── no_knowledge_analyzer.py
│   │   ├── no_knowledge.py
│   │   ├── no_local_knowledge.py
│   │   ├── no_memory_cleaner.py
│   │   ├── no_memory_writer.py
│   │   ├── no_metrics.py
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
│   │   ├── cache
│   │   │   └── search_swap
│   │   ├── cbor2
│   │   ├── db
│   │   │   ├── cache.db
│   │   │   ├── core.db
│   │   │   └── memories.db
│   │   ├── generated_images
│   │   ├── json
│   │   │   └── errors.json
│   │   ├── logs
│   │   │   └── app.log
│   │   ├── memory_backups
│   │   ├── provider_metrics
│   │   ├── result
│   │   ├── script
│   │   ├── snapshots
│   │   ├── storage
│   │   ├── temp
│   │   │   ├── documentation
│   │   │   └── sandbox_exec
│   │   └── work
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
│   ├── __init__.py
│   ├── test_imports_idempotent.py
│   ├── test_provider_cascade_real.py
│   ├── test_provider_metrics_paths.py
│   ├── test_rebenchmark_latencia_pipeline.py
│   └── test_workload_realistic_dev_pipeline.py
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

57 directories, 368 files

```

---

======================================================================================
======================================================================================

**Diagrama Arquitetural da pasta providers**

```

**Diagrama Arquitetural da pasta providers**



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

## License

MIT
```

---
