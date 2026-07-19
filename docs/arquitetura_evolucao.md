# 🧬 Arquitetura de Evolução — iaglobal

## Visão Geral

A evolução no iaglobal opera em **DOIS PLANOS**: síncrono (dentro do pipeline) e assíncrono (background time-driven).

```
Pipeline (event-driven)
         │
         ├──► evolution_trigger (nó do grafo) ──► EvolutionEngine.evolve() [SÍNCRONO]
         │                                         │
         │                                         ├─ canonicalize()
         │                                         ├─ seed_evo_population()
         │                                         ├─ select_survivors()
         │                                         ├─ mutate_nodes()
         │                                         ├─ crossover_phase()
         │                                         ├─ run_darwin_harness()
         │                                         └─ evolve_handlers()
         │
         └─► set_task(prompt) [notificação passiva]
               │
               ▼
         EvolutionRuntime (time-driven, background) ──► loop _async_loop()
                                                          │
                                                          └─► Estratégias: Fast (30s) / Deep (120s)
```

**Descoberta crítica (2026-07-18)**: O nó `evolution_trigger` executa ciclos evolutivos completos **dentro do próprio pipeline**, não apenas via loop de background. Evidência: log da run mostra `Crossover`, `Handler-EVO`, `Ciclo de evolução 0 finalizado` ocorrendo durante execução do `iaglobal run`.

---

## Componentes Principais

### 1. EvolutionRuntime (`evolution/evolutionruntime.py` — 230 linhas)
- **Singleton** com loop assíncrono em background
- **Intervalo adaptativo**: 30-120s conforme estratégia
- **Gate**: `EVOLUTION_AUTO=1` (variável de ambiente)
- **Backoff dinâmico**: reduz intervalo se estável, aumenta se falha

### 2. EvolutionEngine (`evolution/evolutionengine.py` — 1077 linhas)
- **Motor genético completo** (usado por BOTH: trigger síncrono + background):
  - Canonicalização de DAG (dedup, consolidação, ordenação)
  - Seed de população evolutiva
  - Seleção por truncamento (pressure configurable)
  - Mutação com 5 operadores AST
  - Crossover com 3 estratégias
  - Darwin Harness (ambiente adversarial)
  - Handler Evolution (código-fonte dos nós)

### 3. EvolutionTrigger (`evolution/metacognition/evolution_trigger.py` — ~140 linhas)
- **Nó do pipeline** (`graphs/nodes/no_evolution_trigger.py`)
- **Chamada direta**: `engine = EvolutionEngine(graph=graph); await engine.evolve()`
- **Condições de disparo**:
  - Score baixo (< threshold)
  - SAMe disponível na pool metabólica
  - Lacunas detectadas pelo evaluator/gap_analyzer
- **Impacto**: Ciclo evolutivo completo ocorre **durante** o request do usuário

### 4. HandlerEvolver (`evolution/handler_evolution.py` — 546 linhas)
- **Mutação de handlers** via AST:
  - `_ScoreThresholdMutator`: ajusta thresholds numéricos
  - `_SourceTupleMutator`: modifica tuplas de source
  - `_LogLevelMutator`: altera níveis de log
  - `_IntParamMutator`: Tweaks em parâmetros int
  - `_BoolFlagMutator`: inverte booleanos
- **Crossover**:
  - `_SourceCrossover`: combina sources de ambos pais
  - `_ThresholdCrossover`: troca thresholds entre handlers

### 5. DarwinHarness (`evolution/darwin_harness.py` — 280 linhas)
- **Ambiente adversarial dinâmico**
- **Métricas de evolução**: `EvolutionMetrics`
- **Invariantes**: hard/soft checks (muitos ainda stubs)
- **SimulationRecorder**: snapshot e detecção de regressão

### 6. CanonicalGraph (`evolution/canonical_graph.py` — 315 linhas)
- **Deduplicação** por chave funcional (node_type + strategy)
- **Consolidação** de dependências transitivas
- **Ordenação topológica** com detecção de ciclos
- **Hash determinístico** SHA3-256

---

## Fluxo de Execução Detalhado

### Caminho Síncrono (dentro do pipeline)
```
user prompt → pipeline.execute()
  │
  ├─► Stage 1: INIT (build graph)
  ├─► Stage 2: MEMORY (cache lookup)
  ├─► Stage 3: GENERATION (DAG execution)
  │     │
  │     └─► ... → evaluator → gap_analyzer → evolution_trigger
  │                                      │
  │                                      └─► EvolutionTrigger.trigger()
  │                                            │
  │                                            ├─ if score < threshold:
  │                                            │   └─► EvolutionEngine.evolve() [BLOQUEANTE]
  │                                            │        ├─ seed → mutate → crossover → darwin_harness
  │                                            │        └─► ~2-5 segundos (depende do LLM)
  │                                            │
  │                                            └─ return {evolution_triggered: bool, reason: str}
  │
  ├─► Stage 4: VALIDATION (AST)
  ├─► Stage 5: REQUIREMENT CHECK
  └─► ... → COMPLETE
```

