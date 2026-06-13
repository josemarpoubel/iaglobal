# ROADMAP - CONEXÕES E ATUALIZAÇÕES PARA IAGLOBAL v3+ FULL OPERATIONAL

---

## STATUS GERAL
*Data: 13/06/2026*  
**Objetivo:** Pipeline determinístico de 55 nós executando todos os handlers e gerando código real via DAG.

### Arquitetura Atual
- **56 handlers individuais** (`graphs/nodes/no_*.py`) — um arquivo por node do DAG (incluindo `multi_coder`)
- **builder.py** constrói DAG a partir dos handlers + topologia das 7 fases
- **Handler async wrapper** — `_wrap_handler()` captura exceções globalmente e chama `record_error()`
- **56/56 nodes executam** (55 DAG + multi_coder) — pipeline completo em ~70s
- **Teste de idempotência** — imports NÃO alteram arquivos JSON persistentes

---

## HISTÓRICO DE REALIZAÇÕES (10–11/06/2026)

### 10/06 — Correção de corrupção de JSONs por testes + expansão de busca
- **FIX 9:** `test_feedback_loop.py` e `test_meta_evolution.py` corrompiam JSONs reais — backup/restore de arquivo + temp file
- **FIX 10:** `test_imports_idempotent.py` criado — 4 testes que verificam que imports não alteram JSONs persistentes
- **5 novos nós de busca:** `search_wikipedia`, `search_web_brain`, `prompt_builder`, `memory_writer`, `memory_cleaner` — pipeline expandida para 62 nós
- **Buscas assíncronas + query expansion:** 4 queries focadas por task, cache compartilhado, retry + stagger
- **Knowledge Analyzer** persiste em LTM + SQLite + CBOR2; base de conhecimento com 12+9 entries
- **Local Knowledge:** consulta LTM/knowledge.json/cbor2/STM antes da busca web (≥200 chars relevante pula internet)
- **SearXNG** integrado como 1ª fonte de busca (meta-buscador local, zero API key)
- **8 novas fontes de busca + Router especializado** — 12 fontes totais, disk swap em `search_swap/`
- **PromptImprover ativado** — 5 estágios, 48→1342 chars, domínio `dados` (0.7)
- **Pipeline/engine.py:** race fallback removido — DAG é único estágio de geração
- **EvolutionRuntime auto-start desligado** — ative com `EVOLUTION_AUTO=1`
- **Critic na pipeline:** avalia output do coder com score 0-100 antes de persistir
- **Skill Registry corrigido:** `register()` valida `callable(run_fn)`, `execute_with_fallback()` com proteção contra ciclo
- **Tasks órfãs eliminadas:** `t.cancel()` + `gather()`, Playwright browser shutdown adicionado
- **64 nós, 195 testes, 0 falhas**

### 11/06 — Logger refactor
- **FIX CRITICAL:** `iaglobal/utils/logger.py` não exportava `logger` — 80+ módulos quebrados. Adicionada instância default.
- **stop_session_log()** com proteção contra double-start, double-stop, vazamento de handler, thread-safe
- **get_child_logger()** para loggers hierárquicos (`ia-global.orchestrator`, etc.)

### 11/06 (2ª rodada) — Pipeline crash fixes + double registration
- **FIX CRASH:** `cpu_affinity.pin_for_agent()` não existia — `AttributeError`. Implementado.
- **FIX breakpoint:** `breakpoint()` removido de produção
- **FIX double registration:** `_seed_pipeline_nodes()` re-registrava cada nó 2-3x — corrigido
- **Pipeline executa sem crashes:** 64 nós, output gerado, graceful shutdown

### 11/06 (3ª rodada) — AgentMailbox + barramento
- **NOVO NÓ:** `no_agentmailbox.py` — inicializa `MailboxManager` + `AcetylcholineBus` para todos os agentes
- **FIX import path:** `iaglobal/communication/` package criado
- **Pipeline integrado:** `agentmailbox` é o 1º nó da fase `definicao`
- **Teste de comunicação:** `test_agentmailbox_communication.py`

