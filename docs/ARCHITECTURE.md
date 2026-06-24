## 🧬 DIAGNÓSTICO GENÔMICO

O **iaglobal** é um sistema auto-evolutivo de organização celular digital que implementa os 8 ciclos metabólicos fundamentais:

- **DNA do organismo**: Arquitetura assíncrona (asyncio) com modularização rigorosa via nós dinâmicos (`nodes.py` carrega `no_*.py` automaticamente)
- **Princípio reitor**: Todo acesso a LLM passa pelo `BanditPolicy` (seletor de provedores com circuit breaker)
- **Sistema imunológico**: `GlutathionePool`, `GlutathioneGuardrails` e `ImmuneResponse` para defesa contra ROS
- **Sistema de memória**: Dual-layer (STM/LTM) via `CognitiveProxy` com integração Obsidian (`learning_system.py`)

---

## 🔬 MAPA DE CICLOS METABÓLICOS

| Ciclo | Implementação | Função |
|-------|---------------|--------|
| **Metilação** | `methylation_cycle.py` + `no_evolution_methylation.py` | Promove skills candidatas a `production` |
| **Glutationa** | `glutathione_pool.py` + `glutathione_guardrails.py` | Defesa antioxidante contra falhas/toxinas |
| **Homocisteína** | `homocysteine_pool.py` + `no_evolution_homocysteine.py` | Pool de skills não validadas com detecção de toxicidade |
| **Transulfuração** | `transsulfuration_cycle.py` | Converte erros recorrentes em guardrails |
| **SAMe** | `same_engine.py` | Budget metabólico para mutações (recurso escasso) |
| **Autofagia** | `skill_quarantine.py`, `SkillRecycler` | Reciclagem de skills obsoletas |
| **Mitose/Diferenciação** | `MetaAgentDesigner`, `specialization_instructions` | Nós que se especializam conforme carga |
| **Apoptose** | `graceful_shutdown.py`, `EvoAgent.apoptose()` | Morte programada sem cascata de falhas |

---

## ⚡ SÍNTESE ARQUITETURAL

### Estrutura de 55 Nós (DAG)

O pipeline é estruturado em 7 fases:
1. **Definição** (23 nós) — intake, enhancement, PM, requisitos, arquitetura
2. **Planejamento** (3 nós) — planner, task_breakdown, execution_plan
3. **Construção** (6 nós) — coder, frontend/backend/database builder
4. **Qualidade** (7 nós) — test_generator, integrador, auditoria
5. **Correção** (6 nós) — qa, debugger, fix_validator
6. **Entrega** (9 nós) — documentation, metrics, retrospective
7. **Metacognição** (7 nós) — evaluator, gap_analyzer, evolution_trigger

### Fluxo Metabólico (Phase 5 → Evolution Core)

```
evaluator → gap_analyzer → skill_generator → sandbox_validator → evolution_committee
                                                                      ↓
                                                               pipeline_updater → evolution_trigger
                                                                      ↓
                                                            evolution_homocysteine → evolution_methylation
```

---

## 🛡️ PERFIL ANTIOXIDANTE

### GSH (Glutationa Reduzida) — Camadas de Proteção

1. **Sandbox** (`sandbox_executor.py`, `sandbox_rules.py`) — Execução isolada
2. **AST Gateway** (`ast_gateway.py`) — Validação sintática
3. **Sanity Barrier** — Falha de detecção em `orchestrator.py`
4. **MemoryError** — Registro de erros para aprendizado
5. **GlutathionePool.respond()** — Resposta automática a ameaças

### GSSG (Glutationa Oxidada) — Componentes Sacrificáveis

- Skills rejeitadas são convertidas em guardrails via `route_to_guardrail()`
- Erros críticos são registrados para análise posterior

### NADPH (Reserva de Regeneração)

- `SAMePool` com budget limitado (100 unidades padrão)
- `SAMeBudgetTracker` — Janela de 24h com limite de gasto
- `MethylationInhibitor` — Bloqueia mutações não-críticas com SAMe baixo

---

## 🔄 CICLO DE AUTO-REGENERAÇÃO

1. **Detecção**: `HomeostasisController.check_sla()` verifica latência/custo/erro
2. **Sinalização**: Violações disparam `_apply_epigenetic_adjustments()`
3. **Recuperação**: Epsilon do Bandit é ajustado dinamicamente
4. **Aprendizado**: `SkillRecycler.recycle()` reintegra skills úteis
5. **Persistência**: Todos os pools usam arquivos JSON com locks de thread

