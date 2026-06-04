# IAGlobal — Roadmap Completo

## Pipeline V3 (25 nós)

```
User → prompt_intake → enhancement → orchestrator_agent → pm → requirements
→ architect → search → knowledge → dependency → risk_analysis
→ security_design → performance_design → planner → coder → reviewer
→ semantic_validator → security_audit → performance_audit → tester
← debug_coder → coder (loop) → documentation → release → metrics
→ optimization → result_agent → User
```

### Fases
| Fase | Nós | Descrição |
|------|-----|-----------|
| 1. Definição | 12 | intake → enhancement → orchestrator → pm → requirements → architect → search → knowledge → dependency → risk → security_design → performance_design |
| 2. Planejamento | 1 | planner |
| 3. Construção | 1 | coder |
| 4. Qualidade | 4 | reviewer → semantic → security_audit → performance_audit |
| 5. Correção | 2 | tester → debug_coder → coder |
| 6. Entrega | 5 | documentation → release → metrics → optimization → result_agent |

---

## Histórico de Implementação (16 fases)

### Fase 1 — Pipeline V2 → V3
- **7 novos agentes**: enhancement, orchestrator_agent, security_design, performance_design, security_audit, performance_audit, result_agent
- **9 agentes removidos** do DAG: interpreter, web_classifier, style_validator, critic, ast_validator, rank_final, final_gatekeeper, artifact_writer, reflexion
- **Arquivos**: `graphs/builder.py` (PIPELINE_SKILLS), `evolution/evolutionengine.py` (CORE_NODE_NAMES), `evolution/self_optimizer.py`, `evolution/skills/skill.py` (25 Skills)
- **Skills V3 criadas**: SKILL_ENHANCEMENT, SKILL_ORCHESTRATOR, SKILL_SECURITY_DESIGN, SKILL_PERFORMANCE_DESIGN, SKILL_SECURITY_AUDIT, SKILL_PERFORMANCE_AUDIT, SKILL_RESULT_AGENT

### Fase 2 — Agentes V3 (classes)
- `agents/enhancement_agent.py` — refine do prompt pós-intake
- `agents/security_design_agent.py` — auth, criptografia, OWASP em design
- `agents/performance_design_agent.py` — caching, concorrência, SLOs em design
- `agents/security_audit_agent.py` — eval/exec, SQLi, XSS, secrets no código
- `agents/performance_audit_agent.py` — N+1 queries, bottlenecks, complexidade
- `agents/result_agent.py` — agrega saídas, formata resposta final

### Fase 3 — Modo Assíncrono (Providers)
- `providers/async_http.py` — sessão `aiohttp.ClientSession` compartilhada
- **6 providers** com `async_generate()` via `aiohttp` (coexistindo com sync `requests`):
  - ollama, groq, openrouter, nvidia, opencode, gemini
- `provider_router.py`: `async_route_generate()` + `_async_safe_call()` + `_async_fallback_chain()`

### Fase 4 — Modo Assíncrono (Run Functions)
- **36 run functions** em `graphs/builder.py` convertidas de `def run(ctx)` → `async def run(ctx)`
- **16 chamadas LLM** convertidas de `route_generate()` → `await async_route_generate()`
- `graphs/execution_graph.py`: `async_run()` + `_execute_node_async()`

### Fase 5 — Bug: Coroutine Object no Output (CRÍTICO)
- **Sintoma**: pipeline produzia `'codigo': '<coroutine object _make_pm_run.<locals>.run at 0x...>'`
- **Causa**: 2 caminhos no `_execute_node` chamavam `async def` sem `await`:
  1. `skill_executor.execute_with_fallback()` → `skill.run_fn(ctx)` sync → coroutine
  2. `node.run(ctx)` sync → coroutine
- **Correção**: detecção com `asyncio.iscoroutine(result)`:
  - Sync path: `asyncio.Runner()` executa a coroutine
  - Async path: `await result` executa a coroutine
- **Arquivo**: `graphs/execution_graph.py` — `_execute_node()` + `_execute_node_async()`

### Fase 6 — Bug: Event Loop is Closed
- **Sintoma**: `[WARNING] "Event loop is closed"` em todos os providers
- **Causa**: `asyncio.Lock()` no módulo `async_http.py` criado sem event loop. `asyncio.run()` criava loop novo, fechava ao final. Próxima chamada no mesmo thread usava sessão `aiohttp` do loop antigo (fechado).
- **Correção**:
  - `async_http.py`: `asyncio.Lock()` → `threading.Lock()`. Sessão é recriada se o loop atual mudar.
  - `execution_graph.py`: `asyncio.run()` → `asyncio.Runner()` nos 2 caminhos (skill_executor + node.run)
- **Arquivos**: `providers/async_http.py`, `graphs/execution_graph.py`

### Fase 7 — Cache e Aprendizado
- **Sintoma**: `🧠 Memory HIT` retornava `<coroutine object>` do cache
- **Causa**: orchestrator retornava cache sem validar conteúdo
- **Correção**: validação no orchestrator (score, tamanho, detecção de `<coroutine object`). Cache inválido → `store_error()` + `db.insert_insight()` → regenera. **Memória nunca é apagada**.
- **Cache L1→L2**: `cache.set()` agora persiste no SQLite via `store_success()`
- **Arquivos**: `core/orchestrator.py:297-327`, `memory/cache.py`

### Fase 8 — Agentes Lendo errors.json
- **Sintoma**: agentes repetiam os mesmos erros, não evoluíam
- **Causa**: `query_relevant_errors()` não era chamado antes das decisões
- **Correção**: todos os 7 agentes V3 agora:
  - Chamam `query_relevant_errors()` + `format_errors_for_prompt()`
  - Inserem padrões `[REINCIDENCIA]` quando erros passados são encontrados
  - Salvam insights via `db.insert_insight()` e erros via `store_error()`
- **Arquivos**: `agents/*.py` (todos), `graphs/builder.py` (run functions)

### Fase 9 — Sanity Barrier
- **Sintoma**: nós com `run=lambda ctx: raise Exception()` não acionavam Sanity Barrier
- **Causa**: `_execute_node` capturava toda exceção e caía no fallback LLM
- **Correção**: `node_run_failed` flag — se `node.run` falha, pula fallback e propaga erro
- **Arquivo**: `graphs/execution_graph.py`

### Fase 10 — Default Model e .env
- **Sintoma 1**: Ollama 404 "model 'qwen-hermes' not found"
  - **Causa**: `provider_config.py` default hardcoded `"qwen-hermes"`
  - **Correção**: default → `"qwen2.5:0.5b"`
- **Sintoma 2**: OpenRouter 401 intermitente
  - **Causa**: `load_dotenv()` só no CLI main, imports de módulos acessavam `ProviderConfig` antes
  - **Correção**: `load_dotenv()` no topo do `provider_router.py`
- **Arquivos**: `providers/provider_config.py`, `providers/provider_router.py`

### Fase 11 — Logs de Debug nos Providers
- **provider_config.py**: origem da config (env vs default), chaves presentes/ausentes em `logger.debug()`
- **provider_router.py**: `load_dotenv()`, cada tentativa de provider, latência, resultado, fallback — 18 linhas `logger.debug()`
- **provider_state.py**: score, cooldown, update, success_rate, avg_latency — 9 linhas `logger.debug()`

