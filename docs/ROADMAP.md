# ROADMAP — iaglobal: Evolução Real

**Princípio:** Só o CriticAgent chama LLM externo. Todo o resto aprende de memória local + metabolismo interno.

---

## Fase 1 — Bootstrapping do Chappie (4 módulos)
Ativar os 4 componentes do Chappie no startup do sistema.

| # | Tarefa | Arquivos | Verificação |
|---|--------|----------|-------------|
| 1.1 | `IVMAxiom` instanciado no bootstrap | `chappie/ivm_axiom.py` → `cli/bootstrap.py` | `iaglobal status` mostra IVM dos agentes |
| 1.2 | `VacuumDaemon` rodando em background | `chappie/vacuum_daemon.py` | `memory_swap/` populado com STM→LTM |
| 1.3 | `ErrorEnricher` como decorator nos agents | `chappie/error_enricher.py` → `agents/agent_base.py` | Erros viram notas no Obsidian |
| 1.4 | `LineageGuardian` validando DNA em runtime | `chappie/lineage_guardian.py` → `graphs/node.py` | Nodes com DNA inválido são bloqueados |

---

## Fase 2 — Roteamento Local First
Agentes consultam memória/obsidian antes de chamar LLM.

| # | Tarefa | Arquivos | Verificação |
|---|--------|----------|-------------|
| 2.1 | `MemoryFirstRouter` — busca local antes de LLM | `chappie/memory_first_router.py` (novo) | Logs mostram "cache hit" vs "LLM call" |
| 2.2 | Agents comuns usam `_call_local()` em vez de `_call_llm()` | `agents/agent_base.py` | 80% das chamadas são locais |
| 2.3 | Somente `CriticAgent._avaliar_multidimensional` chama modelos grandes | `agents/critic_agent.py` | Só critic bate em Groq/NVIDIA |

---

## Fase 3 — Metabolismo Evolutivo Ativo
Conectar os ciclos metabólicos que estão dormentes.

| # | Tarefa | Arquivos | Verificação |
|---|--------|----------|-------------|
| 3.1 | `HomocysteinePool` integrado no pipeline | `evolution/metabolism/homocysteine_pool.py` | Erros acumulados disparam autofagia |
| 3.2 | `ErrorEnricher` alimenta `HomocysteinePool` | `chappie/error_enricher.py` → `evolution/metabolism/` | Erros enriquecidos viram homocisteína |
| 3.3 | Nodes `no_evolution_*` adicionados ao DAG | `graphs/edges.py` + `graphs/registry.py` | Grafo mostra nós de evolução |

---

## Fase 4 — EvolutionRuntime Autônomo
Sistema evolui sozinho em background sem intervenção.

| # | Tarefa | Arquivos | Verificação |
|---|--------|----------|-------------|
| 4.1 | `EvolutionRuntime.start()` chamado no bootstrap | `evolution/evolutionruntime.py` → `cli/bootstrap.py` | `iaglobal status` mostra "Running: yes" |
| 4.2 | `HandlerEvolver` conectado ao `ErrorEnricher` | `evolution/handler_evolution.py` | AST de handlers muta por padrão de erro |
| 4.3 | `FusionEngine` rodando fusão de DNA completa | `evolution/fusion_engine.py` | Agentes fundem traits periodicamente |

---

## Fase 5 — Loop Fechado (Autopoiese)
Sistema auto-sustentável: gera, avalia, aprende, evolui sem humano.

| # | Tarefa | Arquivos | Verificação |
|---|--------|----------|-------------|
| 5.1 | Pipeline executa sem chamar LLM externo (exceto critic) | todo o sistema | `iaglobal run` funciona offline |
| 5.2 | Evolution gera novos skills automaticamente | `evolution/metacognition/skill_generator.py` | Skills novos aparecem no registry |
| 5.3 | Apoptose remove agents degradados sem intervenção | `immunity/apoptosis_engine.py` | Agents ruins morrem sozinhos |

---

## Critério de Sucesso

```
Antes:  79 nós × LLM externo = 79 chamadas de API por execução
Depois: 1 nó (critic) × LLM externo + 78 nós × memória local
        → 98.7% redução de dependência externa
        → Sistema funciona offline
        → Aprende com cada execução
        → Evolui sem humano no loop
```