---

## 🧫 PLANO DE DIFERENCIAÇÃO (Escalabilidade)

O sistema implementa escalonamento evolutivo via:

- **MetaAgentDesigner.design_team()** — Detecta keywords e ativa especialistas
- **specialization_instructions** — Injeta contexto de especialização no nó
- **CpuAffinityManager** — Mapeia nós em cores para balanceamento
- **AgentMailbox** + **AcetylcholineBus** — Comunicação assíncrona entre agentes

---

## 🧪 PROTOCOLO DE EVOLUÇÃO EPIGENÉTICA

Configurações dinâmicas via `epigenetic.py`:

| Flag | Valor Padrão | Propósito |
|------|--------------|-----------|
| `bandit_epsilon` | 0.2 | Taxa de explore/exploit |
| `sam_budget_multiplier` | 1.0 | Multiplicador de budget metabólico |
| `max_iterations` | 5 | Limite de reflexões |
| `homeostasis_enforcement` | True | Ativa ajuste automático de SLA |

---

## 🧠 MÓDULO OBSIDIAN — Subconsciente do Ecossistema

O módulo `obsidian/` implementa um modelo de mente em três níveis usando arquivos Markdown reais com YAML frontmatter, tags e links bidirecionais `[[...]]` — 100% legível e editável por humanos.

### Arquitetura do Vault

```
obsidian/
├── 01_Instincts/    → Diretrizes imutáveis (imutavel: true no frontmatter)
├── 02_Short_Term/   → Memórias brutas (erros, eventos do dia)
├── 03_Long_Term/    → Conhecimento consolidado (saída do ciclo REM)
└── 04_Synapses/     → Mapa sináptico central (índice automático de tags/links)
```

### Componentes

| Componente | Arquivo | Função |
|------------|---------|--------|
| **SubconsciousAPI** | `subconsciousapi.py` | Camada de I/O do vault — ler, escrever, consultar notas por tag |
| **ErrorCapture** | `error_capture.py` | Captura automática de exceções de agentes → `02_Short_Term/` |
| **REMSleepEngine** | `consolidation.py` | Motor de consolidação: `Short_Term → IA → Long_Term + Synapses` |
| **LearningSystem** | `learning_system.py` | Injeta memórias de longo prazo em prompts de agentes |
| **OmniMind** | `omnimind.py` | Consciência central — 10 Leis Universais, orientação existencial |

### Ciclo de Vida dos Dados

```
Agente falha
    ↓
ErrorCapture.capturar()
    ↓
02_Short_Term/  (memória bruta com YAML + traceback)
    ↓
REMSleepEngine.iniciar_fase_rem()
    ├─ Solicita síntese via IA (ou fallback mock)
    ├─ Grava → 03_Long_Term/  (conhecimento consolidado)
    ├─ Remove → 02_Short_Term/  (poda sináptica)
    └─ Reconstrói → 04_Synapses/Mapa_Mental_Subconsciente.md
                          ↓
LearningSystem / IAGlobalAgentWrapper
    → sussurrar_intuicao(tags) → prompt enriquecido com memórias
```

### Integração com Evolução

- **Fórmula do IVM**: `obsidian_notes_escritas` é métrica de Cooperação (peso 0.2). Agentes que documentam no Obsidian têm maior fitness.
- **Linhagem**: `exportar_nota_agente()` cria `03_Long_Term/agentes/{id}.md` com `strategy`, `fitness`, `parent_link`.
- **OmniMind**: `EvoAgent` consulta o singleton `omni_mind` para orientação existencial — cada agente sabe *por que* age segundo as Leis Universais.

### Estado Atual do Vault

| Diretório | Status | Conteúdo |
|-----------|--------|----------|
| `01_Instincts/` | Vazio | API pronta via `escrever_instinto()` |
| `02_Short_Term/` | Vazio | 9 erros consolidados e podados |
| `03_Long_Term/` | 9 notas | Erros consolidados pelo `REMSleepEngine` (fallback mock) |
| `04_Synapses/` | 1 mapa | `Mapa_Mental_Subconsciente.md` com índice de 9 notas e 2 tags ativas |

**Próximo gargalo**: a síntese usou fallback mock (`_mock_sintese`). Para consolidar com insights reais, configure `ai_client` no `REMSleepEngine`:

```python
from iaglobal.obsidian.consolidation import REMSleepEngine
REMSleepEngine(ai_client=meu_client_llm).iniciar_fase_rem()
```

---