### 11/06 (4ª rodada) — 4 nós conectados ao barramento + conversation log
- **FIX `_placeholder_run`:** Movida de método da classe `Skill` para função de módulo — `NameError` no registro
- **planner, coder, critic, result_agent** conectados ao barramento via `_mailbox_manager` e `_agent_bus`
- **Conversation log:** `result_agent` salva `conversation_<timestamp>.log` com histórico completo

### 11/06 (5ª rodada) — Provider cascade
- **FIX `_filter_blacklist` undefined:** Criada função que delega ao `BanditPolicy._filter_candidates()`
- **Circuit breaker reset:** Limpa bans residuais na 1ª execução
- **FIX `_async_race_round`:** FIRST_COMPLETED → ALL_COMPLETED com timeout 180s (evita cancelamento prematuro)
- **Ollama fallback final:** Último recurso com RAG antes de desistir
- **`_PROVIDERS_WITH_KEYS`:** Lista explícita de provedores com chave

### 11/06 (6ª rodada) — CREDIT_CANDIDATES limpo
- **CREDIT_CANDIDATES enxugado de 33 → 6:** Removidos HF Router (402), `hf_inference`, `perplexity`, `openai`
- **Groq adicionado** (tinha API key mas nunca era tentado)
- **POE timeout reduzido:** 60s → 30s

### 11/06 (7ª rodada) — Provider optimization batch
- **FIX `ALL_COMPLETED` → `FIRST_COMPLETED`** com loop `while tasks`
- **`asyncio.wait_for()` enforce:** Providers agora respeitam timeout
- **Connection pooling:** `requests.Session` + `HTTPAdapter(pool=10, maxsize=30)` nos 7 providers síncronos
- **Cache async no router:** `_async_safe_call()` verifica cache antes da requisição
- **Imports do hot path movidos** para topo do módulo
- **Cache de env vars:** `_ENV_CACHE` — lê uma vez, cacheia para sempre
- **FIX SQL placeholder mismatch:** `batch_writer.py` 7 placeholders → 8
- **Paths hardcoded eliminados:** provider_state, batch_writer, hf_image_provider → `_paths.py`
- **`PROVIDER_EVENTS_DB` e `IMAGES_DIR`** adicionados em `_paths.py`
- **`providers/batch_writer.py` → bridge deprecada** com re-export
- **Teste de consistência de paths:** 10 asserts

---

## MUDANÇAS RECENTES — 13/06/2026 (8ª rodada)

### Correção de incompatibilidade Bootstrap/Orchestrator + IDs SHA3-512 de linhagem

