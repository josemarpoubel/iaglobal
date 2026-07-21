# 🧬 Linguagem Ubíqua — iaglobal

> Versão: 1.0 (Julho 2026)
> Mantido por: auditoria_arquitetural.py

---

## Contexto e Pipeline

| Termo | Significado | Onde |
|---|---|---|
| **ExecutionContext** | Contexto canônico de **um domínio específico**. Existem 4 ocorrências legítimas: pipeline (composição de sub-contextos), graph (estado operacional), evolution (replay), cognition.awareness (estado cognitivo). **Não unificar.** | `pipeline/context/protocol.py`, `graphs/execution_context.py`, `evolution/execution_context.py`, `cognition/awareness/models.py` |
| **NodeContext** | Projeção derivada do `ExecutionContext`, consumida por um nó do grafo. Contém `sections` (conteúdo tipado) e `budget`. | `pipeline/context/protocol.py` |
| **NodeSection** | Unidade atômica de contexto: `id`, `title`, `content` (tupla tipada), `priority`. | `pipeline/context/protocol.py` |
| **TokenBudget** | Orçamento de tokens por seção. Controla quanto de cada seção chega ao LLM. | `pipeline/context/protocol.py` |
| **ContextProvider** | Constrói um `NodeContext` a partir de um `ExecutionContext`. Declara dependências via `requires`. | `pipeline/context/protocol.py` |
| **ProjectionProvider** | Provider declarativo que projeta campos do `ExecutionContext` em `NodeSections` via `SectionSpec`. | `pipeline/context/providers/base.py` |
| **SectionSpec** | Especificação declarativa: de onde ler (`source` dot-path), qual prioridade, qual orçamento. | `pipeline/context/providers/base.py` |
| **Serializer** | Transforma `NodeContext` em string (prompt). Estratégia permutável (`ContextSerializer` markdown, `JSONSerializer`). | `pipeline/context/serializers/` |
| **ProviderRegistry** | Registro de `ContextProviders` por nome de nó. Auto-import via lazy load. | `pipeline/context/provider_registry.py` |

---

## Motores e Provedores

| Termo | Significado | Onde |
|---|---|---|
| **Provider (LLM)** | Adaptador para modelo externo (OpenAI, Ollama, Groq, etc.). | `providers/provider_router.py` |
| **BanditPolicy** | Gatekeeper de chamadas LLM. Aplica PSC (Protocolo de Soberania do Crítico), membrana seletiva, ε-greedy. | `graphs/bandit.py` |
| **PSC** | Protocolo de Soberania do Crítico. Apenas `critic` pode chamar `bandit.generate()`. Demais nós são confinados. | `graphs/bandit.py` |
| **CriticAgent** | Único nó com acesso a modelos cloud. Arbitra delegações de outros agentes via `arbitrar_geracao()`. | `agents/critic_agent.py` |

---

## Recuperação e Imunidade

| Termo | Significado | Onde |
|---|---|---|
| **EvolutionRecoveryEngine** | Substituição de agente que falhou repetidamente. Gera clone com herança epigenética. **Não confundir com ImmuneApoptosis.** | `core/` (renomear de `ApoptosisEngine`) |
| **ImmuneApoptosisEngine** | Eliminação de agente considerado patológico pelo sistema imunológico. Drain → snapshot → registry cleanup. | `immunity/apoptosis_engine.py` |
| **MHC Detector** | Fingerprinting + anomaly scoring de módulos Python. | `immunity/mhc_detector.py` |
| **PathogenAnalyzer** | Detecção de code injection e imports maliciosos. | `immunity/pathogen_analyzer.py` |
| **MetabolicPruner** | TTL pruning + deduplicação de memórias. | `immunity/metabolic_pruner.py` |
| **ImmuneOrchestrator** | Integra 5 camadas imunes em um pipeline único. | `immunity/immune_orchestrator.py` |

---

## Memória e Metabolismo