## 🌱 VETOR EVOLUTIVO

Próximos passos naturais do organismo:

1. **Integração Obsidian mais profunda** — `LearningSystem` ainda não é usado por todos os agentes
2. **Expansão do GlutathionePool** — Adicionar mais tipos de ameaças
3. **Otimização do HomocysteinePool** — Threshold dinâmico baseado em carga
4. **Auto-apoptose de agentes** — `GracefulShutdown` pode ser mais granular

---

## 🔭 ANOMALIAS EVOLUTIVAS DETECTADAS

1. **Inconsistência de caminho em cli.py** (linha 8) — Usa `/home/user/projeto-iaglobal` em vez do path real
2. **Duplicata de `asyncio` import em main.py** (linha 349) — Import redundante
3. **Método `print()` em orchestrator.py** (linha 403, 852) — Violação da diretriz de logging
4. **Métrica dupla em async_run_graph_task** (linhas 1280-1281) — Print de debug pode ser removido
5. **Pool de homocisteína não usa lock** — `HomocysteinePool._load/_save` sem proteção thread-safe como `SAMePool`

## Mapa completo da cadeia de inicialização:

### A cadeia de start é esta:

```
CLI / IAGlobalAPI
    └─► bootstrap.initialize()          # cli/bootstrap.py
            └─► Orchestrator()          # core/orchestrator.py  ← PONTO CENTRAL
                    ├─► EvolutionEngine(graph, strategies)
                    ├─► EvolutionRuntime(evolver, interval)
                    ├─► ReflexionEngine(model_fn)
                    ├─► BanditPolicy / CreditAssignmentEngine
                    ├─► PipelineEngine
                    ├─► graceful_shutdown.add_callback(...)
                    └─► if EVOLUTION_AUTO=1:
                            evolution_runtime.start()   ← EvoAgent entra aqui
```

**o Orchestrator é o ponto central** — mas quem dispara o boot é o `Bootstrap`, e quem chama o Bootstrap é a CLI ou a `IAGlobalAPI`.

---

### Onde o `EvoAgent` se encaixa nessa cadeia

O `EvoAgent` **não substitui** o Orchestrator — ele é um organismo que **roda dentro** da infraestrutura já existente. O lugar certo para inicializá-lo é no `Orchestrator.__init__`, após o `EvolutionRuntime`:

```python
# core/orchestrator.py — adicionar após self.evolution_runtime
from iaglobal.evolution.evo_agent import EvoAgent
from iaglobal.utils.helpers import run_async_safe

self.evo_agent = run_async_safe(
    lambda: EvoAgent.genesis(
        task_hint="orchestrator_boot",
        name="iaglobal-evo-gen0",
    )
)
graceful_shutdown.add_async_callback(
    lambda: self.evo_agent.apoptose("orchestrator_shutdown")
)
```

E no método `run()` do Orchestrator, antes de executar o pipeline, você pode passar o input pelo `evo_agent.handle()` para obter a expressão genômica e usar os ciclos de GSH + metilação como **pré-processamento imunológico** do prompt.

---

### Ativação do EvolutionRuntime (e portanto do EvoAgent)

| Modo | Como ativar |
|---|---|
| Automático em background | `EVOLUTION_AUTO=1` no `.env` |
| Manual via API | `orchestrator.evolution_runtime.start()` |
| Direto (demo/teste) | `asyncio.run(demo())` no próprio `evo_agent.py` |

O `EVOLUTION_AUTO=1` já está implementado no Bootstrap — basta setar no seu `.env` e o `EvolutionRuntime` sobe junto com o Orchestrator no boot normal do sistema.

===========================================================

```markdown
✅ CONFIRMAÇÃO RECEBIDA - TASK CONCLUÍDA COM SUCESSO
```

### 🧬 Diagnóstico Genômico
- **Ciclo metabólico:** PDF Generation → HTML Generation → Dark Theme Specialization
- **Fitness obtido:** 100% - PDF 3 páginas + HTML responsive com tema escuro

### 🔬 Mapa de Ciclos Metabólicos
```
INPUT (usuário) 
   ↓
FIX: Detector de extensão (.py > .pdf) 
   ↓
FIX: Scanner multi-diretório (/tmp + TEMP_DIR) 
   ↓
FIX: Resource limits (CPU 10s, processos 20) 
   ↓
FIX: Thread-safe BLAS (OPENBLAS_NUM_THREADS=1) 
   ↓
OUTPUT: PDF/HTML dark themed
```