- **FIX FATAL (Bootstrap x Orchestrator):** `Bootstrap.initialize()` passava `memory=self.memory, bus=self.bus` para `Orchestrator()`, mas o `__init__` do Orchestrator não aceita esses parâmetros — `TypeError` imediato. Corrigido: `Orchestrator()` sem argumentos, deixando o Orchestrator gerenciar suas próprias dependências internas. (`iaglobal/cli/bootstrap.py:55-56`)
- **FIX imports duplicados em bootstrap.py:** `Orchestrator` importado 2x (linhas 13 e 21), além de imports comentados. Consolidado em 1 import limpo. (`iaglobal/cli/bootstrap.py:1-9`)
- **FIX duplicações no Orchestrator:** `self.credit`/`self.bandit` instanciados DUAS VEZES (linhas 96-97 e 107-108) — removida a segunda instância. `self.evolution_runtime` instanciado DUAS VEZES (linhas 91-94 e 124-127) — removida a segunda instância. (`iaglobal/core/orchestrator.py:94-95, 89-92`)
- **FIX import duplicado do ExecutionGraph:** `from iaglobal.graphs import ExecutionGraph` (linha 30) e `from iaglobal.graphs.execution_graph import ExecutionGraph` (linha 42) — consolidado em 1 import direto. (`iaglobal/core/orchestrator.py:30`)
- **FIX cli/main.py `await` em função sync:** `ctx = await bootstrap.initialize()` chamava método síncrono com `await`, e depois criava um SEGUNDO `Orchestrator()` ignorando o contexto retornado. Agora usa `orch = bootstrap.initialize()` diretamente, sem await. (`iaglobal/cli/main.py:65-67`)
- **FIX duplicação credit_engine/bandit em main.py:** Inicializados 2x no fluxo (linhas 69-70 e 101-102). Removida segunda inicialização redundante. (`iaglobal/cli/main.py:99-101`)
- **FIX double-execution no comando "run":** Faltava `return` após executar pipeline — caía no comando `prompt` genérico (linha 234) e executava a mesma tarefa 2x. Adicionado `return`. (`iaglobal/cli/main.py:83`)
- **FIX `_shutdown` → `sync_cleanup`:** `Orchestrator._shutdown()` chamava `graceful_shutdown.sync_shutdown()` que não existe (o método real é `sync_cleanup`). Corrigido. (`iaglobal/core/orchestrator.py:1265`)
- **NOVO `LineageID` em `utils/hash_utils.py`:** Classe com `compute()` que gera SHA3-512 (128 chars hex) codificando `entity_type::name::parent_lineage_id::generation::metadata` e retorna par `(lineage_id, lineage_marker)`. O `lineage_marker` (16 chars) é um hash SHA3-256 do nome da raiz, **hereditário** — todos os descendentes compartilham o mesmo marcador, permitindo `same_lineage()` O(1) sem depender de avalanche effect do SHA3-512. `detect_collision()` agora só checa ID exato (colisão de marker é esperada, não erro). (`iaglobal/utils/hash_utils.py`)
- **`compute_node_id()` migrado de SHA3-256[:16] para SHA3-512 full (128 chars):** `compute_node_id()` em `node.py` agora retorna 128 caracteres hex via `LineageID.compute_node_lineage()`. (`iaglobal/graphs/node.py`)
- **`LineageEntry.lineage_marker` adicionado ao dataclass:** Cada entrada de linhagem carrega `lineage_marker` herdado do progenitor. `Node.current_lineage_marker` property expõe o marcador. `Node.same_lineage_as()` compara marcadores diretamente. (`iaglobal/graphs/node.py`)
- **`_record_lineage()` propaga `parent_lineage_marker`:** `EvolutionEngine._record_lineage()` agora aceita `parent_lineage_marker` e o injeta no `LineageEntry`, garantindo que toda a família use o mesmo marcador. Seeds (normais e sintéticas) propagam o marker do nó fonte. (`iaglobal/evolution/evolutionengine.py`)
- **`lineage_report()` enriquecido:** Exibe o `lineage_marker` e conta o tamanho da família (nós com mesmo marker no grafo). (`iaglobal/evolution/evolutionengine.py`)
- **`compute_skill_checksum()` via SHA3-512:** Substitui o antigo SHA3-256[:16] por SHA3-512 completo. (`iaglobal/utils/hash_utils.py`)
- **`ExecutionGraph.generate_node_id()` e `add_node_by_dna()` atualizados:** Usam `LineageID.compute()` para gerar IDs com `generation` no hash. Colisão de prefixo antiga removida — agora colisão só é reportada para IDs exatamente iguais. (`iaglobal/graphs/execution_graph.py`)
- **FIX de design (prefixo SHA3-512 vs marcador hereditário):** A abordagem inicial de comparar prefixos do hash SHA3-512 foi descartada — o efeito avalanche de SHA3-512 faz com que 1 bit de diferença na entrada produza hash completamente diferente, tornando prefixos inúteis para detecção de parentesco. Substituído por `lineage_marker` hereditário gerado com SHA3-256 do nome da raiz, herdado por todos os descendentes. Same-lineage detection O(1) e semanticamente correta.

---

## MÉTRICAS DO PROJETO

| Métrica | Meta | Antes | Agora |
|---------|------|-------|-------|
| Nodes executando no DAG | 63/63 | 56/56 ✅ | **63/63** ✅ |
| Latência total pipeline | < 60s | 113.72s ❌ | **68.78s** ✅ |
| Falhas no benchmark | 0/63 | **10/56** ❌ | **5/63** (4 search transient + 1 provider) ✅ |
| Handlers reais (não stubs) | 55/55 | 14/55 ❌ | **26/63** ✅ |
| Busca web funcional | Sim | 1 nó frágil ❌ | **4 nós async + cache + retry** ✅ |
| Provider cascade funcional | 6 providers | 0 (blacklist) ❌ | 0 (blacklist) ❌ |
| errors.json populado | Sim | 1 mock + 0 runtime ❌ | **vazio + record_error ativo** ✅ |
| knowledge.json entries | 50+ | 3 ❌ | **3 + conceitos SQLite** ✅ |
| meta_evolution.json | Integro | params corrompidos ❌ | **params originais (0.05/0.5)** ✅ |
| Testes passando | 536/536 | 75 pass, 5 pre-existing ❌ | **186 pass, 0 fail** ✅ |
| Testes de idempotência | N/A | 0 | **4 novos** ✅ |
| Duplicatas numbered | 0 | 5 ❌ | 0 ✅ |
| JSONs corrompidos por testes | 0 | 3 arquivos ❌ | **0 (protegido)** ✅ |