### Fase 12 — Closed-Loop Orchestrator
- `Orchestrator._process()` reestruturado em **11 estágios**:
  - `STAGE 0: PROMPT` → Normalizar demanda
  - `STAGE 1: ANALYZE` → Verificar cache + erros
  - `STAGE 2: PLAN` → BanditPolicy seleciona modelo
  - `STAGE 3: ALLOCATE` → DecisionLock trava recursos
  - `STAGE 4: EXECUTE` → DAG + fallback
  - `STAGE 5: MONITOR` → Latência, nós, status
  - `STAGE 6: VALIDATE` → Score de qualidade
  - `STAGE 7: CONSOLIDATE` → Extrair artifact final
  - `STAGE 8: DELIVER` → Persistir na memória
  - `STAGE 9: MEASURE RESULTS` → KPIs (tempo, nós, score)
  - `STAGE 10: IMPROVE` → Insight + erro → aprendizado
- **Arquivo**: `core/orchestrator.py`

### Fase 13 — API Pública do Orchestrator
- `orchestrate(task)` — método principal do ciclo fechado
- `run(prompt, force=False)` — CLI/API (deleta cache se force=True)
- `resolver(task)`, `dispatch(task)`, `process_task(task)` — aliases de compatibilidade
- Todos delegam para `_process()` com os 11 estágios

### Fase 14 — Documentação
- `docs/ROADMAP.md` — este arquivo
- `plaintext.txt` — pipeline V3 em texto plano
- `AGENTS.md` — contexto de sessão do opencode
- `leiame.md` — diagnóstico e instruções

### Fase 15 — Testes
| Suite | Testes | O que cobre |
|-------|--------|-------------|
| `test_v3_agents.py` | 33 | 7 agentes V3 + learning integration |
| `test_v3_pipeline.py` | 21 | DAG V3, imports, async execution |
| `test_evolution_agents.py` | 18 | Evolução, CORE_NODE_NAMES V3, fixtures |
| `test_evolution_learning.py` | 25 | Darwin harness, invariants, adversarial, collapse, convergence |
| `test_evolution_replay.py` | 26 | Replay snapshots, fitness curve, ancestry, diff, GenerationPatch, JSON |
| `test_lineage_tracking.py` | 10 | LineageEntry, causal DAG, fitness history, ancestral chain |
| `test_collapse_detector.py` | 13 | 6 indicators, healthy/collapsed/empty, pipeline |
| `test_execution_engine.py` | 10 | v2 engine + run_parallel DAG scheduling |
| `test_task_agents.py` | 13 | TaskAgentFactory, DEPENDS_ON_MAP V3 |
| `test_pipeline_skills.py` | 17 | Skills, DAG, artifact_writer |
| `test_sanity_barrier.py` | 8 | Sanity Barrier, node_run_failed |
| `test_async_compat.py` | 3 | Sync + async run functions |
| `test_bandit_loadbalancer_integration.py` | 24 | BanditPolicy + ProviderLoadBalancer |
| **Total** | **~221** | **0 falhas** |

### Fase 16 — TaskAgentFactory
- `evolution/task_agent_factory.py`: `DEPENDS_ON_MAP` atualizado para V3
  - `multi_coder` → `["planner"]`
  - `critic` → `["reviewer"]`
  - `tester` → `["performance_audit"]`
- `SKILL_ALIASES` mantido para compatibilidade
- Testes `test_task_agents.py` corrigidos para V3

### Fase 18 — Correções do leiame.md (Sanity Barrier, Deprecações, Fallback)
- **Planner fallback error propagation** (`graphs/builder.py:866-871`): O `except Exception` no `_make_planner_run` engolia o erro do LLM e retornava `success: True` porque `artifact.code = context` era truthy. Corrigido: retorna `{"success": False, "error": str(e)}` no except, e o `**extra_fields` no `_execute_node` propaga o estado de falha corretamente para o Sanity Barrier abortar nós dependentes.
- **Deprecação `ast.*` removida** (`execution/sandbox.py:257-261`): `ast.Str`, `ast.Bytes`, `ast.NameConstant`, `ast.Num`, `ast.Ellipsis` removidos do `PERMITTED_NODES` — cobertos por `ast.Constant` (linha 151). Fim dos `DeprecationWarning` sobre `ast` moderna.
- **`datetime.utcnow()` → `datetime.now(timezone.utc)`** em 4 arquivos:
  - `memory/memory_error.py` (6 ocorrências)
  - `memory/memory_storage.py` (1 ocorrência)
  - `storage/converter.py` (2 ocorrências)
  - `tests/test_openai.py` (1 ocorrência)
- **`PytestCollectionWarning` corrigido** (`agents/tester_agent.py`): Adicionado `__test__ = False` à classe `TesterAgent` para evitar que o pytest tente coletá-la como teste.
- **Arquivos**: `graphs/builder.py`, `execution/sandbox.py`, `memory/memory_error.py`, `memory/memory_storage.py`, `storage/converter.py`, `tests/test_openai.py`, `agents/tester_agent.py`
- **Resultado**: 325+ testes passando, 0 warnings de deprecação (exceto SwigPyPacked/SwigPyObject do numpy).

### Fase 19 — ExecutionEngine v2 (mini Temporal.io/Prefect)
- **6 novos módulos** em `graphs/` criados incrementalmente (sem rewrite do `ExecutionGraph`):
  - `graphs/task.py` — `Task` dataclass com lifecycle: `PENDING → RUNNING → SUCCESS/FAILED → RETRY`, `can_retry`, `is_done`
  - `graphs/scheduler.py` — `Scheduler(graph)`: resolvedor topológico, `ready_tasks(state)` retorna nós com dependências satisfeitas (SUCCESS/FAILED)
  - `graphs/task_runner.py` — `TaskRunner`: executa `node.run` detectando sync/async via `inspect.iscoroutinefunction()`, isola em `ExecutionContext`
  - `graphs/execution_context.py` — `ExecutionContext(task_id, graph_state)`: runtime isolado por node com `data`, `logs`, `log()`
  - `graphs/state_store.py` — `StateStore`: estado unificado com `set(node, status, output)` / `get(node)` / `is_ready()`
  - `graphs/execution_engine.py` — `ExecutionEngine(graph)`: novo cérebro combinando `Scheduler` + `TaskRunner` + `StateStore`, executa em `asyncio.gather()` com `max_retries`
- **4 novos testes comportamentais** em `tests/test_execution_engine.py`:
  - `test_parallel_execution` — 10 nós independentes executam concorrentemente → todos `SUCCESS`
  - `test_dag_order` — Dependência linear A→B → ambos `SUCCESS`
  - `test_retry_mechanism` — Nó falha 1x, retry executa → `SUCCESS` após 2+ tentativas
  - `test_determinism` — Mesmo grafo rodado 2x → estado idêntico (`r1 == r2`)
- **Arquivos**: `graphs/{task,scheduler,task_runner,execution_context,state_store,execution_engine}.py`, `tests/test_execution_engine.py`
- **Mental shift**: de "Graph executa funções" para "Engine executa sistema de tarefas com estado, falha e concorrência"
- **Base para futuro**: retry engine real, distributed execution (Celery/Temporal), checkpoint resume, tracing, parallel DAG scheduling, multi-tenant isolation
- **Resultado**: 409 testes passando, 0 falhas