| Termo | Significado | Onde |
|---|---|---|
| **MissionContext** | Fonte única de verdade sobre a missão. Domínio, entidades, restrições, prioridades. | `pipeline/context/protocol.py` |
| **MissionAnalyzer** | Análise heurística (zero LLM) do prompt para extrair domínio, entidades, restrições. | `pipeline/mission.py` |
| **ShortTermMemory** | Memória de curto prazo (STM). | `memory/term_short.py` |
| **LongTermMemory** | Memória de longo prazo (LTM). | `memory/term_long.py` |
| **ObsidianVault** | Memória subconsciente persistente com ciclo REM. | `obsidian/` |
| **MetabolicDataAdapter** | Ponte CBOR2 → JSON para dados metabólicos. | `storage/metabolic_adapter.py` |
| **HomocysteinePool** | Pool de candidatos à metilação. | `metabolism/homocysteine_pool.py` |
| **MethylationEngine** | Ciclo de metionina → SAMe → homocisteína → regeneração. | `metabolism/methylation_engine.py` |

---

## Grafos e Execução

| Termo | Significado | Onde |
|---|---|---|
| **ExecutionGraph** | DAG que orquestra a execução dos nós do pipeline. | `graphs/execution_graph.py` |
| **Node** | Nó do DAG. Possui `node_id`, `name`, `run`, `acquire`/`release`. | `graphs/node.py` |
| **AcetylcholineBus** | Barramento de comunicação assíncrona entre agentes. | `graphs/comms/acetylcholine_bus.py` |
| **Apoptosis** | Morte celular programada (ver EvolutionRecovery vs ImmuneApoptosis). | — |
| **Autophagy** | Limpeza evolutiva de componentes degradados com reciclagem de aprendizado. | — |

---

## Símbolos com Nomes Duplicados (documentação arquitetural)

Para cada símbolo que aparece em mais de um módulo, a classificação oficial está abaixo.
Mantido pelo `auditoria_arquitetural.py`.

```
ExecutionContext      ✅ DOMÍNIOS DISTINTOS   (4 ocorrências)
ProviderRegistry      ✅ DOMÍNIOS DISTINTOS   (2 ocorrências)
FusionEngine          ✅ DOMÍNIOS DISTINTOS   (3 ocorrências)
RewardAggregator      ✅ DOMÍNIOS DISTINTOS   (2 ocorrências)
MetaLearner           ✅ DOMÍNIOS DISTINTOS   (2 ocorrências)
ValidationResult      ✅ DOMÍNIOS DISTINTOS   (4 ocorrências)
EventType             ✅ DOMÍNIOS DISTINTOS   (2 ocorrências)
EventBus              ✅ DOMÍNIOS DISTINTOS   (2 ocorrências)
ApoptosisEngine       ⚠️ COLISÃO DE VOCABULÁRIO  (2 ocorrências) → renomear
```

---

## Termos proibidos ou ambíguos

| Termo | Motivo | Alternativa |
|---|---|---|
| **Manager** | Pouco semântico; qualquer classe pode ser manager | `Orchestrator`, `Controller`, `Coordinator` |
| **Handler** | Responsabilidade indefinida; vira catch-all | `Processor`, `Listener`, `Responder` |
| **Engine** | Usar **somente** quando controla ciclo completo com estado | Especificar o ciclo: `RecoveryEngine`, `FusionEngine` |
| **Base** | Evitar sem necessidade; tende a acumular código órfão | `Abstract`, `Protocol`, ou nome do contrato |
| **Helper** | Catch-all de funções sem domicílio fixo | Colocar no módulo de domínio correspondente |
| **Util** / **Utils** | Mesmo problema de Helper | Quebrar em módulos de responsabilidade única |
| **Manager** | (repetido intencionalmente) É o pior nome de todos | Prefira nomes que descrevem o que o objeto *faz* |
| **Processor** | Use com cuidado; prefira verbos mais específicos | `Validator`, `Transformer`, `Analyzer` |

### Regra prática

Se você precisa de um `Manager` ou `Handler`, provavelmente falta um conceito de domínio.
Em vez de criar um Manager, pergunte: que *processo de negócio* este código implementa?

---

## Como atualizar

1. Execute `python -m iaglobal.auditoria_arquitetural`
2. Para cada nova colisão, classifique e adicione a entry na base de conhecimento em `auditoria_arquitetural.py` (`_KNOWN_DISTINCT` ou `_COLLISION_VOCABULARY`)
3. Atualize esta tabela se o termo fizer parte da linguagem ubíqua
