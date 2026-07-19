iaglobal$ tree
.
├── agents
│   ├── agent_base.py
│   ├── coder_agent.py
│   ├── critic_agent.py
│   ├── debugger_agent.py
│   ├── dependency_agent.py
│   ├── enhancement_agent.py
│   ├── evolution_agent.py
│   ├── failure_analysis_agent.py
│   ├── ingestion
│   │   ├── consolidation.py
│   │   ├── experiment_runner.py
│   │   ├── file_ingestion_agent.py
│   │   ├── hypothesis_generator.py
│   │   ├── __init__.py
│   │   ├── meta_learner.py
│   │   ├── paper_ingestor.py
│   │   └── paper_parser.py
│   ├── __init__.py
│   ├── intent_classifier_agent.py
│   ├── knowledge_writer_agent.py
│   ├── mitosis_engine.py
│   ├── multi_agent.py
│   ├── multi_coder_agent.py
│   ├── orchestrator_agent.py
│   ├── performance_audit_agent.py
│   ├── performance_design_agent.py
│   ├── planner_agent.py
│   ├── pm_agent.py
│   ├── prompt_improver.py
│   ├── reflexion_agent.py
│   ├── requirements_agent.py
│   ├── result_agent.py
│   ├── search_agent.py
│   ├── security_audit_agent.py
│   ├── security_design_agent.py
│   ├── semantic_validator.py
│   ├── tester_agent.py
│   ├── tool_caller_agent.py
│   ├── typing_agent.py
│   └── validator.py
├── api
│   ├── __init__.py
│   └── mcp_server.py
├── artifacts
│   ├── artifact_factory.py
│   └── __init__.py
├── chappie
│   ├── bandit_evolution.py
│   ├── error_enricher.py
│   ├── __init__.py
│   ├── ivm_axiom.py
│   ├── ivm_compliance.py
│   ├── lineage_guardian.py
│   └── vacuum_daemon.py
├── cli
│   ├── bootstrap_engine.py
│   ├── bootstrap.py
│   ├── evolution_lab.py
│   ├── __init__.py
│   ├── learn.py
│   ├── life_signals.py
│   ├── __main__.py
│   ├── main.py
│   ├── output.py
│   ├── status.py
│   └── ui_cli.py
├── cognition
│   ├── adaptive_router.py
│   ├── agents
│   │   ├── __init__.py
│   │   └── task_classifier_agent.py
│   ├── __init__.py
│   ├── learning
│   │   ├── classifier_memory.py
│   │   └── __init__.py
│   ├── memory_first_router.py
│   ├── outcome_tracker.py
│   ├── reputation_engine.py
│   └── task_fingerprint.py
├── colony_comms
│   ├── fitness.py
│   ├── genesis_handshake.py
│   ├── __init__.py
│   ├── integrator.py
│   ├── queen.py
│   └── worker.py
├── core
│   ├── acetylcholine_bus.py
│   ├── apoptosis.py
│   ├── assistant.py
│   ├── auto_correction.py
│   ├── code_assembler.py
│   ├── cognitive_proxy.py
│   ├── cognitive_runtime.py
│   ├── config.py
│   ├── critic_batch_queue.py
│   ├── decision_engine.py
│   ├── dependency_enforcer.py
│   ├── diagnostico.py
│   ├── env_loader.py
│   ├── evolution_controller.py
│   ├── few_shot_provider.py
│   ├── governance.py
│   ├── graceful_shutdown.py
│   ├── __init__.py
│   ├── law_enforcement.py
│   ├── mitochondrial_probe.py
│   ├── neuro_orchestrator.py
│   ├── orchestrator.py
│   ├── organism_main.py
│   ├── organism.py
│   ├── registry.py
│   ├── retry_handler.py
│   └── structure.py
├── dashboard
│   ├── __init__.py
│   ├── metabolic_sleep_dashboard.py
│   └── phospholipid_dashboard.py
├── debug
│   ├── __init__.py
│   └── node_timing.py
├── events
│   ├── acetylcholine_bus.py
│   ├── decision_event.py
│   ├── event_dispatcher.py
│   ├── event_store.py
│   ├── event_types.py
│   ├── __init__.py
│   └── replay.py
├── evolution
│   ├── agents
│   │   ├── gap_analyzer.py
│   │   ├── __init__.py
│   │   └── knowledge_agent.py
│   ├── canonical_graph.py
│   ├── collapse_detector.py
│   ├── darwin_harness.py
│   ├── epigenetic.py
│   ├── evo_agent.py
│   ├── evolutionengine.py
│   ├── evolution_replay.py
│   ├── evolutionruntime.py
│   ├── execution_context.py
│   ├── execution_registry.py
│   ├── fusion_engine.py
│   ├── ga
│   │   ├── ga_runner.py
│   │   ├── __init__.py
│   │   ├── population.py
│   │   └── selector.py
│   ├── ga_router_optimizer.py
│   ├── genomic_reflection.py
│   ├── handler_evolution.py
│   ├── homeostasis_controller.py
│   ├── __init__.py
│   ├── memory_apoptosis.py
│   ├── meta_agent_designer.py
│   ├── metabolic_lifecycle.py
│   ├── metabolic_rhythm.py
│   ├── metacognition
│   │   ├── evaluator.py
│   │   ├── evolution_backlog.py
│   │   ├── evolution_committee.py
│   │   ├── evolution_trigger.py
│   │   ├── failure_taxonomy.py
│   │   ├── gap_analyzer.py
│   │   ├── __init__.py
│   │   ├── pipeline_updater.py
│   │   └── sandbox_validator.py
│   ├── meta_evolver.py
│   ├── proposal_quarantine.py
│   ├── reward_aggregator.py
│   ├── same_engine.py
│   ├── self_optimizer.py
│   ├── skills
│   │   ├── __init__.py
│   │   ├── native
│   │   │   ├── reactpy_skill_registry.py
│   │   │   ├── README_SKILL_MODEL_ROUTER.md
│   │   │   ├── skill_debug_unificado.py
│   │   │   ├── skill_executor.py
│   │   │   ├── skill_generator_agent.py
│   │   │   ├── skill_generator.py
│   │   │   ├── skill_model_router.py
│   │   │   ├── skill_prompt_structurer.py
│   │   │   ├── skill.py
│   │   │   ├── skill_python_autocomplete.py
│   │   │   ├── skill_rag_optimizer.py
│   │   │   ├── skill_registry.py
│   │   │   └── skill_versions.py
│   │   ├── README.md
│   │   ├── templates
│   │   │   ├── api_builder.txt
│   │   │   ├── api_design.txt
│   │   │   ├── architect.txt
│   │   │   ├── backend_builder.txt
│   │   │   ├── business_rules.txt
│   │   │   ├── coder.txt
│   │   │   ├── critic.txt
│   │   │   ├── database_design.txt
│   │   │   ├── documentation.txt
│   │   │   ├── domain_analysis.txt
│   │   │   ├── frontend_builder.txt
│   │   │   ├── integrator.txt
│   │   │   ├── performance_audit.txt
│   │   │   ├── planner.txt
│   │   │   ├── README.md
│   │   │   ├── requirements.txt
│   │   │   ├── security_audit.txt
│   │   │   ├── skill_debug_unificado.txt
│   │   │   ├── skill_executor.txt
│   │   │   ├── skill_generator.txt
│   │   │   ├── skill_prompt_structurer.txt
│   │   │   ├── skill_python_autocomplete.txt
│   │   │   ├── system_design.txt
│   │   │   ├── technology_selection.txt
│   │   │   └── test_generator.txt
│   │   └── utils
│   │       ├── dynamic_registry.py
│   │       ├── __init__.py
│   │       ├── run_fn_factory.py
│   │       ├── skill_quarantine.py
│   │       ├── skill_recycler.py
│   │       └── template_loader.py
│   ├── task_agent_factory.py
│   ├── task_analyzer.py
│   └── watchdog.py
├── exceptions.py
├── execution
│   ├── cpu_affinity.py
│   ├── executor.py
│   ├── __init__.py
│   ├── sandbox.py
│   └── token_bucket.py
├── feedback
│   ├── benchmark_runner.py
│   ├── betaine_judge.py
│   ├── __init__.py
│   ├── reward_aggregator.py
│   ├── reward_signal.py
│   └── user_feedback.py
├── genesis
│   ├── certify_block.py
│   ├── check_cbor.py
│   ├── data
│   │   ├── check_genesis_integrity.py
│   │   ├── integrity_tree.cbor
│   │   ├── webhidden_genesis_blueprint.cbor
│   │   └── webhidden_genesis_evolutive.cbor
│   ├── fusion_engine.py
│   ├── genesis_purifier.py
│   ├── genesis_verifier.py
│   ├── identity.py
│   ├── __init__.py
│   ├── lineage_gate.py
│   ├── tribunal.py
│   └── verifygenesis.py
├── graphs
│   ├── artifact.py
│   ├── bandit.py
│   ├── builder.py
│   ├── comms
│   │   ├── acetylcholine_bus.py
│   │   ├── agent_mailbox.py
│   │   ├── __init__.py
│   │   └── membrane_key.py
│   ├── credit.py
│   ├── edge.py
│   ├── edges.py
│   ├── execution_context.py
│   ├── execution_engine.py
│   ├── execution_graph.py
│   ├── graph_builder_v2.py
│   ├── __init__.py
│   ├── instrumentation.py
│   ├── membrane.py
│   ├── migrar_nodes.py
│   ├── node_lineage_registry.py
│   ├── node.py
│   ├── nodes
│   │   ├── _disk_swap.py
│   │   ├── __init__.py
│   │   ├── js_syntax_sentinel.py
│   │   ├── no_adaptive_router.py
│   │   ├── no_agentmailbox.py
│   │   ├── no_ai_audit_compliance.py
│   │   ├── no_api_builder.py
│   │   ├── no_api_design.py
│   │   ├── no_apoptosis_kill.py
│   │   ├── no_applied_ai_engineer.py
│   │   ├── no_architect.py
│   │   ├── no_architecture_validator.py
│   │   ├── no_artifact_writer.py
│   │   ├── no_async_violation_detector.py
│   │   ├── no_auditor_sentinel.py
│   │   ├── no_backend_builder.py
│   │   ├── no_business_rules.py
│   │   ├── no_chappie_bandit_evolution.py
│   │   ├── no_clarity_directive.py
│   │   ├── no_code_executor.py
│   │   ├── no_coder.py
│   │   ├── no_compliance_audit.py
│   │   ├── no_context_weaver.py
│   │   ├── no_critic.py
│   │   ├── no_darwin_harness.py
│   │   ├── no_database_builder.py
│   │   ├── no_database_design.py
│   │   ├── no_debug_coder.py
│   │   ├── no_debugger.py
│   │   ├── no_debug_unificado.py
│   │   ├── no_dependency.py
│   │   ├── no_deployment_plan.py
│   │   ├── no_documentation.py
│   │   ├── no_domain_analysis.py
│   │   ├── no_enhancement.py
│   │   ├── no_entropy_sentinel.py
│   │   ├── no_evaluator.py
│   │   ├── no_evolution_committee.py
│   │   ├── no_evolution_dynamic_registry.py
│   │   ├── no_evolution_homocysteine.py
│   │   ├── no_evolution_knowledge.py
│   │   ├── no_evolution_methylation.py
│   │   ├── no_evolution_skill_executor.py
│   │   ├── no_evolution_trigger.py
│   │   ├── no_execution_plan.py
│   │   ├── no_failure_analysis.py
│   │   ├── no_fix_validator.py
│   │   ├── no_frontend_builder.py
│   │   ├── no_fugue_compartment.py
│   │   ├── no_fusion.py
│   │   ├── no_gap_analyzer.py
│   │   ├── no_ga_router_evolve.py
│   │   ├── no_genesis_builder.py
│   │   ├── no_immune_check_build.py
│   │   ├── no_immune_check.py
│   │   ├── no_immune_exchange.py
│   │   ├── no_immune_monitor.py
│   │   ├── no_ingestion.py
│   │   ├── no_integrator.py
│   │   ├── no_integrator.py.backup.before_fix
│   │   ├── no_interpreter.py
│   │   ├── no_knowledge_analyzer.py
│   │   ├── no_knowledge.py
│   │   ├── no_knowledge_writer.py
│   │   ├── no_law_of_thought_enforcer.py
│   │   ├── no_lineage_proof.py
│   │   ├── no_local_knowledge.py
│   │   ├── no_lsp_validator.py
│   │   ├── no_memory_cleaner.py
│   │   ├── no_memory_writer.py
│   │   ├── no_metabolic_pruning.py
│   │   ├── no_meta_director.py
│   │   ├── no_metrics.py
│   │   ├── no_mini_evaluator_post_arch.py
│   │   ├── no_mini_evaluator_post_build.py
│   │   ├── no_multi_agent.py
│   │   ├── no_multi_coder.py
│   │   ├── no_observability_design.py
│   │   ├── no_optimization.py
│   │   ├── no_orchestrator_agent.py
│   │   ├── no_orchestrator_pump.py
│   │   ├── no_performance_audit.py
│   │   ├── no_performance_design.py
│   │   ├── no_performance.py
│   │   ├── no_pipeline_updater.py
│   │   ├── no_pip_install.py
│   │   ├── no_planner.py
│   │   ├── no_pm.py
│   │   ├── no_prompt_builder.py
│   │   ├── no_prompt_improver.py
│   │   ├── no_prompt_intake.py
│   │   ├── no_proposal_quarantine.py
│   │   ├── no_qa.py
│   │   ├── no_reactpy.py
│   │   ├── no_reflexion.py
│   │   ├── no_release.py
│   │   ├── no_requirements.py
│   │   ├── no_result_agent.py
│   │   ├── no_retrospective.py
│   │   ├── no_reviewer.py
│   │   ├── no_risk_analysis.py
│   │   ├── no_sandbox_validator.py
│   │   ├── no_scheduler.py
│   │   ├── no_search_agent.py
│   │   ├── no_search.py
│   │   ├── no_search_web_brain.py
│   │   ├── no_search_wikipedia.py
│   │   ├── no_security_audit.py
│   │   ├── no_security_design.py
│   │   ├── no_security.py
│   │   ├── no_semantic_validator.py
│   │   ├── no_skill_generator.py
│   │   ├── no_success_ritual.py
│   │   ├── no_symbiont_handshake.py
│   │   ├── no_system_analysis.py
│   │   ├── no_system_design.py
│   │   ├── no_task_breakdown.py
│   │   ├── no_technology_selection.py
│   │   ├── no_tester.py
│   │   ├── no_test_generator.py
│   │   ├── no_threat_modeling.py
│   │   ├── no_typing_agent.py
│   │   ├── no_vacuum_strength.py
│   │   ├── no_validator.py
│   │   ├── no_web_classifier.py
│   │   ├── _search_capabilities.py
│   │   ├── _search_enhanced.py
│   │   ├── _search_queries.py
│   │   ├── _search_router.py
│   │   ├── _search_shared.py
│   │   ├── _search_sources.py
│   │   ├── _search_wikipedia.py
│   │   └── syntax_sentinel.py
│   ├── nodes.py
│   ├── pipeline_definition.py
│   ├── policy.py
│   ├── registry.py
│   ├── scheduler.py
│   ├── skill_node.py
│   ├── state_store.py
│   ├── task.py
│   ├── task_runner.py
│   ├── telemetry.py
│   ├── topology.py
│   └── workdir.py
├── immunity
│   ├── adaptive_threat_detector.py
│   ├── apoptosis_engine.py
│   ├── async_violation_detector.py
│   ├── autoimmunity_detector.py
│   ├── emergent_behavior_detector.py
│   ├── entropy_sentinel.py
│   ├── epigenetic_masking.py
│   ├── error_persistence.py
│   ├── failure_analyzer.py
│   ├── glutathione_guardrails.py
│   ├── glutathione_pool.py
│   ├── hallucination_detector.py
│   ├── immune_memory_exchange.py
│   ├── immune_orchestrator.py
│   ├── __init__.py
│   ├── loop_detector.py
│   ├── metabolic_immune_barrier.py
│   ├── metabolic_pruner.py
│   ├── mhc_detector.py
│   ├── pathogen_analyzer.py
│   ├── regression_detector.py
│   ├── symbiosis_score.py
│   ├── vaccine_ledger.py
│   └── vacuum_trigger.py
├── __init__.py
├── intention
│   ├── __init__.py
│   └── meta_director.py
├── interface
│   ├── chat_agent.py
│   ├── diagnostico.py
│   └── __init__.py
├── mcp
│   ├── client.py
│   ├── code_executor.py
│   ├── discovery.py
│   ├── file_system.py
│   ├── __init__.py
│   ├── mcp_agent.py
│   ├── mcp_server.py
│   ├── search_web.py
│   └── server.py
├── memory
│   ├── async_memory.py
│   ├── backup_manager.py
│   ├── bandit_evolution.json
│   ├── cache.py
│   ├── check_db.py
│   ├── cognitive_cache.py
│   ├── consolidation.py
│   ├── core.py
│   ├── data
│   ├── db_manager.py
│   ├── db_utils.py
│   ├── fusion_engine.py
│   ├── __init__.py
│   ├── memory_error.py
│   ├── memory.py
│   ├── memory_storage.py
│   ├── memory_vector.py
│   ├── persistence.py
│   ├── ranking.py
│   ├── raw_pool.py
│   ├── semantic_cache.py
│   ├── synthesis_sweeper.py
│   ├── term_long.py
│   ├── term_short.py
│   └── vault_unifier.py
├── meta
│   ├── __init__.py
│   └── meta_learner.py
├── metabolism
│   ├── bucket_manager.py
│   ├── clarity_directive.py
│   ├── dashboard_congestion.py
│   ├── homocysteine_pool.py
│   ├── __init__.py
│   ├── joint_optimization.py
│   ├── jol_metrics.py
│   ├── metabolic_autocorrect.py
│   ├── metabolic_invariants.py
│   ├── metabolic_metrics.py
│   ├── methylation_cycle.py
│   ├── methylation_engine.py
│   ├── opportunity_cost_detector.py
│   ├── sentinel.py
│   ├── threshold_analyzer.py
│   └── transsulfuration_cycle.py
├── models
│   ├── agent_context.py
│   ├── event_bus.py
│   ├── __init__.py
│   └── task.py
├── observability
│   ├── entropy_interceptor.py
│   ├── health.py
│   ├── __init__.py
│   ├── load_balancer.py
│   ├── metrics_collector.py
│   ├── phospholipid_bridge.py
│   ├── registry.py
│   ├── search_bridge.py
│   └── tracing.py
├── obsidian
│   ├── 00_Quarentena
│   ├── 01_Instincts
│   ├── 02_Short_Term
│   ├── 03_Long_Term
│   ├── 04_Synapses
│   ├── 05_Vaccines
│   ├── ancestry_tree.py
│   ├── compliance.py
│   ├── consolidation.py
│   ├── delta_sleep.py
│   ├── epigenetic
│   ├── epigenetic_registry.py
│   ├── error_capture.py
│   ├── fugue_compartment.py
│   ├── __init__.py
│   ├── law_compliance_logger.py
│   ├── learning_system.py
│   ├── omnimind.py
│   ├── subconsciousapi.py
│   └── success_cycle_logger.py
├── _paths.py
├── pipeline
│   ├── engine.py
│   ├── __init__.py
│   ├── pipelinestate.py
│   ├── result.py
│   └── stages.py
├── policy
│   ├── bandit_evolutivo.py
│   └── __init__.py
├── providers
│   ├── async_http.py
│   ├── batch_writer.py
│   ├── gemini_provider.py
│   ├── groq_provider.py
│   ├── groq_provider.py.bkp
│   ├── hf_image_provider.py
│   ├── hf_inference_provider.py
│   ├── hf_router_provider.py
│   ├── hf_video_provider.py
│   ├── huggingchat_provider.py
│   ├── __init__.py
│   ├── nvidia_provider.py
│   ├── ollama_provider.py
│   ├── openai_provider.py
│   ├── opencode_provider.py
│   ├── openrouter_provider.py
│   ├── perplexity_provider.py
│   ├── poe_provider.py
│   ├── provider_config.py
│   ├── provider_metrics.py
│   ├── provider_registry.py
│   ├── provider_router.py
│   ├── provider_router.py.backup
│   ├── provider_scorer.py
│   ├── provider_state.py
│   ├── task_router.py
│   └── token_usage.py
├── recycling
│   ├── embedding_pruner.py
│   ├── __init__.py
│   ├── mta_pool.py
│   └── prompt_recycler.py
├── reflection
│   ├── claim_detection.py
│   ├── contamination_report.py
│   ├── failure_analysis.py
│   ├── __init__.py
│   ├── learning_loop.py
│   ├── reflexion_engine.py
│   ├── self_critique_evolutivo.py
│   └── self_critique.py
├── sandbox
│   ├── __init__.py
│   └── sandbox_expansion.py
├── search
│   ├── confidence_tracker.py
│   ├── feedback_loop.py
│   ├── __init__.py
│   ├── local_summarizer.py
│   ├── query_expander.py
│   ├── search_code_extractor.py
│   ├── search_memory.py
│   ├── search_middleware.py
│   ├── snippet_synthesizer.py
│   └── source_validator.py
├── security
│   ├── ast_gateway.py
│   ├── __init__.py
│   ├── mcp_sandbox.py
│   ├── network_guard.py
│   ├── pysecurity1024.py
│   ├── resource_limits.py
│   ├── runtime_sandbox.py
│   ├── sandbox_executor.py
│   └── sandbox_rules.py
├── server
│   ├── asgi.py
│   ├── health_aggregator.py
│   ├── __init__.py
│   ├── __main__.py
│   ├── mcp_server.py
│   └── server.py
├── storage
│   ├── batch_writer.py
│   ├── converter.py
│   ├── daemon_monitor.py
│   ├── __init__.py
│   ├── metabolic_adapter.py
│   └── snapshotter.py
├── tests
│   ├── conftest.py
│   ├── __init__.py
│   ├── integration
│   │   ├── test_stress_fase31.py
│   │   └── test_synapse_full_flow.py
│   ├── temp
│   ├── test_agents_tribunal.py
│   ├── test_apoptosis_kill.py
│   ├── test_artifact_contract.py
│   ├── test_artifact_extension.py
│   ├── test_ast_fuzzer.py
│   ├── test_autonomous_research_loop_e2e.py
│   ├── test_autonomous_research_loop_pipeline.py
│   ├── test_autonomous_research_loop.py
│   ├── test_await_detection.py
│   ├── test_bandit_membrane_chokepoint.py
│   ├── test_cache_immune_barrier.py
│   ├── test_chat_agent_integration.py
│   ├── test_circuit_breaker.py
│   ├── test_cli_log_level.py
│   ├── test_colony_intelligence.py
│   ├── test_confidence_tracker.py
│   ├── test_consolidation.py
│   ├── test_contamination_report.py
│   ├── test_cpu_priority_boost.py
│   ├── test_critic_batch_queue.py
│   ├── test_debug_unificado.py
│   ├── test_dependency_enforcer_autoinstall.py
│   ├── test_e2e_membrane_validation.py
│   ├── test_entropy_integration.py
│   ├── test_evo_agent_reflection_integration.py
│   ├── test_evo_integration_recent.py
│   ├── test_evolution_standalone.py
│   ├── test_experiment_runner.py
│   ├── test_failure_analyzer.py
│   ├── test_fake_noise_detector.py
│   ├── test_feedback_loop.py
│   ├── test_fewshot_embedding_cache.py
│   ├── test_fewshot_vaccine_expiry.py
│   ├── test_ga_tuning.py
│   ├── test_health_unified.py
│   ├── test_hypothesis_generator.py
│   ├── test_immune_activation.py
│   ├── test_immune_stress.py
│   ├── test_instrument_decorator.py
│   ├── test_integration_phospholipid_registry_pipeline.py
│   ├── test_integration_pipeline_genetic_algorithm_tuning.py
│   ├── test_ivm_singleton_unification.py
│   ├── test_joint_optimization.py
│   ├── test_lineage_proof.py
│   ├── test_local_summarizer.py
│   ├── test_mcp_protocol_expansion.py
│   ├── test_metabolic_apoptosis.py
│   ├── test_metabolic_immune_barrier.py
│   ├── test_meta_learner.py
│   ├── test_metrics.py
│   ├── test_mitochondrial_probe.py
│   ├── test_model_router.py
│   ├── test_no_false_metrics_deployment.py
│   ├── test_omnimind_integration.py
│   ├── test_omnimind_lineage.py
│   ├── test_phospholipid_bridge.py
│   ├── test_phospholipid_registry.py
│   ├── test_psc_hierarchy.py
│   ├── test_pysecurity1024.py
│   ├── test_python_autocomplete.py
│   ├── test_query_expander.py
│   ├── test_rag_web_search_full.py
│   ├── test_remsleep_dlq_scan.py
│   ├── test_runtime_sandbox.py
│   ├── test_search_memory.py
│   ├── test_self_critique_evolutivo.py
│   ├── test_snippet_synthesizer.py
│   ├── test_source_validator.py
│   ├── test_task_router_stress.py
│   ├── test_token_bucket.py
│   └── test_vaccine_ledger.py
├── tools
│   ├── builtins
│   │   ├── code_executor.py
│   │   ├── __init__.py
│   │   └── pdf_tools.py
│   ├── __init__.py
│   ├── search.py
│   ├── search_tools.py
│   ├── tool_library.py
│   ├── tool_router.py
│   └── web_brain.py
├── ui
│   ├── data_converter.py
│   ├── fastapi_app.py
│   ├── git_workspace.py
│   ├── __init__.py
│   ├── reactpy_components.py
│   ├── templates
│   │   ├── dashboard.html
│   │   └── index.html
│   ├── urls.py
│   ├── views.py
│   └── workspace_runner.py
├── utils
│   ├── ansi_colors.py
│   ├── controlled_subprocess.py
│   ├── hash_utils.py
│   ├── helpers.py
│   ├── __init__.py
│   ├── integrity.py
│   ├── life_signal_collector.py
│   ├── logger.py
│   └── playwright_util.py
└── validation
    ├── ast_security.py
    ├── engine.py
    ├── gateway.py
    ├── __init__.py
    ├── js_validator.py
    ├── normalization.py
    ├── scoring.py
    └── syntax.py

67 directories, 695 files