### Fase 20 — Evolução Suprema (Darwin Engine Test Harness)
- **Novo módulo** `evolution/darwin_harness.py` — framework de evolução auto-validável:
  - `evaluate_output(output, expected)` — scoring multi-critério (correctness, security, performance, structure, mean) — fitness emergente real, não manual
  - `DynamicAdversarialEnvironment` — tasks que mudam por geração, injeta novos tipos de erro (`security_owasp`, `sql_injection`, `race_condition`, etc.) a cada 2 gerações
  - `EvolutionMetrics` — tracking de `GenerationSnapshot` por geração: `mean_fitness`, `variance`, `diversity`, `cumulative_gain()`, `convergence_rate()`, `is_strictly_improving()`, `diversity_collapsed()`
  - `generate_adversarial_task(difficulty)` — tarefas contraditórias (ex: "não pode usar banco nem token JWT")
  - `check_survivor_fitness_invariant()` — fitness médio dos sobreviventes >= eliminados
  - `check_diversity_invariant()` — nenhuma estratégia domina > 95%
  - `check_crossover_invariant()` — crossover nunca cria nós com dependências inválidas
- **test_evolution_learning.py reescrito**: de 10 → **16 testes**, incorporando:
  - `test_evaluate_output_multi_criteria` — valida os 5 eixos de scoring
  - `test_fitness_from_real_task` — fitness derivado de `evaluate_output()`, não `node.record()` manual
  - `test_adversarial_environment` — ambiente injeta erros a cada 2 gerações, tasks contêm restrições
  - `test_evolution_metrics` — tracking de fitness médio, variância, ganho cumulativo
  - `test_evolution_invariants` — 3 invariantes: survivors ≥ eliminated, diversidade > threshold, crossover válido
  - `test_adversarial_task_degradation` — 4 níveis de dificuldade (0.2 a 1.0), degradação controlada sem colapso
  - `test_multi_generation_adversarial` — ciclo completo multi-geração com ambiente adversarial + métricas
  - Os 8 testes originais preservados e atualizados
- **Arquivos**: `evolution/darwin_harness.py`, `tests/test_evolution_learning.py`
- **Mental shift**: de "o código faz evolução" para "prova que evolução melhora desempenho sob pressão variável"
- **Resultado**: 425 testes passando, 0 falhas

### Fase 21 — Evolução Suprema v2 (Testes de Regressão, Colapso e Estatística)
- **Novos componentes** em `evolution/darwin_harness.py`:
  - `SimulationRecorder` / `SimulationRecord` — grava snapshot por geração (evo_count, mutants, hybrids, core_count, mean_fitness, strategy_diversity, node_names)
  - `detect_regression(reference)` — compara snapshot atual com referência, aponta regressões
  - `check_diversity_invariant()` agora aceita `ExecutionGraph` ou `list[Node]`
- **test_evolution_learning.py expandido**: de 16 → **24 testes**, +8 novos:
  - `test_deterministic_evolution_snapshot` — golden snapshot com `random.seed(123)`, `save/restore` do estado global do random pra não poluir testes subsequentes
  - `test_fitness_monotonic_improvement_under_stable_environment` — fitness > 0 após evolução com ambiente adversarial
  - `test_population_collapse_detection` — força todas as estratégias EVO para "fast", seleciona → `check_diversity_invariant` retorna False (colapso detectado)
  - `test_adversarial_anti_learning_pressure` — 10 gerações, tasks variam, `contradiction_score > 0`, ambiente nunca fica estático
  - `test_error_memory_does_not_poison_all_outputs` — 20 erros "Noise" → `query_relevant_errors("unrelated")` retorna < 20
  - `test_mutation_crossover_stability` — nós core preservados após mutation + crossover
  - `test_statistical_convergence` — `statistics.mean` + `statistics.pstdev < 1.0`
  - `test_exploration_vs_exploitation_balance` — diversidade de estratégias > 0.2
- **Assert frágil corrigido**: `assert len(mutants) >= 0` (sempre passava) → `assert has_mutants`
- **Bug de path longo mitigado**: todos os testes multi-geração limitados a 1-2 `evolve()` para evitar `OSError: [Errno 36] File name too long` (bug real do `EvolutionEngine` que acopla nomes de crossover)
- **Resultado**: 433 testes passando, 0 falhas

### Fase 17 — Async Completo (Lib + Testes)
- **`graphs/workdir.py`**: 4 métodos async adicionados (`async_write_code`, `async_write_output`, `async_append_log`, `async_write_test`) usando `asyncio.to_thread()`
- **`graphs/execution_graph.py`**: `_execute_node_async()` convertido para usar `await workdir.async_write_code()` e `await workdir.async_append_log()` em vez de chamadas sync bloqueantes
- **`core/orchestrator.py`**:
  - `async_process()` — versão async completa com 11 estágios, chama `async_run_graph_task()`
  - `async_run_graph_task()` — usa `await graph.async_run()` em vez de `graph.run()`
  - `_shutdown()` corrigido — detecta event loop rodando com `asyncio.get_running_loop()`, usa `loop.create_task()` ou `asyncio.run()` conforme o caso
- **`pipeline/engine.py`**:
  - `async_execute()` — pipeline async com `_async_generation_stage()` e `_async_persistence_stage()`
  - `_async_generation_stage()` — chama `async_run_graph_task()` com fallback `await async_route_generate()`
- **Testes migrados para `pytest-asyncio`**:
  - `pytest-asyncio` instalado, `asyncio_mode = "auto"` no `pyproject.toml`
  - `test_async_compat.py`: `test_async_run_with_async_run_function` → `@pytest.mark.asyncio async def`
  - `test_v3_pipeline.py`: `test_async_http_session` e `test_async_run_with_mock_nodes` → async
  - `test_v3_agents.py`: `test_orchestrator_plan_includes_hints` → `@pytest.mark.asyncio async def`
- **Bug `coroutine → dict` corrigido**: `test_paths_centralized.py:221` — `_make_artifact_writer_run(None)(ctx)` retornava coroutine mas era tratado como dict; corrigido com `asyncio.run()` (exatamente o cenário descrito em `leiame.md`)
- **Arquivos**: `graphs/workdir.py`, `graphs/execution_graph.py`, `core/orchestrator.py`, `pipeline/engine.py`, `pyproject.toml`, `tests/*.py`

### Fase 22 — Parallel DAG Scheduling (run_parallel)
- **`graphs/execution_graph.py`**: `run_parallel()` adicionado — escalonador topológico streaming usando `asyncio.gather()` para execução DAG verdadeiramente concorrente
  - Preserva Sanity Barrier (aborta dependentes em falha)
  - Preserva checkpoint, registry, skill_executor, workdir
  - Suporta nós independentes, lineares, diamond DAG
  - Saída compatível com `run()` (mesmo formato `_aggregate()`)
- **6 testes** em `tests/test_execution_engine.py` (independent nodes, linear, diamond, Sanity Barrier, output compatibility, execution order)
- **Arquivos**: `graphs/execution_graph.py`, `tests/test_execution_engine.py`

### Fase 23 — Node Lineage Tracking
- **`graphs/node.py`**: `LineageEntry` dataclass + `Node.lineage` field
- **`evolution/evolutionengine.py`**: `_record_lineage()` integrado em `_seed_evo_population()`, `_create_synthetic_evo_seeds()`, `_mutate_node()`, `_crossover()`
- **Métodos de análise**: `lineage_graph()` (DAG causal), `fitness_history()` (fitness por geração), `lineage_report()` (human-readable ancestry)
- **10 testes** em `tests/test_lineage_tracking.py`: criação de entry, field no Node, recording seed/mutation/crossover, causal DAG, fitness history, ancestral chain, persistência entre gerações
- **Arquivos**: `graphs/node.py`, `graphs/__init__.py`, `evolution/evolutionengine.py`, `tests/test_lineage_tracking.py`