**Impacto na latência**: Quando o trigger dispara, o usuário espera o ciclo evolutivo completo terminar antes de receber a resposta.

### Caminho Assíncrono (background)
```
EvolutionRuntime._async_loop():
  while running:
    if EVOLUTION_AUTO=1:
      await evolver.evolve_async(strategy)  # ← Independente do pipeline
      await asyncio.sleep(interval)
```

**Execução**: A cada 30-120s (Fast/Deep), mesmo sem requests do usuário.

---

## Estratégias de Evolução

| Estratégia | Intervalo | Mutation Rate | Crossover | Selection Pressure | Uso |
|------------|-----------|---------------|-----------|-------------------|-----|
| FastEvolutionStrategy | 30s | 0.30 | 0.50 | 0.30 (top 30%) | Background (descoberta) |
| DeepEvolutionStrategy | 120s | 0.05 | 0.10 | 0.70 (top 70%) | Background (refinamento) |
| Trigger Síncrono | Imediato | 0.30 (Fast) | 0.50 (Fast) | 0.30 (Fast) | Pipeline (correção de lacunas) |

**Nota**: O trigger síncrono chama `engine.evolve()` sem passar `strategy` → fallback para `FastEvolutionStrategy()` (linha 428 do `evolutionengine.py`).

---

## Estados e Persistência

- **Estado evolutivo**: `iaglobal/memory/data/cache/evolution_state.json`
- **Hash do grafo**: recalculado a cada ciclo (ambos caminhos)
- **Geração**: incrementada após cada ciclo completo
- **WorkDirs**: limpas após cada ciclo (`_clean_workdirs()`)
- **Linhagem**: registrada em `node.lineage` (SHA3-512 + marker hereditário)

---

## Segurança e Validação

- **ASTGateway**: único ponto de AST parsing (obrigatório)
- **SkillExecutor**: valida se nó pode ser clonado (`can_execute()`)
- **ExecutionPolicy**: nós `SINGLE_RUN` não são evoluídos
- **Quarantine**: skills em quarentena são excluídas
- **Genesis Tribunal**: valida LINEAGE_MARKER antes de evoluir

---

## Pontos de Refatoração Identificados

1. **Acoplamento síncrono não documentado**: `evolution_trigger` chama `EvolutionEngine.evolve()` diretamente — impacto na latência do pipeline não era óbvio
2. **Async-first inconsistente**: métodos têm wrappers síncronos (`_run_evolution_step`, `_seed_evo_population`) que poderiam ser nativamente async
3. **CPU-bound em thread**: `copy.deepcopy` e AST mutation rodam em `asyncio.to_thread` — considerar pool dedicado
4. **DarwinHarness stubs**: `check_hard_invariants`, `generate_adversarial_task` retornam vazio — invariantes não estão realmente protegidas
5. **MetabolicLifecycle não integrado**: importado mas não executado no loop principal
6. **Extensão de arquivo bugada**: `_detect_extension()` sempre retorna `.py` como default, ignora conteúdo texto quando pedido `.txt`

---

## Recomendações Atualizadas

1. **Documentar acoplamento síncrono**: `evolution_trigger` já é um mecanismo válido — tornar explícito no README e diagramas
2. **Adicionar métricas de latência**: exportar IVM + tempo de ciclo evolutivo síncrono para observabilidade
3. **Persistir linhagem**: salvar `lineage_graph()` e `lineage_report()` em disco para auditoria pós-execução
4. **Warm-up de modelo**: pré-aquecer Ollama antes de ciclos (cold-load = ~59s para GLM4.7-1.2B)
5. **Timeout ajustável**: `PROVIDER_TIMEOUT=120` recomendado para ciclos com LLM síncronos
6. **Corrigir `_detect_extension()`**: adicionar detecção de conteúdo texto vs código, respeitar pedido de extensão do usuário
7. **Considerar flag de bypass**: permitir `--no-evolution` para requests que não precisam de ciclo síncrono

---

## Anexo: Evidência da Run (2026-07-18 20:06:07)