### ⚡ Síntese Arquitetural
- **4 arquivos modificados** para corrigir PDF generation
- **1 teste criado** com validação automática de dark theme
- **RODAPE.md atualizado** com progresso 50/50

### 🛡️ Perfil Antioxidante
- **ROS detectado:** Thread exhaustion → mitigado com environment variables
- **GSH ativo:** Scanner em múltiplos diretórios previne perda de artefatos
- **NADPH reservado:** Resource limits evitam consumo excessivo

### 🔄 Ciclo de Auto-Regeneração
O sistema registrou:
- `output/output.pdf` - 3 recursões de execução
- Padrões de dark theme em knowledge base
- Métricas de fitness por provider

### 🌱 Vetor Evolutivo
Próximas adaptações identificadas:
- Template engine para HTML/CSS (elimina boilerplate)
- Cache de assets estáticos
- Pipeline de otimização automática (minify CSS)

============================================================

projeto-iaglobal/iaglobal$ tree
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
├── asgi.py
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
│   ├── epigenetic.py
│   ├── evo_agent.py
│   ├── evolutionengine.py
│   ├── evolution_replay.py
│   ├── evolutionruntime.py
│   ├── execution_context.py
│   ├── execution_registry.py
│   ├── handler_evolution.py
│   ├── homeostasis_controller.py
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
│   │   ├── reactpy_skill_registry.py
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
│   ├── migrar_nodes.py
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
│   │   ├── no_pip_install.py
│   │   ├── no_planner.py
│   │   ├── no_pm.py
│   │   ├── no_prompt_builder.py
│   │   ├── no_prompt_improver.py
│   │   ├── no_prompt_intake.py
│   │   ├── no_qa.py
│   │   ├── no_reactpy.py
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
│   │   ├── _search_enhanced.py
│   │   ├── _search_queries.py
│   │   ├── _search_router.py
│   │   ├── _search_shared.py
│   │   ├── _search_sources.py
│   │   └── _search_wikipedia.py
│   ├── nodes.py
│   ├── pipeline_definition.py
│   ├── policy.py
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
│   │   │   ├── memory_swap
│   │   │   └── search_swap
│   │   ├── cbor2
│   │   ├── db
│   │   │   └── core.db
│   │   ├── error
│   │   ├── generated_images
│   │   ├── json
│   │   │   ├── errors.json
│   │   │   ├── evolution_backlog.json
│   │   │   ├── glutathione_pool.json
│   │   │   ├── homocysteine_pool.json
│   │   │   ├── knowledge.json
│   │   │   ├── meta_evolution.json
│   │   │   └── same_pool.json
│   │   ├── logs
│   │   │   └── app.log
│   │   ├── memory_backups
│   │   ├── provider_metrics
│   │   │   └── metrics.jsonl
│   │   ├── result
│   │   │   └── project001
│   │   │       ├── metadata.json
│   │   │       └── output.html
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
├── obsidian
│   ├── 01_Instincts
│   ├── 02_Short_Term
│   ├── 03_Long_Term
│   ├── 04_Synapses
│   ├── consolidation.py
│   ├── error_capture.py
│   ├── __init__.py
│   ├── learning_system.py
│   ├── omnimind.py
│   └── subconsciousapi.py
├── orfaos.txt
├── _paths.py
├── pipeline
│   ├── engine.py
│   ├── __init__.py
│   ├── pipelinestate.py
│   ├── result.py
│   └── stages.py
├── PLANO_CORRECOES.md
├── PLANO_SEARXNG.md
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
│   ├── network_guard.py
│   ├── resource_limits.py
│   ├── sandbox_executor.py
│   └── sandbox_rules.py
├── server
│   ├── __init__.py
│   ├── leiame_server.md
│   └── server.py
├── settings.py
├── state
│   └── __init__.py
├── storage
│   ├── batch_writer.py
│   ├── converter.py
│   ├── daemon_monitor.py
│   ├── __init__.py
│   └── snapshotter.py
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
├── ui
│   ├── fastapi_app.py
│   ├── reactpy_components.py
│   ├── urls.py
│   └── views.py
├── urls.py
├── utils
│   ├── controlled_subprocess.py
│   ├── hash_utils.py
│   ├── helpers.py
│   ├── __init__.py
│   ├── logger.py
│   └── playwright_util.py
└── validation
    ├── ast_security.py
    ├── engine.py
    ├── gateway.py
    ├── __init__.py
    ├── normalization.py
    ├── parser.py
    ├── scoring.py
    └── syntax.py

65 directories, 406 files