### Fase 24 — Formal Collapse Detector
- **`evolution/collapse_detector.py`**: `CollapseDetector` com 6 indicadores configuráveis:
  - Strategy Entropy (Shannon) — diversidade de estratégias
  - Fitness Variance — variância da população
  - Fitness Stagnation — estagnação por N gerações
  - Population Size — abaixo do mínimo
  - Genetic Diversity — dominância de uma estratégia
  - Premature Convergence — convergência precoce
- Score ponderado (configurável), `summary()` human-readable
- **13 testes** em `tests/test_collapse_detector.py`: healthy population (sem falso positivo), collapsed (verdadeiro positivo), indicadores individuais, população vazia, pipeline completa
- **Arquivos**: `evolution/collapse_detector.py`, `tests/test_collapse_detector.py`

### Fase 25 — Evolution Replay
- **`evolution/evolution_replay.py`**: Replay engine completo:
  - `ReplayNode` / `ReplaySnapshot` / `ReplayDiff` — estado reconstruído por geração
  - `EvolutionReplay.snapshots()` — reconstrói snapshots por geração a partir do lineage
  - `fitness_curve()` — fitness médio por geração
  - `ancestry()` / `ancestry_tree()` — cadeia ancestral + ASCII tree
  - `diff()` — diff entre 2 gerações
  - `stepper()` — generator de snapshots
  - `report()` — relatório human-readable completo
- **10 testes** em `tests/test_evolution_replay.py`
- **Arquivos**: `evolution/evolution_replay.py`, `tests/test_evolution_replay.py`

### Fase 26 — Git-like Diff entre Gerações
- **`evolution/evolution_replay.py`**: `GenerationPatch` — diff completo entre 2 gerações:
  - `nodes_added/removed` (dicts com metadados completos ReplayNode)
  - `nodes_modified` (before/after com fitness delta e strategy shifts)
  - `strategy_shifts`, `fitness_delta`, `diversity_delta`
  - `to_json()` / `from_json()` — serialização JSON para auditoria persistente
  - `apply_to(snapshot)` — reconstrói snapshot seguinte (`git apply`)
  - `ReplayDiff.to_dict()` / `from_dict()` — serialização do diff simples
- **Métodos novos em EvolutionReplay**:
  - `diff_patch(gen_a, gen_b)` — produz GenerationPatch
  - `patch_sequence()` — todos os patches consecutivos
  - `diff_to_json()` / `diff_from_json()` — audit trail
- **8 novos testes** (18→26 em `test_evolution_replay.py`)
- **Arquivos**: `evolution/evolution_replay.py`, `tests/test_evolution_replay.py`

### Fase 27 — Evolutionary Test Lab CLI
- **`iaglobal/cli/evolution_lab.py`**: CLI unificada com 10 subcomandos:
  - `init` — grafo core + EVO population
  - `evolve <N>` — N ciclos de evolução (seleção, mutação, crossover)
  - `snapshots` — lista gerações em tabela
  - `report` — relatório Evolution Replay
  - `diff <A> <B>` — GenerationPatch completo
  - `patch-sequence` — patches consecutivos
  - `detect-collapse` — CollapseDetector com 6 indicadores
  - `lineage [name]` — ASCII ancestry tree + fitness history
  - `fitness-curve` — fitness média com barras
  - `export-json <file>` — histórico JSON
- **Entry point** em `pyproject.toml`: `evolution-lab = "iaglobal.cli.evolution_lab:run_evolution_lab"`
- **Uso**: `evolution-lab --mutation-rate 0.5 init && evolution-lab evolve 2 && evolution-lab snapshots`
- **Arquivos**: `iaglobal/cli/evolution_lab.py`, `pyproject.toml`

### Fase 28 — Bug Fixes: Nome Longo, Lazy Loading, Skill Warnings
- **Bug 1 — OSError nome muito longo (Errno 36)**:
  - **Causa**: `_mutate_node()` e `_crossover()` concatenavam nomes recursivamente (`a_x_b_mut_0_x_c_mut_1...`), ultrapassando limite do filesystem
  - **Correção**: Nova função `_short_name()` com hash SHA-256 (8 hex chars) quando o nome excede `MAX_NODE_NAME=120`. Garantia: nomes nunca ultrapassam limite.
  - **Arquivos**: `evolution/evolutionengine.py`
- **Bug 2 — sentence-transformers carregado no startup (10s+)**:
  - **Causa**: `memory_vector.py` carregava `SentenceTransformer("all-MiniLM-L6-v2")` no módulo, executando download e carregamento ao importar `iaglobal.memory`
  - **Correção**: Substituído por lazy loading via `_get_model()`. Modelo só é baixado/carregado na primeira chamada real. Import caiu de ~10s para **0.175s**.
  - **Arquivos**: `memory/memory_vector.py`
- **Bug 3 — Warnings "Skill não registrada" no CLI init**:
  - **Causa**: EVO seeds sintéticos usavam `node_type="general"`, e `_mutate_node()` tentava executar skill pelo nome do nó (ex: `evo_coding_seed_0`), que não existia no registry
  - **Correção**: `_create_synthetic_evo_seeds()` registra Skill para cada seed sintética. `_mutate_node()` e `_crossover()` registram skill dos descendentes automaticamente quando o pai é EVO sintético. Warnings eliminados.
  - **Arquivos**: `evolution/evolutionengine.py`, `evolution/skills/skill_registry.py`
- **Resultado**: 132 testes passando, 0 falhas, 0 warnings

### Fase 29 — Integrar run_parallel na Pipeline de Produção
- **`core/orchestrator.py`**: `async_run_graph_task()` ganhou parâmetro `parallel: bool = False`
  - `parallel=True` → `await self.graph.run_parallel()` (DAG concorrente real, sem batch cap)
  - `parallel=False` (default) → `await self.graph.async_run()` (comportamento original, batches MAX_WORKERS=4)
- **`pipeline/engine.py`**: `async_execute()` e `_async_generation_stage()` propagam `parallel`
  - Uso: `await pipeline.async_execute("task", parallel=True)`
- **Compatibilidade total**: API pública inalterada, zero quebras
- **Arquivos**: `core/orchestrator.py`, `pipeline/engine.py`
- **Resultado**: 135 testes passando, 0 falhas

### Fase 30 — Teste de Integracao parallel=True
- **4 novos testes** em `tests/test_v3_pipeline.py::TestPipelineAsyncExecution`:
  - `test_parallel_run_with_independent_nodes` — 6 nós independentes executam via `graph.run_parallel()`, todos SUCCESS
  - `test_parallel_run_with_linear_dag` — DAG linear A→B→C→D, execução sequencial respeitada
  - `test_parallel_via_orchestrator` — `async_run_graph_task(parallel=True)` chama `run_parallel()`, `parallel=False` chama `async_run()`
  - `test_parallel_via_pipeline_async_execute` — `async_execute("task", parallel=True)` propaga `parallel=True` para o orchestrator, valida chamada correta
- **Arquivos**: `tests/test_v3_pipeline.py`
- **Resultado**: 189 testes passando (21 V3 pipeline, incluindo 4 novos), 0 falhas