```log
[EVO-TRIGGER] Ciclo evolutivo disparado: Score baixo (0) — necessário evoluir agentes (SAMe restante: 10)
🧬 Crossover: 'evolution_methylation_x_immune_check_0' = evolution_methylation x immune_check (strategy=general)
🧬 Crossover: 'evolution_methylation_x_evo_metrics_seed_0_mut_0_0' = ...
🧬 7 híbrido(s) adicionado(s)!
[HANDLER-EVO] Nenhum handler elegível para evolução
🏁 Ciclo de evolução 0 finalizado com sucesso.
[EVO] Passo finalizado: 19 nós evo ativos, geração 1
✅ [ASYNC] Ciclo evolutivo concluído com sucesso (strategy=fast).
[EVOLUTION_TRIGGER] Ciclo evolutivo disparado: score=0 | motivo=Score baixo (0) — necessário evoluir agentes
```

**Nós envolvidos**: `evolution_trigger`, `evolution_committee`, `evaluator`, `gap_analyzer` — todos no grafo do pipeline, não no loop de background.

---

*Documento gerado em 2026-07-18 — Auditoria de evolução iaglobal*
*Correção aplicada: incluído acoplamento síncrono via evolution_trigger (descoberto nesta sessão)*

---

## Anexo: Correções de Latência Aplicadas (2026-07-18)

### Problema Descoberto
O nó `evolution_trigger` executava chamadas síncronas com `fcntl.flock` dentro do pipeline, bloqueando o event loop durante requisições de usuário:
- `same_pool.spend()` → `mutate_sync()` → `fcntl.flock(LOCK_EX)`
- `same_pool.recharge()` → `mutate_sync()` → `fcntl.flock(LOCK_EX)`
- `meta_evolver.record_trial()` → `_save()` → `mutate_sync()` → `fcntl.flock(LOCK_EX)`

### Solução Aplicada
Envoltório em `asyncio.to_thread()` para todas as chamadas bloqueantes em `iaglobal/evolution/metacognition/evolution_trigger.py`:

```python
# Antes (bloqueava o event loop)
same_pool.spend("evolution_trigger", COST_CREATE_SKILL)
same_pool.recharge("evolution_trigger")
meta_evolver.record_trial(params, improvement, task_type)

# Depois (executa em thread pool)
await asyncio.to_thread(same_pool.spend, "evolution_trigger", COST_CREATE_SKILL)
await asyncio.to_thread(same_pool.recharge, "evolution_trigger")
await asyncio.to_thread(meta_evolver.record_trial, params, improvement, task_type)
```

### Impacto
- **Antes**: Sob contenção (CLI + UI acessando o mesmo pool), o event loop inteiro travava esperando `flock` liberar
- **Depois**: `flock` ainda bloqueia a thread, mas o event loop continua servindo outras requisições
- **Latência**: Ciclo evolutivo síncrono ainda adiciona 2-5s ao request, mas não bloqueia outros requests concorrentes

### Arquivos Modificados
- `iaglobal/evolution/metacognition/evolution_trigger.py`: +1 import `asyncio`, 3 chamadas envoltas em `to_thread()`

---

*Atualização: 2026-07-18 20:30 — Correções de latência aplicadas*

---

## Anexo: Descoberta E2E — Modelo Desviando Conteúdo (2026-07-18 22:45)

### Cenário testado
```bash
iaglobal run "Explique o protocolo HTTP em português. Não gere código."
```

### Resultado observado
- `project001/output.json` — **extensão correta** para o conteúdo gerado
- Conteúdo: `{'performance_design_report': {'load_profile': ..., 'rendering_strategy': ..., 'score': {...}, ...}}`
- **Não é texto plano sobre HTTP**: é um relatório estruturado de performance

### Conclusão
- `_detect_extension()` **está funcionando corretamente** — detectou dict Python → `.json`
- `save_result_artifact()` **está funcionando corretamente** — salvou em `project001/output.json`
- `_safe_relative_path()` **foi exercitada** — arquivo dentro do diretório do projeto
- **Problema real**: o modelo GLM4.7-1.2B retornou conteúdo não solicitado (relatório de performance)

### Causa provável
- `prompt_improver` está reescrevendo o prompt antes do modelo (foi o "melhor código" na run anterior)
- Ou o modelo está ignorando a instrução "não gere código"
- Ou o agente `performance_design` está sendo chamado indevidamente

### Ação futura (não bloqueante para esta refatoração)
- Investigar qual nó do DAG produziu `final_output` (linha 675 do `engine.py`)
- Verificar se o `prompt_improver` está alterando o prompt do usuário
- Considerar adicionar validação de tipo de conteúdo antes da persistência

---

*Registrado em 2026-07-18 — E2E de persistência validado; desvio de conteúdo é problema separado*