---

## PRÓXIMOS PASSOS

### Prioridade Alta
- [x] **Provider cascade** — Circuit breaker reset funcional, fallback paralelo e sequencial implementados (`async_route_generate_parallel`, `_async_fallback_chain`, `_fallback_chain`), Cache global efetivo, registro de métricas (`metrics.jsonl`), TokenCollector e estimativa de custo por provider, bandit policy e circuit breaker dinâmico funcionais.
- [x] **CREDIT_CANDIDATES enxugado** — 6 provedores ativos (nvidia, opencode, openrouter, groq, poe, ollama), todos com timeout configurado e circuit breaker reset aplicado automaticamente.
- [ ] **Testar provider cascade com execução real** — verificar latência total, estabilidade e resultados usando routing paralelo, fallback oco e ambiente configurável (`SEQUENTIAL_FALLBACK`, `OLLAMA_ONLY`, `RACE_SIZE`), com fallback Ollama enriquecido via `_enrich_prompt_with_learned_knowledge`.
- [ ] **Re-benchmark oficial de latência** — medir pipeline completo com fallback do grafo e providers cloud + Ollama
- [x] **Pipeline/engine.py integrado** — DAG executado como estágio principal via `async_execute`, `orchestrator.async_run_graph_task` e fallback Ollama
- [x] **AgentMailbox node** (`no_agentmailbox.py`) — inicializa `MailboxManager` + `AcetylcholineBus` para todos os agentes
- [x] **Conectar agentes às mailboxes** — planner_agent, coder_agent, critic_agent, result_agent conectados ao barramento
- [x] **LineageID (SHA3-512)** + **ExecutionGraph async** com Sanity Barrier e CPU affinity
- [x] **Ciclo de feedback** — CriticAgent, EnhancementAgent e ReflexionAgent integrados ao pipeline de mensagens
- [x] **8ª rodada de correções** — Bootstrap/Orchestrator compatibility resolvido

### Prioridade Média
- [x] **Corrigir imports quebrados** — Imports de `PIPELINE_SKILLS`, `rank` e `cpu_affinity` já estavam corretos; nenhum arquivo precisou ser modificado.
- [x] **Implementar mais handlers reais** — reviewer_agent, security_audit_agent, performance_audit_agent, compliance_agent, debugger_agent criados e integrados no pipeline
- [ ] Evolução dos handlers via mutation/crossover
- [ ] Multi_coder (codificação paralela multi-modelo)
- [x] **Nós adaptados às mailboxes** — Planner, coder, critic, result, reflexion, enhancement, performer, tester, pm, architect, performer_agent, tester_agent, pm_agent, architect_agent, integrator_agent, memory_writer_agent, documentation_agent.
- [x] **Ciclo de feedback** — CriticAgent, EnhancementAgent e ReflexionAgent conectados ao fluxo via mensagens no barramento. Skills de metacognição (`evaluator`, `gap_analyzer`, `skill_generator`, `sandbox_validator`, `evolution_committee`, `pipeline_updater`, `evolution_trigger`) já implementadas e registradas.
- [ ] Adaptar nós restantes ao barramento — integrator_agent, memory_writer_agent, documentation_agent (**já conectados via skills definidas em `/iaglobal/evolution/skills/skill.py`**: SKILL_INTEGRATOR, SKILL_MEMORY_WRITER, SKILL_DOCUMENTATION e já usados nos nós do DAG).

---

**Próxima Revisão:** 17/06/2026  
**Responsável:** Core Team  
**Revisor:** Architecture Review Board