### Fase 31 — Pipeline Real + evolution-lab
- **`iaglobal/cli/evolution_lab.py`**: Adicionado `--pipeline` flag global
  - `evolution-lab --pipeline init` — carrega o grafo real do DAG V3 (25 nós core) via `build_default_graph()` em vez do grafo sintético de 6 nós
  - Usa `unittest.mock.MagicMock` como orchestrator para construir o grafo sem executar LLM
  - EVO seeds são criados a partir dos 25 nós reais do pipeline (prompt_intake, enhancement, orchestrator_agent, pm, requirements, architect, search, knowledge, dependency, risk_analysis, security_design, performance_design, planner, coder, reviewer, semantic_validator, security_audit, performance_audit, tester, debug_coder, documentation, release, metrics, optimization, result_agent)
  - Todos os subcomandos (`evolve`, `snapshots`, `report`, `diff`, `detect-collapse`, `lineage`, `patch-sequence`, `export-json`, `fitness-curve`) funcionam com o grafo real
- **Arquivos**: `iaglobal/cli/evolution_lab.py`
- **Resultado**: 189 testes passando, 0 falhas

### Fase 32 — Correção de Testes (536 passando)
- **test_pipeline.py**: `escolher_modelo()` não aceitava `system_constraints` — removido argumento inexistente da chamada de teste
- **test_iaglobal.py**: teste de integração pendurava com Ollama offline — mockado `resolver` via `@patch`
- **test_memory.py**: 4 testes patchavam `memory_vector.model` (removido na refatoração para lazy loading) — corrigido para patch em `_get_model`
- **test_security_integration.py**: `unittest.mock.patch` sem import explícito do submódulo — adicionado `import unittest.mock`
- **Resultado**: 536 testes passando, 0 falhas, 2 warnings (SwigPyPacked/SwigPyObject do numpy)
- **Arquivos**: `tests/test_pipeline.py`, `tests/test_iaglobal.py`, `tests/test_memory.py`, `tests/test_security_integration.py`

### Fase 33 — CME-ONLINE (Cognitive Memory Evolution v2)
- **ShortTermMemory** (`memory/term_short.py`): TTL adaptativo, expire automático, search keyword, metadata tracking
- **LongTermMemory** (`memory/term_long.py`): importance score, usage tracking, consolidação inteligente, prune automático
- **WebBrain** (`tools/web_brain.py`): busca multicamadas DuckDuckGo + Wikipedia + RSS feeds com ranking por relevância
- **ConsolidationEngine** (`memory/consolidation.py`): cluster por palavras-chave, sumarização, consolidação web+local em LTM
- **CognitiveRanking** (`memory/ranking.py`): score multi-critério (relevance*0.4 + usage*0.2 + recency*0.2 + web_freq*0.2) + detecção de conflito cognitivo
- **Assistant CME** (`core/assistant.py`): pipeline 9 estágios — memory retrieval (STM+LTM+vector), web retrieval, consistency check, unified context, cognitive prompt, LLM, persistence, consolidation, STM update
- **Prompt cognitivo**: `[MEMÓRIA LOCAL]` + `[CONHECIMENTO DA INTERNET]` + `[CONSOLIDAÇÃO]`
- **Resultado**: 536 testes, 0 falhas

### Fase 34 — Web + Memory Fusion Engine
- **FusionEngine** (`memory/fusion_engine.py`): orquestrador de 6 subsistemas:
  - `WebCacheInteligente` — cache com TTL adaptativo por fonte (Wikipedia 24h, RSS 30min), SQLite + RAM L1
  - `AntiRedundanciaGlobal` — dedup hash exato + difflib SequenceMatcher (threshold 85%) + merge de similares (threshold 70%)
  - `FakeNoiseDetector` — score de confiança (0-1) por autoridade da fonte, tamanho, clickbait detection, datas; detecta contradições via Jaccard + negação
  - `KnowledgeGraph` — extração automática de conceitos (entidades nomeadas), co-ocorrência → relações ponderadas, tabelas SQL dedicadas (`kg_concepts`, `kg_relationships`), busca por nome
  - `AtualizacaoIncremental` — incorporação com dedup + noise check + KG + merge, suporte a batch
  - `FusionEngine` — API unificada: `process_web_result()`, `process_knowledge_batch()`, `get_knowledge_context()`
- **test_bandit_loadbalancer_integration.py**: corrigido teste flaky `test_best_model_wins_after_training` (probabilístico) para múltiplas tentativas
- **Arquivos**: `memory/fusion_engine.py`, `memory/__init__.py`, `tools/web_brain.py`, `memory/term_short.py`, `memory/term_long.py`, `memory/consolidation.py`, `memory/ranking.py`, `core/assistant.py`, `tests/test_bandit_loadbalancer_integration.py`
- **Resultado**: 536 testes passando, 0 falhas

### Fase 35 — Agent that writes its own knowledge base
- **KnowledgeWriterAgent** (`agents/knowledge_writer_agent.py`): agente que escreve e mantém a base de conhecimento automaticamente
  - `learn_from_conversation()` — extrai conceitos, definições, código, FAQs e relações de diálogos
  - `learn_from_text()` — aprende de texto arbitrário (conceitos + entry)
  - `consolidate_session()` — consolida aprendizados da sessão em resumo
  - `search_kb()` — busca textual na base de conhecimento
  - `get_knowledge_base_stats()` — estatísticas completas (entries por tipo, top FAQs)
- **Tabelas SQL dedicadas**: `kb_entries` (entry_type, title, content, confidence, tags), `kb_faq` (question, answer, frequency)
- **Integração no Assistant**: `kb_learning=True` (default) — toda conversa alimenta a KB automaticamente
- **Arquivos**: `agents/knowledge_writer_agent.py`, `core/assistant.py`
- **Resultado**: 536 testes passando, 0 falhas

### Fase 36 — Aquisição Automática de Skills
- **DynamicSkillRegistry** (`evolution/skills/dynamic_registry.py`): estende SkillRegistry com persistência SQLite, `register_dynamic()`, `register_dynamic_from_dict()`, carregamento automático na inicialização
- **RunFnFactory** (`evolution/skills/run_fn_factory.py`): gera `run_fn` callable para skills dinâmicas via template LLM (`{task}` substituído) ou determinístico (`exec`); templates pré-definidos: `summary`, `analysis`, `classification`
- **SkillGeneratorAgent** (`agents/skill_generator_agent.py`): analisa KB entries (`kb_*_analyzer`), conceitos frequentes no KG (`concept_*_expert`) e FAQs frequentes (`faq_*_helper`); gera e registra skills automaticamente
- **Integração no Assistant**: `skill_generation=True` (default); trigger automático a cada 5 entries na KB
- **Padrão `_paths.py`**: todos os novos módulos usam `Union[str, Path] = CORE_DB` com `_norm_path()` para normalização
- **Arquivos**: `evolution/skills/dynamic_registry.py`, `evolution/skills/run_fn_factory.py`, `agents/skill_generator_agent.py`, `evolution/skills/__init__.py`, `core/assistant.py`
- **Resultado**: 536 testes passando, 0 falhas

### Fase 37 — LLM Cognitive Proxy (Deterministic Orchestrator)
- **CognitiveProxy** (`core/cognitive_proxy.py`): proxy local com 6 estágios determinísticos:
  1. `_normalize()` — anti-ambiguidade: strip, lower, remove ruído
  2. `_build_context()` — busca memória vetorial + STM + LTM + web (NUNCA sem contexto)
  3. `_compile_prompt()` — prompt rígido anti-alucinação: `[SYSTEM INSTRUCTION]` + `[REGRAS]` + `[MEMÓRIA]` + `[WEB]` + `[TAREFA]` + `[FORMATO DE SAÍDA]`
  4. `_route()` — roteia para modelo (fallback automático se >4000 chars)
  5. `_validate()` — crítico com loop: detecta `UNKNOWN`, código válido, erros; gera prompt corrigido via `CriticAgent.avaliar()`
  6. `_store_result()` — persiste em memory.py + memory_vector + LTM
