# 🧬 iaglobal — Arquitetura do Sistema

## Sumário

1. [Visão Geral](#1-visão-geral)
2. [Princípios Fundamentais](#2-princípios-fundamentais-o-dna-do-sistema)
3. [Verificação Genômica (Genesis & Lineage)](#3-verificação-genômica-genesis--lineage)
4. [Sistema Imunológico](#4-sistema-imunológico)
5. [Ciclos Metabólicos (Pipeline de Dados)](#5-ciclos-metabólicos-pipeline-de-dados)
6. [Pipeline de Execução (DAG)](#6-pipeline-de-execução-dag)
7. [Motor Evolutivo (Genomic Reflection)](#7-motor-evolutivo-genomic-reflection)
8. [Leis Universais Aplicadas — Fusão, Simbiose, Vácuo, Ancestralidade](#8-leis-universais-aplicadas)
9. [Módulo Obsidian — Subconsciente](#9-módulo-obsidian--subconsciente)
10. [Comunicação Assíncrona](#10-comunicação-assíncrona)
11. [Validação sob Carga](#11-validação-sob-carga)
12. [Débito Técnico e Inconsistências Detectadas](#12-débito-técnico-e-inconsistências-detectadas)
13. [Vetor Evolutivo (Roadmap Consolidado)](#13-vetor-evolutivo-roadmap-consolidado)
14. [Apêndice A — Árvore Completa de Diretórios](#apêndice-a--árvore-completa-de-diretórios)
15. [Nota de Curadoria](#nota-de-curadoria)

---

## 1. Visão Geral

**iaglobal** é um sistema multi-agente assíncrono cuja arquitetura é modelada sobre ciclos de metabolismo celular (metilação, glutationa, autofagia, mitose, apoptose, epigenética, sinalização celular) em vez dos padrões convencionais de orquestração de agentes. Roda 100% em CPU (4 núcleos, sem GPU), usando Ollama como provider local de LLM com fallback para provedores em nuvem primeiro via `BanditPolicy`.

### Snapshot de status (conforme documento original)

| Métrica | Valor reportado | Observação |
|---|---|---|
| Testes de linhagem de DNA | 153/153 ✅ | Cobre genesis (6), agentes (32), nós (115), constante identity (1) |
| Sistema imunológico | "12 camadas ativas" | Ver §4 — a enumeração explícita no texto original lista apenas 5; a árvore de diretórios permite reconstruir a lista completa |
| Testes totais (marco "Zenith") | 724/724 | Depois ampliado para 832 após Fase 9 (+99) e Fase 12 (+9) |
| Hardware | CPU 4 núcleos, 0 GPU | — |
| Passos evolutivos | 107/107 → depois "116/107" | Ver §12, item 6 — número inconsistente no original |
| Estrutura de nós do DAG | "55 nós" (síntese inicial) → 115 nós (cobertura de testes) | Ver §12, item 1 — o projeto cresceu entre uma seção e outra do próprio documento |

---

## 2. Princípios Fundamentais (o DNA do sistema)

- **Async-first absoluto**: toda operação de I/O passa por `asyncio`; nada de chamadas bloqueantes no event loop principal.
- **`BanditPolicy` como portão único**: todo acesso a modelo de IA passa por ele — seleção de provider, circuit breaker, métricas de performance, atribuição de crédito, fallback chain.

🧬 Arquitetura Correta BanditPolicy e AgentBase:

AgentBase._call_llm() 
    ↓
BanditPolicy.select_and_generate()  ← SEMÁFORO AQUI!
    ↓
async_route_generate()  ← Apenas executa
    ↓
Provider

📦 FLUXO COMPLETO:

Agent (herda de AgentBase)
    ↓
await self._call_llm(prompt, task_type)
    ↓
BanditPolicy.generate()
    ├─ 1. Seleciona modelo (ε-greedy + pesos)
    ├─ 2. Adquire semáforo (controla concorrência)
    ├─ 3. Executa via async_route_generate()
    ├─ 4. Libera semáforo
    ├─ 5. Registra métricas no CreditAssignmentEngine
    └─ 6. Atualiza rewards do bandit
    ↓
Provider (Groq/NVIDIA/Ollama)

### 🧬 **3. Ciclo Metabólico de Cada Lógica**

#### **`async_route_generate_parallel`** → **Sistema Imunológico Inato**

```
📥 PROMPT
     ↓
🧠 BanditPolicy rank_models()
     ↓
🏎️ BATCH 1 (Top 3 providers em paralelo)
     ↓ (se falhar)
🏎️ BATCH 2 (Próximos 3)
     ↓ (se falhar)
🏠 FALLBACK: Ollama local
     ↓ (se falhar)
💥 RuntimeError: "Todos falharam"
```

**Metabolismo:** ATP 10:1 — máxima eficiência energética

**DNA:** Adaptabilidade + Paralelismo + Fallback local

---

#### **`async_route_generate`** → **Sistema Imunológico Adaptativo**

```
📥 PROMPT + MODELO
     ↓
🔒 Check OLLAMA_ONLY (sandbox)
     ↓ (se "auto")
🔄 Delega para async_route_generate_parallel
     ↓ (se modelo específico)
🎯 Provider direto (ex: "groq/llama-3.3")
     ↓ (se falhar)
🔁 Fallback chain (sequencial ou paralelo)
     ↓ (se falhar)
💥 RuntimeError: "Todos falharam"
```

**Metabolismo:** ATP 5:1 — menos eficiente, mas necessário para casos específicos

**DNA:** Determinismo + Controle manual + Sandbox

- **Modularidade radical (regra de ouro)**: `iaglobal/graphs/nodes.py` é um *proxy dinâmico* — nunca acumula lógica. Cada nó operacional vive em seu próprio arquivo `no_<nome>.py` dentro de `graphs/nodes/`, exportando uma função assíncrona `run_<nome>`.
- **Sistema imunológico multicamada**: `GlutathionePool`, `GlutathioneGuardrails` e `ImmuneResponse` como defesa contra "ROS" (erros, inputs maliciosos, cascatas de falha).
- **Memória dual-layer**: STM/LTM via `CognitiveProxy`, com integração ao vault Obsidian (`learning_system.py`) para memória de longo prazo entre sessões.

---

## 3. Verificação Genômica (Genesis & Lineage)

Cadeia de validação de identidade e integridade, do boot até a execução de cada agente individual — não é um hash-check simples, é um portão que impede que código não-derivado do DNA oficial entre no grafo de execução.

```
BOOT DO SISTEMA
       ↓
verifygenesis.py ──► SHA3-512 streaming hash (chunks de 64KB)
       ↓
identity.py ──► compara com GENESIS_HASH_OFFICIAL (constante congelada)
       ↓
test_dna_lineage.py ──► 153 testes parametrizados
       ↓
CAMADAS DE VERIFICAÇÃO CONTÍNUA
 • MHC Detector · EntropySentinel · AsyncViolationDetector · ApoptosisEngine
       ↓
EXECUÇÃO DE AGENTES/NÓS
       ↓
Cada arquivo deve carregar "# 🧬 LINEAGE_MARKER: <hash>" na primeira linha
```

**Componentes-chave:**

| Componente | Arquivo | Função |
|---|---|---|
| Tribunal de Genesis | `genesis/verifygenesis.py` | Compara hash do `evolutive.cbor` contra o `blueprint.cbor`; aborta o boot se divergir |
| Identidade congelada | `genesis/identity.py` | Define `GENESIS_HASH_OFFICIAL` |
| Verificação de linhagem | `genesis/test_dna_lineage.py` | Extrai `LINEAGE_MARKER` de cada arquivo e valida contra o hash oficial |

**Cobertura atual (153/153 passed):** arquivos genesis (6/6) · agentes (32/32) · nós executáveis (115/115) · constante identity (1/1).

**Por que isso importa para fusões entre agentes/repositórios:**
1. Todo agente/nó derivado do mesmo `LINEAGE_MARKER` compartilha identidade genômica — `FusionEngine`, `GenomicReflection` e `MetaSkillGenerator` operam sabendo que os parceiros não são "corpos estranhos".
2. O tribunal (`verifygenesis.py` + `test_dna_lineage.py`) funciona como um contrato de fusão pré-assinado.
3. `EvoAgent.replicate()` propaga o `lineage_marker` do pai para o filho automaticamente.
4. `ImmuneMemoryExchange` e o vault Obsidian compartilham "vacinas" apenas entre agentes de mesmo DNA.
5. Feature flags via `epigenetic_registry.py` mudam comportamento sem tocar no DNA base.

**Genesis Handshake Protocol** **mutação planejada:** handshake de Genesis entre nós remotos (SHA3-512 no lugar de certificados X.509) para permitir que repositórios clonados participem de uma rede global de agentes. implementado e testado:

- `iaglobal/communication/genesis_handshake.py` — protocolo de autenticação entre nós remotos via SHA3-512 + HMAC
- `tests/integration/test_genesis_handshake.py` — 8 testes simulativos passando

---

## 4. Sistema Imunológico

O texto original menciona "12 camadas ativas" mas só nomeia 5 explicitamente numa tabela. Reconstruindo a partir da árvore real de `immunity/` (Apêndice A), os módulos existentes são:

| Módulo | Caminho | Papel (conforme uso descrito no texto) |
|---|---|---|
| MHC Detector | `immunity/mhc_detector.py` | Fingerprints + anomaly scoring |
| Entropy Sentinel | `immunity/entropy_sentinel.py` **e** `security/entropy_sentinel.py` | Anti-manipulação / detecção de caos — ⚠️ existe em duplicidade, ver §12 |
| Async Violation Detector | `immunity/async_violation_detector.py` | Detecta blocking I/O em código async |
| Apoptosis Engine | `immunity/apoptosis_engine.py` | Eliminação limpa de nós corrompidos |
| Glutathione Pool / Guardrails | `immunity/glutathione_pool.py`, `glutathione_guardrails.py` | Defesa antioxidante contra ROS |
| Pathogen Analyzer | `immunity/pathogen_analyzer.py` | Detecção de código malicioso/injeção |
| Immune Memory Exchange | `immunity/immune_memory_exchange.py` | Compartilha "vacinas" entre nós de mesmo DNA |
| Adaptive Threat Detector | `immunity/adaptive_threat_detector.py` | Aprende com ataques anteriores |
| Regression Detector | `immunity/regression_detector.py` | Impede reintrodução de bugs já corrigidos |
| Immune Orchestrator | `immunity/immune_orchestrator.py` | Integra as camadas acima |
| Epigenetic Masking | `immunity/epigenetic_masking.py` | Barreira de memória crítica |
| Metabolic Pruner | `immunity/metabolic_pruner.py` | Poda por TTL + deduplicação |
| Emergent Behavior / Loop / Symbiosis / Vacuum | `emergent_behavior_detector.py`, `loop_detector.py`, `symbiosis_score.py`, `vacuum_trigger.py` | Ver §8 (Fase 9 — Leis de Holliwell) |

### Caso de estudo: `AsyncViolationDetector` como "órgão" completo

O texto original descreve este componente com riqueza suficiente para servir de exemplo de como o padrão biológico se aplica a um único módulo:

```
AGENTE STEM (async_violation_detector)
    ├── NÚCLEO        → AST Analyzer (análise sintática)
    ├── MITOCÔNDRIA   → PatternDNA (padrões de detecção evoluem)
    ├── RIBOSSOMO     → scan_ecosystem() (síntese de relatórios)
    ├── MEMBRANA      → glutathione_filter (seletividade de entrada)
    ├── IMUNIDADE     → ImmuneMemoryExchange (memória de falsos positivos)
    ├── EPIGENÉTICA   → _epigenetic_adaptation (expressão dinâmica)
    ├── EVOLUÇÃO      → _genomic_reflection (BanditPolicy)
    └── APOPTOSE      → _apoptose_toxic_patterns (limpeza de padrões)
```

Fluxo operacional: `scan → detectar → filtrar (GSH) → aprender (memória) → adaptar (epigenética) → limpar (apoptose) → regenerar`. Regeneração automática é disparada quando `fitness_score < 0.5`; feedback humano é registrado via `detector.register_feedback(path, is_false_positive=True)`.

**Mecanismos de defesa registrados no documento original:**

| ROS (ameaça) | GSH (defesa) |
|---|---|
| Falsos positivos | Threshold de confiança + filtro GSH |
| Padrões tóxicos | Apoptose automática (fitness < 20%) |
| Auto-degradação | `regenerate()` |
| Falta de aprendizado | Memória imunológica + feedback loop |
| Isolamento | `AcetylcholineBus` + `OmniMind` |
| Detecção over-aggressive | Modo adaptativo + peso epigenético |

---

## 5. Ciclos Metabólicos (Pipeline de Dados)

| Ciclo | Implementação | Função |
|---|---|---|
| Metilação | `methylation_cycle.py` + `no_evolution_methylation.py` | Promove skills candidatas a `production` |
| Glutationa | `glutathione_pool.py` + `glutathione_guardrails.py` | Defesa antioxidante contra falhas/toxinas |
| Homocisteína | `homocysteine_pool.py` + `no_evolution_homocysteine.py` | Pool de skills não validadas + detecção de toxicidade |
| Transulfuração | `transsulfuration_cycle.py` | Converte erros recorrentes em guardrails |
| SAMe | `same_engine.py` | Budget metabólico para mutações (recurso escasso) |
| Autofagia | `skill_quarantine.py`, `SkillRecycler` | Reciclagem de skills obsoletas |
| Mitose/Diferenciação | `MetaAgentDesigner`, `specialization_instructions` | Nós que se especializam conforme carga |
| Apoptose | `graceful_shutdown.py`, `EvoAgent.apoptose()` | Morte programada sem cascata de falhas |

### Perfil antioxidante (GSH / GSSG / NADPH)

- **GSH (camadas de proteção)**: sandbox (`sandbox_executor.py`, `sandbox_rules.py`) · AST Gateway (`ast_gateway.py`) · sanity barrier em `orchestrator.py` · `MemoryError` para aprendizado · `GlutathionePool.respond()`.
- **GSSG (componentes sacrificáveis)**: skills rejeitadas viram guardrails via `route_to_guardrail()`; erros críticos são registrados para análise posterior.
- **NADPH (reserva de regeneração)**: `SAMePool` com budget limitado (100 unidades padrão) · `SAMeBudgetTracker` (janela de 24h) · `MethylationInhibitor` bloqueia mutações não-críticas quando SAMe está baixo.

### Ciclo de auto-regeneração (geral)

1. **Detecção** — `HomeostasisController.check_sla()` verifica latência/custo/erro.
2. **Sinalização** — violações disparam `_apply_epigenetic_adjustments()`.
3. **Recuperação** — epsilon do `BanditPolicy` é ajustado dinamicamente.
4. **Aprendizado** — `SkillRecycler.recycle()` reintegra skills úteis.
5. **Persistência** — pools usam arquivos JSON com locks de thread (⚠️ com uma exceção — ver §12).

---

## 6. Pipeline de Execução (DAG)

> ⚠️ O documento original descreve o DAG em dois momentos diferentes com números diferentes: uma síntese inicial fala em **55 nós/7 fases**; a cobertura de testes de linhagem, mais adiante, já fala em **115 nós executáveis**. Isso bate com o crescimento real do projeto — não é um erro de digitação isolado, é o projeto evoluindo entre uma seção e outra do mesmo arquivo. Mantive as duas versões, na ordem em que aparecem.

### Estrutura original (síntese em 7 fases, 55 nós)

1. **Definição** (23 nós) — intake, enhancement, PM, requisitos, arquitetura
2. **Planejamento** (3 nós) — planner, task_breakdown, execution_plan
3. **Construção** (6 nós) — coder, frontend/backend/database builder
4. **Qualidade** (7 nós) — test_generator, integrador, auditoria
5. **Correção** (6 nós) — qa, debugger, fix_validator
6. **Entrega** (9 nós) — documentation, metrics, retrospective
7. **Metacognição** (7 nós) — evaluator, gap_analyzer, evolution_trigger

### Fluxo metabólico do núcleo evolutivo

```
evaluator → gap_analyzer → skill_generator → sandbox_validator → evolution_committee
                                                                       ↓
                                                                pipeline_updater
                                                                       ↓
                                                                evolution_trigger
                                                                       ↓
                                                             evolution_homocysteine
                                                                       ↓
                                                              evolution_methylation
                                                                       ↓
                                                                   omnimind
```

### Estado atual (conforme árvore de diretórios, Apêndice A)

`graphs/nodes/` contém **110 arquivos únicos `no_*.py`** na árvore fornecida (mais os módulos auxiliares `_search_*.py`) — consistente com os "115 nós executáveis" citados na cobertura de testes de linhagem. Isso confirma que a estrutura de 55 nós é um retrato antigo do sistema, não o estado atual.

---

## 7. Motor Evolutivo (Genomic Reflection)

```
EXECUÇÃO DO AGENTE
       ↓
ResultAgent registra ExecutionMetrics
       ↓
GenomicReflection.analyze_performance()
       ↓
Identifica best_traits / worst_traits
       ↓
propose_mutations_async()
       ↓
Tipo de mutação: TRAIT_ENHANCEMENT (sucesso) · TRAIT_SUPPRESSION (fracasso) · TRAIT_ADDITION (faltante)
       ↓
validate_with_bandit_async()  →  validador customizado, ou fallback: confidence > 0.6
       ↓
apply_mutation_async()
       ↓
DNA atualizado no FusionEngine
```

### Cadeia de boot (do CLI ao `EvoAgent`)

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

O `EvoAgent` não substitui o `Orchestrator` — roda dentro da infraestrutura existente. Local correto de inicialização (`core/orchestrator.py`, após `self.evolution_runtime`):

```python
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

No `run()` do `Orchestrator`, antes de executar o pipeline, o input pode passar por `evo_agent.handle()` para obter a expressão genômica e usar os ciclos de GSH + metilação como pré-processamento imunológico do prompt.

**Modos de ativação do `EvolutionRuntime`:**

| Modo | Como ativar |
|---|---|
| Automático em background | `EVOLUTION_AUTO=1` no `.env` |
| Manual via API | `orchestrator.evolution_runtime.start()` |
| Direto (demo/teste) | `asyncio.run(demo())` em `evo_agent.py` |

---

## 8. Leis Universais Aplicadas

Bloco de trabalho identificado no documento original como "Fase 9", mapeando as Leis de Holliwell a componentes concretos:

| Lei Universal | Componente |
|---|---|
| Lei da Ordem | `EntropySentinel` |
| Lei da Caridade | `SymbiosisScore` |
| Lei do Vácuo | `VacuumTrigger` |
| Lei da Replicação | `FusionEngine` + `AncestryTree` |
| Lei da Memória Imunológica | `GenomicReflection` |
| Lei da Homeostase | `MetabolicRhythm` |

**Integração:** `no_fusion.py` (nó de metacognição).

```
ENTROPIA (Lei da Ordem)
    ↓ detecta caos → penaliza fitness → dispara apoptose
VÁCUO (Lei do Vácuo)
    ↓ remove padrões obsoletos → cria espaço → força diversidade
SIMBIOSE (Lei da Caridade)
    ↓ detecta cooperação → bônus de fitness → identifica parceiros
FUSÃO (Lei da Replicação)
    ↓ calcula ressonância de DNA → sintetiza híbrido → registra linhagem
ANCESTRALIDADE (Lei da Memória)
    ↓ gera MOC (Map of Content) → timeline de mutações → preserva identidade
```

Integrações: `FusionEngine → FusionNode → Topology → Obsidian`.

---

## 9. Módulo Obsidian — Subconsciente

Modelo de mente em três níveis usando Markdown real com YAML frontmatter, tags e links bidirecionais `[[...]]` — 100% legível e editável por humanos.

```
obsidian/
├── 01_Instincts/    → Diretrizes imutáveis (imutavel: true no frontmatter)
├── 02_Short_Term/   → Memórias brutas (erros, eventos do dia)
├── 03_Long_Term/    → Conhecimento consolidado (saída do ciclo REM)
└── 04_Synapses/     → Mapa sináptico central (índice automático de tags/links)
```

| Componente | Arquivo | Função |
|---|---|---|
| SubconsciousAPI | `subconsciousapi.py` | Camada de I/O do vault — ler, escrever, consultar por tag |
| ErrorCapture | `error_capture.py` | Captura automática de exceções → `02_Short_Term/` |
| REMSleepEngine | `consolidation.py` | Consolidação: `Short_Term → IA → Long_Term + Synapses` |
| LearningSystem | `learning_system.py` | Injeta memórias de longo prazo em prompts de agentes |
| OmniMind | `omnimind.py` | Consciência central — Leis Universais, orientação existencial |

### 🔬 MAPA DE CONEXÕES METABÓLICAS

### **Fluxo de Dados Chappie → Obsidian:**

```
┌─────────────────────────────────────────────────────────────┐
│                    CHAPPIE CORE                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  vacuum_daemon.py ──────────┐                                │
│  (Consolidação Automática)   │                                │
│                              ▼                                │
│                     iaglobal/obsidian/                        │
│                     ├── 02_Short_Term/  ← lê                  │
│                     ├── 03_Long_Term/   ← grava               │
│                     └── 04_Synapses/    ← atualiza mapa       │
│                                                               │
│  error_enricher.py ───────────┐                               │
│  (Erros Enriquecidos)          │                               │
│                               ▼                                │
│                      iaglobal/obsidian/                        │
│                      └── 02_Short_Term/  ← grava erro_*.md    │
│                                                               │
│  lineage_guardian.py ───────┐                                 │
│  (Validação DNA)             │  (Sem integração direta)        │
│                             (sem seta)                         │
│                                                               │
│  ivm_axiom.py ─────────────┐                                  │
│  (IVM em Tempo Real)        │  (Memória apenas, sem persist)  │
│                            (sem seta)                          │
└─────────────────────────────────────────────────────────────┘
```

---

### ⚡ SÍNTESE ARQUITETURAL — O QUE ESTÁ CONECTADO

### **1. VacuumDaemon → REMSleepEngine → Obsidian**

```python
# Em vacuum_daemon.py (linha ~35-40):
from iaglobal.obsidian.consolidation import REMSleepEngine

class VacuumDaemon:
    def __init__(self, vault_path: Optional[Path] = None, ...):
        self.vault_path = Path(vault_path or PACKAGE_DIR / "obsidian")
        self.remsleep_engine = REMSleepEngine(vault_path=self.vault_path)
        #                                             ↑
        #                             Usa EXATAMENTE o mesmo vault
```


### Ciclo de vida dos dados

```
Agente falha
    ↓
ErrorCapture.capturar()
    ↓
02_Short_Term/  (memória bruta, YAML + traceback)
    ↓
REMSleepEngine.iniciar_fase_rem()
    ├─ Solicita síntese via IA (ou fallback mock)
    ├─ Grava → 03_Long_Term/
    ├─ Remove → 02_Short_Term/ (poda sináptica)
    └─ Reconstrói → 04_Synapses/Mapa_Mental_Subconsciente.md
                          ↓
LearningSystem / IAGlobalAgentWrapper → sussurrar_intuicao(tags) → prompt enriquecido
```

### Integração com evolução

- **IVM**: `obsidian_notes_escritas` é métrica de Cooperação (peso 0.2) — agentes que documentam no Obsidian têm maior fitness.
- **Linhagem**: `exportar_nota_agente()` cria `03_Long_Term/agentes/{id}.md` com `strategy`, `fitness`, `parent_link`.
- **OmniMind**: `EvoAgent` consulta o singleton `omni_mind` para orientação existencial.

### Estado do vault (conforme documento original)

| Diretório | Status | Conteúdo |
|---|---|---|
| `01_Instincts/` | Vazio | API pronta via `escrever_instinto()` |
| `02_Short_Term/` | Vazio | 9 erros consolidados e podados |
| `03_Long_Term/` | 9 notas | Erros consolidados pelo `REMSleepEngine` (fallback mock) |
| `04_Synapses/` | 1 mapa | `Mapa_Mental_Subconsciente.md`, índice de 9 notas e 2 tags ativas |

**Gargalo pendente:** a síntese usou fallback mock (`_mock_sintese`). Para consolidar com insights reais:

```python
from iaglobal.obsidian.consolidation import REMSleepEngine
REMSleepEngine(ai_client=meu_client_llm).iniciar_fase_rem()
```

---

## 10. Comunicação Assíncrona

- **`AcetylcholineBus`** (`graphs/communication/acetylcholine_bus.py`) — barramento de eventos assíncrono entre agentes.
- **`AgentMailbox`** (`graphs/communication/agent_mailbox.py`) — caixa de mensagens por agente.
- **`Membrane` / `membrane_key.py`** — filtro seletivo de entrada, análogo à membrana celular.
- **Diferenciação/escala**: `MetaAgentDesigner.design_team()` detecta keywords e ativa especialistas; `specialization_instructions` injeta contexto de especialização no nó; `CpuAffinityManager` mapeia nós em núcleos para balanceamento.

### Epigenética operacional (`epigenetic.py`)

| Flag | Valor padrão | Propósito |
|---|---|---|
| `bandit_epsilon` | 0.2 | Taxa de explore/exploit |
| `sam_budget_multiplier` | 1.0 | Multiplicador de budget metabólico |
| `max_iterations` | 5 | Limite de reflexões |
| `homeostasis_enforcement` | True | Ativa ajuste automático de SLA |

Configurações que sobrevivem a restarts: `bandit_epsilon`, `sam_budget_multiplier`, `max_iterations`, `homeostasis_enforcement`.

---

## 11. Validação sob Carga

Bloco identificado no original como "Fase 12" — testes de produção sob estresse:

| Categoria | Testes | Resultado |
|---|---|---|
| Ressonância de DNA | `test_fusion_under_load` (20 agentes) · `test_resonance_calculation_performance` (1225 cálculos em <5s) | ✅ 2/2 |
| Homeostase de energia | burst mode (carga >80%) · deep sleep (carga <20%) · recuperação pós-burst | ✅ 3/3 |
| Reflexão genômica | 150 execuções em <2s · 10 agentes concorrentes | ✅ 2/2 |
| Pipeline integrado | Fusão + Reflexão + Metabolismo + Vácuo | ✅ 1/1 |
| Recuperação de falhas | Recuperação após exceção | ✅ 1/1 |

Esses **99 testes de carga** somados aos 724 anteriores e a mais **9 testes** de outro bloco chegam ao total de **832 testes passando** citado no original (`724 + 99 + 9 = 832`).

---

## 12. Débito Técnico e Inconsistências Detectadas

Itens sinalizados explicitamente no documento original (mantidos como lista acionável, não diluídos em prosa):

1. **Contagem de nós inconsistente dentro do próprio documento** — uma seção fala em 55 nós/7 fases, outra em 115 nós executáveis testados. A árvore de diretórios confirma ~110–115 arquivos `no_*.py` reais — a estrutura de 55 nós está desatualizada.
2. **`entropy_sentinel.py` duplicado** — existe tanto em `immunity/entropy_sentinel.py` quanto em `security/entropy_sentinel.py`. Vale confirmar se é intencional (duas responsabilidades distintas) ou duplicação acidental.
3. **Inconsistência de caminho em `cli.py`** (linha 8) — usa `/home/user/projeto-iaglobal` em vez do path real do ambiente.
4. **Import duplicado de `asyncio`** em `main.py` (linha 349).
5. **Uso de `print()` em `orchestrator.py`** (linhas 403 e 852) — viola a diretriz de logging do projeto (deve ser `logger.info/error/exception`).
6. **Métrica duplicada em `async_run_graph_task`** (linhas 1280–1281) — print de debug redundante, candidato a remoção.
7. **`HomocysteinePool` sem lock** — `_load/_save` não é thread-safe, ao contrário de `SAMePool`, que já usa lock.
8. **"Total de Passos Implementados: 116/107"** — o próprio original registra um número de passos concluídos maior que o total planejado (107). Provavelmente reflete passos evolutivos adicionais gerados organicamente além da meta original, mas o documento não explica a discrepância — vale confirmar antes de citar esse número externamente.
9. **Conteúdo fora de lugar**: o documento original também continha um relatório de sessão específico (correção de geração de PDF/HTML com tema escuro — detector de extensão, scanner multi-diretório, resource limits, thread-safe BLAS). Esse é um registro de mudança pontual, não arquitetura estrutural — removido desta consolidação; recomendo mover esse tipo de conteúdo para um `CHANGELOG.md` ou log de sessões separado, para o `ARCHITECTURE.md` não voltar a acumular ruído cronológico.

---

## 13. Vetor Evolutivo (Roadmap Consolidado)

Itens de "próxima mutação" espalhados pelo documento original, consolidados aqui:

- **Genetic Algorithm** para tuning automático de pesos do IVM.
- **Expansão do MCP Protocol** — tools externas via Model Context Protocol.
- **`PhospholipidRegistry`** — load balancing dinâmico em nível de serviço.
- **Colony Intelligence** — múltiplos organismos `iaglobal` colaborando entre si.
- **Integração Obsidian mais profunda** — `LearningSystem` ainda não é usado por todos os agentes.
- **Expansão do `GlutathionePool`** — mais tipos de ameaças cobertas.
- **Threshold dinâmico no `HomocysteinePool`** baseado em carga.
- **`GracefulShutdown` mais granular** para auto-apoptose de agentes.
- **Handshake de Genesis entre nós remotos** (SHA3-512, ver §3) para rede global de agentes.
- **Detector `AsyncViolationDetector`**: migrar de regex para `ast.NodeVisitor` (precisão 100%) → classificador supervisionado para falsos positivos → distribuição de scanners entre núcleos (mitose) → compartilhamento de descobertas via `ImmuneMemoryExchange` → auto-proposta de patches via `no_code_executor`.

---

## Apêndice A — Árvore Completa de Diretórios

```
iaglobal/
├── agents/
│   ├── coder_agent.py
│   ├── critic_agent.py
│   ├── debugger_agent.py
│   ├── dependency_agent.py
│   ├── enhancement_agent.py
│   ├── evolution_agent.py
│   ├── failure_analysis_agent.py
│   ├── ingestion/
│   │   └── file_ingestion_agent.py
│   ├── intent_classifier_agent.py
│   ├── knowledge_writer_agent.py
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
│   ├── skill_generator_agent.py
│   ├── tester_agent.py
│   ├── typing_agent.py
│   └── validator.py
├── api/
│   └── mcp_server.py
├── asgi.py
├── auditoria_arquitetural.py
├── cli/
│   ├── bootstrap_engine.py
│   ├── bootstrap.py
│   ├── evolution_lab.py
│   ├── main.py
│   ├── output.py
│   └── status.py
├── cognition/
│   ├── adaptive_router.py
│   ├── agents/
│   │   └── task_classifier_agent.py
│   ├── learning/
│   │   └── classifier_memory.py
│   ├── outcome_tracker.py
│   ├── reputation_engine.py
│   └── task_fingerprint.py
├── communication/
├── core/
│   ├── apoptosis.py
│   ├── assistant.py (+ assistant.py.bkp)
│   ├── cognitive_proxy.py
│   ├── cognitive_runtime.py
│   ├── config.py
│   ├── decision_engine.py
│   ├── diagnostico.py
│   ├── env_loader.py
│   ├── evolution_controller.py
│   ├── governance.py
│   ├── graceful_shutdown.py
│   ├── law_enforcement.py
│   ├── neuro_orchestrator.py
│   ├── orchestrator.py            ← ponto central de boot
│   ├── retry_handler.py
│   └── structure.py
├── debug/
│   └── node_timing.py
├── events/
│   ├── decision_event.py
│   ├── event_dispatcher.py
│   ├── event_store.py
│   ├── event_types.py
│   └── replay.py
├── evolution/
│   ├── agents/
│   │   ├── gap_analyzer.py
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
│   ├── ga_router_optimizer.py
│   ├── genomic_reflection.py
│   ├── handler_evolution.py
│   ├── homeostasis_controller.py
│   ├── meta_agent_designer.py
│   ├── metabolic_lifecycle.py
│   ├── metabolic_rhythm.py
│   ├── metabolism/
│   │   ├── homocysteine_pool.py
│   │   ├── methylation_cycle.py
│   │   ├── opportunity_cost_detector.py
│   │   └── transsulfuration_cycle.py
│   ├── metacognition/
│   │   ├── evaluator.py
│   │   ├── evolution_backlog.py
│   │   ├── evolution_committee.py
│   │   ├── evolution_trigger.py
│   │   ├── failure_taxonomy.py
│   │   ├── gap_analyzer.py
│   │   ├── pipeline_updater.py
│   │   ├── sandbox_validator.py
│   │   └── skill_generator.py
│   ├── meta_evolver.py
│   ├── proposal_quarantine.py
│   ├── reward_aggregator.py
│   ├── same_engine.py
│   ├── self_optimizer.py
│   ├── skill_quarantine.py
│   ├── skills/
│   │   ├── dynamic_registry.py
│   │   ├── reactpy_skill_registry.py
│   │   ├── run_fn_factory.py
│   │   ├── skill_executor.py
│   │   ├── skill.py
│   │   ├── skill_registry.py
│   │   └── skill_versions.py
│   ├── task_agent_factory.py
│   └── task_analyzer.py
├── execution/
│   ├── cpu_affinity.py
│   ├── executor.py
│   └── sandbox.py
├── feedback/
│   ├── benchmark_runner.py
│   ├── betaine_judge.py
│   ├── reward_aggregator.py
│   ├── reward_signal.py
│   └── user_feedback.py
├── genesis/
│   ├── certify_block.py
│   ├── check_cbor.py
│   ├── data/
│   │   ├── integrity_tree.cbor
│   │   ├── test_genesis_integrity.py
│   │   ├── webhidden_genesis_blueprint.cbor
│   │   └── webhidden_genesis_evolutive.cbor
│   ├── fusion_engine.py
│   ├── genesis_purifier.py
│   ├── genesis_verifier.py
│   ├── identity.py
│   └── verifygenesis.py
├── graphs/
│   ├── artifact.py
│   ├── bandit.py
│   ├── builder.py
│   ├── communication/
│   │   ├── acetylcholine_bus.py
│   │   ├── agent_mailbox.py
│   │   └── membrane_key.py
│   ├── credit.py
│   ├── edge.py / edges.py
│   ├── execution_context.py
│   ├── execution_engine.py
│   ├── execution_graph.py
│   ├── graph_builder_v2.py
│   ├── instrumentation.py
│   ├── membrane.py
│   ├── migrar_nodes.py
│   ├── node.py
│   ├── nodes/                     ← ~110-115 arquivos no_*.py (ver §6)
│   │   ├── no_adaptive_router.py
│   │   ├── no_agentmailbox.py
│   │   ├── no_ai_audit_compliance.py
│   │   ├── no_api_builder.py
│   │   ├── no_api_design.py
│   │   ├── no_apoptosis_kill.py
│   │   ├── no_architect.py
│   │   ├── no_architecture_validator.py
│   │   ├── no_artifact_writer.py
│   │   ├── no_async_violation_detector.py
│   │   ├── no_auditor_sentinel.py
│   │   ├── no_backend_builder.py
│   │   ├── no_business_rules.py
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
│   │   ├── no_interpreter.py
│   │   ├── no_knowledge_analyzer.py
│   │   ├── no_knowledge.py
│   │   ├── no_knowledge_writer.py
│   │   ├── no_local_knowledge.py
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
│   │   ├── no_system_design.py
│   │   ├── no_task_breakdown.py
│   │   ├── no_technology_selection.py
│   │   ├── no_tester.py
│   │   ├── no_test_generator.py
│   │   ├── no_threat_modeling.py
│   │   ├── no_typing_agent.py
│   │   ├── no_validator.py
│   │   ├── no_web_classifier.py
│   │   ├── _disk_swap.py
│   │   ├── _search_enhanced.py
│   │   ├── _search_queries.py
│   │   ├── _search_router.py
│   │   ├── _search_shared.py
│   │   ├── _search_sources.py
│   │   └── _search_wikipedia.py
│   ├── nodes.py                   ← proxy dinâmico (Regra de Ouro, §2)
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
├── immunity/                      ← ver §4
│   ├── adaptive_threat_detector.py
│   ├── apoptosis_engine.py
│   ├── async_violation_detector.py
│   ├── emergent_behavior_detector.py
│   ├── entropy_sentinel.py
│   ├── epigenetic_masking.py
│   ├── glutathione_guardrails.py
│   ├── glutathione_pool.py
│   ├── hallucination_detector.py
│   ├── immune_memory_exchange.py
│   ├── immune_orchestrator.py
│   ├── loop_detector.py
│   ├── metabolic_pruner.py
│   ├── mhc_detector.py
│   ├── pathogen_analyzer.py
│   ├── regression_detector.py
│   ├── symbiosis_score.py
│   └── vacuum_trigger.py
├── intention/
│   └── meta_director.py
├── __main__.py
├── memory/
│   ├── async_memory.py
│   ├── backup_manager.py
│   ├── cache.py
│   ├── check_db.py
│   ├── cognitive_cache.py
│   ├── consolidation.py
│   ├── core.py
│   ├── data/                      ← caches, dbs, JSONs de pools (glutathione, homocysteine, etc.), logs, snapshots
│   ├── db_manager.py
│   ├── fusion_engine.py
│   ├── memory_error.py
│   ├── memory.py
│   ├── memory_storage.py
│   ├── memory_vector.py
│   ├── persistence.py
│   ├── ranking.py
│   ├── raw_pool.py
│   ├── semantic_cache.py
│   ├── term_long.py
│   └── term_short.py
├── models/
│   ├── agent_context.py
│   ├── event_bus.py
│   └── task.py
├── observability/
│   ├── health.py
│   ├── metrics_collector.py
│   └── tracing.py
├── obsidian/                      ← ver §9
│   ├── 01_Instincts/
│   ├── 02_Short_Term/
│   ├── 03_Long_Term/
│   ├── 04_Synapses/
│   ├── ancestry_tree.py
│   ├── consolidation.py
│   ├── epigenetic_registry.py
│   ├── error_capture.py
│   ├── law_compliance_logger.py
│   ├── learning_system.py
│   ├── omnimind.py
│   ├── subconsciousapi.py
│   └── success_cycle_logger.py
├── _paths.py
├── pipeline/
│   ├── engine.py
│   ├── pipelinestate.py
│   ├── result.py
│   └── stages.py
├── providers/
│   ├── async_http.py
│   ├── batch_writer.py
│   ├── gemini_provider.py
│   ├── groq_provider.py (+ .bkp)
│   ├── hf_image_provider.py
│   ├── hf_inference_provider.py
│   ├── hf_router_provider.py
│   ├── hf_video_provider.py
│   ├── huggingchat_provider.py
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
│   ├── provider_scorer.py
│   ├── provider_state.py
│   ├── task_router.py
│   └── token_usage.py
├── recycling/
│   ├── embedding_pruner.py
│   ├── mta_pool.py
│   ├── prompt_recycler.py
│   └── skill_recycler.py
├── reflection/
│   ├── failure_analysis.py
│   ├── learning_loop.py
│   ├── reflexion_engine.py
│   └── self_critique.py
├── security/
│   ├── ast_gateway.py
│   ├── network_guard.py
│   ├── pysecurity1024.py
│   ├── resource_limits.py
│   ├── sandbox_executor.py
│   └── sandbox_rules.py
├── server/
│   ├── leiame_server.md
│   └── server.py
├── settings.py
├── state/
├── storage/
│   ├── batch_writer.py
│   ├── converter.py
│   ├── daemon_monitor.py
│   └── snapshotter.py
├── tools/
│   ├── search.py
│   ├── search_tools.py
│   ├── tool_router.py
│   └── web_brain.py
├── ui/
│   ├── fastapi_app.py
│   ├── reactpy_components.py
│   ├── urls.py
│   └── views.py
├── urls.py
├── utils/
│   ├── controlled_subprocess.py
│   ├── hash_utils.py
│   ├── helpers.py
│   ├── logger.py
│   └── playwright_util.py
└── validation/
    ├── ast_security.py
    ├── engine.py
    ├── gateway.py
    ├── normalization.py
    ├── scoring.py
    └── syntax.py

73 diretórios, 486 arquivos (contagem original do comando `tree`)
```

---