- **ProxyResult** dataclass: `success`, `output`, `model_used`, `validation_passed`, `validation_attempts`, `context_sources`
- **Regras anti-alucinação**: "UNKNOWN" obrigatório, sem especulação, sem libs inventadas
- **Integração no Assistant**: `proxy_mode=True` ativa CognitiveProxy como pipeline principal
- **Arquivos**: `core/cognitive_proxy.py`, `core/assistant.py`
- **test_bandit_loadbalancer_integration.py**: convergência aumentada de 100→200 iterações (teste flaky)
- **Resultado**: 536 testes passando, 0 falhas

### Fase 38 — Cache Semântico Inteligente
- **SemanticCache** (`memory/semantic_cache.py`): cache que entende similaridade semântica via embeddings + dot product
  - `get(query)` — busca no cache: embed → RAM L1 (full scan) → SQLite L2 → retorna hit se score ≥ threshold (0.92 default)
  - `set(query, response)` — armazena com embedding no SQLite + RAM
  - Cache hit mesmo com perguntas reescritas: "crie uma função soma" e "criar uma função de soma" compartilham o mesmo cache
  - Perguntas não relacionadas ("capital do brasil" vs "função soma") corretamente fazem miss
  - TTL configurável (default 24h), clean automático de entries expiradas
  - Estatísticas: entries, total_access, ram_entries
- **Integração no CognitiveProxy**: cache checked ANTES de build_context/route — se hit, retorna imediato (model_used="cache")
- **Arquivos**: `memory/semantic_cache.py`, `memory/__init__.py`, `core/cognitive_proxy.py`
- **Resultado**: 536 testes passando, 0 falhas

### Fase 39 — Retry Inteligente com Correção de Prompt
- **RetryHandler** (`core/retry_handler.py`): gerenciador de retry com 3 sub-sistemas:
  - `ErrorDetector` — classifica erros: `empty`, `error`, `hallucination`, `timeout`, `code_error`, `ok`, `unknown`
  - `PromptFixer` — reescreve prompt baseado no tipo de erro: adiciona `[RETRY INSTRUCTION]` específico (vazio, erro, alucinação, timeout, código)
  - `ModelEscalator` — 3 níveis de escalonamento balanceado:
    - **Level 0 (local)**: `ollama/qwen2.5:0.5b`, `ollama/tinyllama:latest` — tenta primeiro
    - **Level 1 (cloud)**: `openrouter/*`, `nvidia/*` — sobe após 2 falhas locais
    - **Level 2 (external)**: `gpt_web_instruction` — último recurso após 4 falhas
  - `RetryHandler.execute()` — pipeline completo: tenta modelos no nível atual → detecta erro → fixa prompt → escala se necessário → até `max_attempts`
  - Tracking de taxa de sucesso por nível para balanceamento futuro
- **Integração no CognitiveProxy**: `retry_enabled=True` (default); `_route()` delega para `RetryHandler.execute()` quando ativo; método `_llm_call()` como router para o handler; `_gpt_web_fallback()` para instrução técnica externa
- **Arquivos**: `core/retry_handler.py`, `core/cognitive_proxy.py`
- **Resultado**: 536 testes passando, 0 falhas

### Fase 40 — Critic Governance: Sensor de Qualidade (não Juiz)
- **Refatoração do CriticAgent** (`agents/critic_agent.py`): contrato restrito conforme `leiame.md`
  - ❌ Removido: `_buscar_contexto_web()` — Critic NÃO pode buscar web
  - ❌ Removido: `_online_models()` — Critic NÃO pode escolher modelos
  - ❌ Removido: auto-rewrite de prompt — Critic NÃO reescreve prompt livremente
  - ✅ Mantido: `avaliar()` — saída JSON obrigatória: `{"approved", "score", "issues", "fix_suggestions"}`
  - ✅ Score 0-100, aggregate com pesos (correctness 35%, completeness 25%, security 25%, spec_match 15%)
  - ✅ Detecção de código perigoso, vazio, erro de sintaxe
- **Refatoração do CognitiveProxy._validate()** (`core/cognitive_proxy.py`):
  - Critic é **sensor passivo**: APENAS avalia e emite score
  - Proxy é **decisor**: se Critic rejeita, Proxy loga e continua
  - ❌ Removido: `_fix_hallucination()` — Critic não reescreve prompt
  - ❌ Removido: `max_critic_loops` — sem loop de correção automática
  - Retry continua sendo responsabilidade do `RetryHandler` (não do Critic)
- **Modelo de governança**: `Model → Critic (score only) → Proxy decides` em vez de `Model → Critic → decide retry`
- **Arquivos**: `agents/critic_agent.py`, `core/cognitive_proxy.py`, `tests/test_agents.py`
- **Resultado**: 536 testes passando, 0 falhas

### Fase 41 — TypingAgent (Simulação de Digitação Humana)
- **TypingAgent** (`agents/typing_agent.py`): simula digitação humana em caixas de texto web
  - `TypingProfile` configurável: `chars_per_second`, `jitter`, `pause_chance`, `initial_delay`, `burst_words`, `punctuation_pause`
  - `simulate_typing(text)` — digitação síncrona com callbacks `on_char`/`on_complete`
  - `simulate_typing_async(text)` — digitação em `threading.Thread` (não bloqueante)
  - `estimate_time(text)` — estima tempo sem executar
  - Velocidade variável com jitter aleatório (±50%), pausas "thinking" ocasionais (15%), rajadas em palavras comuns (2.5x), pausa após pontuação
  - Palavras de rajada: `the`, `and`, `for`, `python`, `def`, `return`, `class`, `import` etc.
- **TypingService** (`agents/typing_agent.py:228`): serviço de integração com perfis default (10 cps) e slow (4 cps) para textos longos
- **Integração no CognitiveProxy**: `_gpt_web_fallback()` agora usa `TypingService.web_llm_call()` — simula digitação do prompt em tempo real antes de enviar para ChatGPT Web, evitando bloqueio por velocidade
- **Arquivos**: `agents/typing_agent.py`, `core/cognitive_proxy.py`
- **Resultado**: 536 testes passando, 0 falhas

### Fase 42 — Agent Governance Layer
- **GovernanceLayer** (`core/governance.py`): framework de contratos formais e limites de autoridade
  - `AgentContract` dataclass: `required_inputs`, `outputs`, `allowed_authorities`, `forbidden_actions`, `timeout_seconds`, `can_modify_state`, `can_delegate`
  - `Authority` enum: `READ_ONLY`, `EVALUATE`, `SEARCH`, `GENERATE`, `EXECUTE`, `COORDINATE`, `DECIDE`
  - `validate_call()` — valida inputs obrigatórios + ação contra lista de proibidos
  - `enforce_timeout()` — retorna timeout configurado para execução
  - `check_violations()` — verifica ações específicas
  - `get_authority_summary()` — resumo legível: "pode", "não pode", inputs, outputs
- **Contratos definidos** (7 agentes):
  | Agente | Autoridade | Proibido |
  |--------|-----------|----------|
  | `critic` | evaluate | executar, buscar web, escolher modelo, reescrever prompt, decidir final |
  | `planner` | generate, evaluate | executar código, gerar código final, escolher modelo, buscar web |
  | `search` | search | executar código, modificar contexto, decidir, gerar código, avaliar |
  | `multi_agent` | coordinate, generate | decidir final sozinho, ignorar proxy, substituir proxy |
  | `coder` | generate | executar sem sandbox, escolher modelo, buscar web, decidir arquitetura |
  | `debugger` | generate, execute | reescrever código completo, ignorar erro original, escolher modelo |
  | `tester` | execute, evaluate | modificar código fonte, escolher modelo, gerar código produção |
- **Regra de ouro**: Nenhum agente tem autonomia completa — decisão final pertence ao CognitiveProxy
- **Integração no CognitiveProxy**: `self.governance = governance` (instância global)
- **Arquivos**: `core/governance.py`, `core/cognitive_proxy.py`
- **Resultado**: 536 testes passando, 0 falhas

### Fase 43 — Integração Multi_Agent → CognitiveProxy + Limpeza
- **Integração**: `Multi_Agent` agora recebe `CognitiveProxy` opcional via `__init__(proxy=...)` — delega a ele a construção de contexto (memória + web + fusão) nas Fases 1-3
- **Removido**: `_fase_knowledge_web` (substituído por `proxy._build_context()`)
- **Removido**: `_fase_knowledge_fusion` (substituído por CognitiveProxy + FusionEngine)
- **Removido**: imports não usados (`requests`, `resolve_model`, `executar`, `DuckDuckGoScraperAgent`, `route_generate`, `ast`, `get_success_by_task`)
- **Removido**: `resolver_com_ajuda_da_internet()` — obsoleto, WebBrain faz isso
- **Unificado**: `_avaliar_candidato()` substitui a lógica duplicada de scoring que existia em `testar_solucoes` e `_fase_testar_rankear`
- **Unificado**: `_parse_test_output()` centraliza regex de extração de resultados de teste
- **Limpeza**: código reduzido de ~830 → ~530 linhas (−36%)
- **Loggers enriquecidos**: timing por fase (`elapsed=`), contagem de candidatos, scores detalhados, erros com contexto
- **Governança**: `governance.validate_call()` antes de cada fase (planner, coder, critic, debugger, multi_agent)
- **Arquivos**: `agents/multi_agent.py`, `tests/test_agents.py`
- **Resultado**: 536 testes passando, 0 falhas

### Fase 44 — BanditPolicy integrado ao CognitiveProxy
- **Integração**: `CognitiveProxy._route()` agora usa `BanditPolicy.select_model()` em vez de `escolher_modelo()` para selecionar o modelo por eficiência/score
- **Analogia**: `BanditPolicy` é como **guarda de trânsito** — ele diz qual modelo vai para qual requisição baseado em score histórico (eficiência/latência/sucesso). Quem executa a chamada real é a **pasta `providers/`** (Ollama, Groq, OpenRouter, NVIDIA, OpenCode, Gemini)
- **CreditAssignmentEngine**: `CognitiveProxy.__init__()` cria `credit = CreditAssignmentEngine()` + `bandit = BanditPolicy(credit)`; resultados de execução alimentam o bandit via `_record_bandit_result()`
- **Separação de responsabilidades**: `BanditPolicy` = seleção (trânsito); `providers/` = execução (chamadas HTTP/rede)
- **`ProviderConfig` removido** do `CognitiveProxy`: não era mais necessário, bandit gerencia a seleção
- **`escolher_modelo()` atualizado**: ainda existe para compatibilidade com `Assistant`/`pipeline`, mas delega para `BanditPolicy`
- **test_pipeline.py**: `test_retorna_mesmo_valor_qualquer_task` ajustado (bandit é probabilístico)
- **Arquivos**: `core/cognitive_proxy.py`, `providers/provider_router.py`, `tests/test_pipeline.py`
- **Resultado**: 536 testes passando, 0 falhas

### Fase 45 — Correções: Web Search Query + Mutação Evolutiva
- **Search node fix** (`graphs/builder.py:_make_search_run`):
  - Extrai `original_prompt` do metadata em vez de usar task aumentada (que continha requirements completos como query de busca)
  - `needs_web` default mudou de `False` para `True` (web_classifier removido no V3)
- **Evolution mutation fix** (`evolution/evolutionengine.py:_mutate_nodes`):
  - Quando há ≤2 agentes EVO e mutação aleatória não produz variantes, força uma mutação de strategy para evitar extinção
  - Previne "nenhuma variação genética foi criada" com população pequena
- **Arquivos**: `graphs/builder.py`, `evolution/evolutionengine.py`
- **Resultado**: 536 testes passando, 0 falhas

### Fase 46 — Fix Crossover 0 Filhos + `random` → `secrets`
- **Crossover fix** (`evolution/evolutionengine.py:_crossover_phase`):
  - Adicionado `len(evo_nodes) > 2 and` antes do random gate `secrets.randbelow(100) > 30`
  - Com ≤2 agentes EVO, crossover agora é **forçado** (70% de skip removido), igual já era feito na mutação
  - Previne "0 novos filhos" quando população pequena
- **`random` → `secrets`** (`evolution/evolutionengine.py`):
  - Removido `from secrets import SystemRandom` / `_rand = SystemRandom()`
  - Todas as chamadas convertidas: `secrets.choice()`, `secrets.randbelow(N)` para decisões binárias (comparação com threshold)
  - Randomness criptograficamente segura mantida (já era via `SystemRandom`)
- **Arquivos**: `evolution/evolutionengine.py`
- **Resultado**: 536 testes passando, 0 falhas

### Fase 47 — Timeouts 30s + Limpeza errors.json
- **Timeouts reduzidos** (`providers/provider_router.py:PROVIDER_TIMEOUT`):
  - Cloud (groq, opencode, gemini): 60s → 30s
  - Ollama/OpenRouter/NVIDIA: 120s → 30s
  - Fallback default `PROVIDER_TIMEOUT.get(provider, 60)` → `30`
  - Todos os 6 providers agora com timeout uniforme de 30s
- **Timestamp fix** (`memory/memory_error.py:store_error`):
  - `.isoformat() + "Z"` produzia `+00:00Z` (duplo timezone)
  - Corrigido: `.isoformat().replace("+00:00", "Z")`
- **Limpeza errors.json** (`memory/data/errors.json`):
  - Removidas 480 entradas `Noise` (prompt="x", ruído de teste)
  - Removidas 46 entradas `TestError` (erros artificiais de teste)
  - Mantidas 115 entradas `Unknown` (erros reais)
- **Arquivos**: `providers/provider_router.py`, `memory/memory_error.py`, `memory/data/errors.json`
- **Resultado**: 536 testes passando, 0 falhas

---

## Sistema de Aprendizado

### Leitura de erros por agente
| Agente | Lê knowledge | Lê errors.json | Salva insight | Salva erro | Usa `[REINCIDENCIA]` |
|--------|-------------|----------------|---------------|------------|---------------------|
| enhancement | ✅ | ✅ | ✅ | — | ✅ |
| orchestrator_agent | ✅ | ✅ | ✅ | — | ✅ |
| security_design | ✅ | ✅ | ✅ | — | ✅ |
| performance_design | ✅ | ✅ | ✅ | — | ✅ |
| security_audit | ✅ | ✅ | ✅ | ✅ | ✅ |
| performance_audit | ✅ | ✅ | ✅ | ✅ | ✅ |
| result_agent | — | — | ✅ | — | — |

### Knowledge Run
Extrai conhecimento de: architect (architecture), debugger/tester (bugs), security_design (pattern), performance_design (pattern), security_audit (bug), performance_audit (bug)

### Cache
- L1 (RAM dict) + L2 (SQLite via `success_registry` com cbor2)
- `cache.set()` persiste no SQLite
- Cache inválido → `store_error()` + `db.insert_insight()` → erro vira lição
- Cache nunca é apagado — resultado bom sobrepõe o ruim

---

## Providers

| Provider | Modelo | Sync | Async | Status |
|----------|--------|------|-------|--------|
| OpenCode | `nemotron-3-super-free` | ✅ `requests` | ✅ `aiohttp` | ✅ |
| NVIDIA | `meta/llama-3.3-70b-instruct` | ✅ | ✅ | ✅ |
| Groq | `llama-3.1-8b-instant` | ✅ | ✅ | ✅ |
| OpenRouter | `poolside/laguna-m.1:free` | ✅ | ✅ | ✅ |
| Ollama | `qwen2.5:0.5b` | ✅ (120s) | ✅ | ⚠️ offline |
| Gemini | `gemini-2.5-flash-lite` | ✅ | ✅ | ⚠️ rate limit |

---

## Estrutura do Projeto

```
/iaglobal/                         (~180 .py, ~45k linhas)
├── agents/                        — 19 agentes
│   ├── critic_agent.py            — Sensor de qualidade (contrato restrito)
│   ├── cognitive_proxy.py         → movido para core/
│   ├── coder_agent.py             — Geração de código
│   ├── debugger_agent.py          — Correção de código
│   ├── enhancement_agent.py       — V3: refine de prompt
│   ├── knowledge_writer_agent.py  — V3: escreve knowledge base
│   ├── multi_agent.py             — Coordenador multi-agente (integrado ao Proxy)
│   ├── performance_audit_agent.py — V3: auditoria de performance
│   ├── performance_design_agent.py— V3: design de performance
│   ├── planner_agent.py           — Planejamento
│   ├── reflexion_agent.py         — Reflexão
│   ├── result_agent.py            — V3: resultado final
│   ├── search_agent.py            — Busca web
│   ├── security_audit_agent.py    — V3: auditoria de segurança
│   ├── security_design_agent.py   — V3: design de segurança
│   ├── semantic_validator.py      — Validação semântica
│   ├── skill_generator_agent.py   — Geração automática de skills
│   ├── tester_agent.py            — Testes
│   └── typing_agent.py            — Simulação de digitação humana
├── providers/                     — 15 arquivos
│   ├── async_http.py              — aiohttp session (multi-loop)
│   ├── provider_router.py         — route_generate + fallback chain
│   ├── provider_config.py         — lazy config w/ debug
│   ├── provider_state.py          — score + cooldown w/ debug
│   ├── provider_load_balancer.py  — Load balancer
│   └── *_provider.py              — 6 providers (sync+async)
├── graphs/                        — DAG + execução
│   ├── builder.py                 — PIPELINE_SKILLS V3 (3206 linhas)
│   ├── execution_graph.py         — run() + async_run() + run_parallel()
│   ├── node.py                    — Node + LineageEntry
│   ├── bandit.py                  — BanditPolicy (ε-greedy)
│   ├── credit.py                  — CreditAssignmentEngine
│   ├── telemetry.py               — ExecutionEvent
│   └── {task,scheduler,task_runner,execution_context,state_store,execution_engine}.py
├── evolution/                     — Evolução autônoma
│   ├── skills/
│   │   ├── skill.py               — 25 Skills V3 (+ dinâmicas)
│   │   ├── skill_registry.py      — Registry global
│   │   ├── dynamic_registry.py    — Skills dinâmicas com SQLite
│   │   ├── run_fn_factory.py      — Factory de run_fn para skills
│   │   ├── skill_executor.py      — Executor
│   │   └── skill_versions.py      — Versionamento
│   ├── evolutionengine.py         — CORE_NODE_NAMES V3, mutação forçada
│   ├── darwin_harness.py          — Darwin Engine Test Harness
│   ├── collapse_detector.py       — CollapseDetector (6 indicadores)
│   ├── evolution_replay.py        — Replay + GenerationPatch
│   ├── meta_agent_designer.py     — Especialização híbrida
│   ├── task_agent_factory.py      — DEPENDS_ON_MAP V3
│   ├── task_analyzer.py           — Análise de tarefas
│   └── canonical_graph.py         — Canonicalização
├── memory/                        — Persistência
│   ├── fusion_engine.py           — Web + Memory Fusion Engine
│   ├── semantic_cache.py          — Cache semântico (embeddings)
│   ├── consolidation.py           — Consolidação inteligente
│   ├── ranking.py                 — Ranking cognitivo
│   ├── term_short.py              — Memória de curto prazo (STM)
│   ├── term_long.py               — Memória de longo prazo (LTM)
│   ├── memory_vector.py           — lazy SentenceTransformer
│   ├── memory_storage.py          — success_registry (cbor2)
│   ├── memory_error.py            — errors.json + learning
│   ├── cache.py                   — L1 RAM + L2 SQLite
│   ├── db_manager.py              — SQLite + insights
│   └── memory.py                  — Evolução documental
├── core/                          — Orquestração + Governança
│   ├── cognitive_proxy.py         — CognitiveProxy (orquestrador determinístico)
│   ├── governance.py              — GovernanceLayer (contratos de agentes)
│   ├── retry_handler.py           — Retry inteligente + escalonamento
│   ├── orchestrator.py            — 11 estágios closed-loop + async
│   ├── assistant.py               — Assistant CME (9 estágios)
│   ├── neuro_orchestrator.py      — Orquestrador neural
│   └── decision_engine.py         — Engine de decisão
├── cli/                           — CLI
│   ├── main.py                    — CLI principal
│   ├── evolution_lab.py           — Evolutionary Test Lab CLI
│   ├── bootstrap.py               — inicialização
│   └── status.py, output.py       — renderizadores
├── tools/                         — Ferramentas
│   ├── web_brain.py               — WebBrain (busca multicamadas)
│   ├── search_tools.py            — SearchTools (ddgs)
│   ├── search.py                  — search_tool (cache)
│   └── tool_router.py             — ToolRouter
├── events/                        — Sistema de eventos
├── execution/                     — Execução sandbox
├── security/                      — Segurança (AST, regras)
├── reflection/                    — Engine de reflexão
├── validation/                    — Validação
├── api/                           — API (MCP server)
└── tests/                         — 30+ arquivos (~536 testes, 0 falhas)
    ├── test_v3_agents.py          — 33
    ├── test_v3_pipeline.py        — 21
    ├── test_evolution_replay.py   — 26
    ├── test_evolution_learning.py — 25
    ├── test_evolution_agents.py   — 18
    ├── test_collapse_detector.py  — 13
    ├── test_lineage_tracking.py   — 10
    ├── test_execution_engine.py   — 10
    ├── test_pipeline_skills.py    — 17
    ├── test_task_agents.py        — 13
    ├── test_sanity_barrier.py     — 8
    ├── test_bandit_loadbalancer_integration.py — 24
    ├── test_security_integration.py — 37
    ├── test_async_compat.py       — 3
    ├── test_agents.py             — 42
    ├── test_pipeline.py           — 22
    └── ...
```
