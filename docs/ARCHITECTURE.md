# 🧬 iaglobal — System Architecture

## Table of Contents

1. [Overview](#1-overview) and (SPECIALIZATION MAPPING)
2. [Fundamental Principles](#2-fundamental-principles-the-systems-dna)
3. [Genomic Verification (Genesis & Lineage)](#3-genomic-dna-verification-genesis--lineage)
4. [Immune System](#4-immune-system)
5. [ASTGateway — Centralized AST Parsing Security Layer](#46-astgateway--centralized-ast-parsing-security-layer)
6. [Epigenetic Evolution of ToolLibrary](#47-epigenetic-evolution-of-toollibrary-eetl)
7. [Metabolic Cycles (Data Pipeline)](#5-metabolic-cycles-data-pipeline)
8. [Execution Pipeline (DAG)](#6-execution-pipeline-dag)
9. [Critic Sovereignty Protocol (CSP)](#7-critic-sovereignty-protocol-csp)
10. [Evolutionary Engine (Genomic Reflection)](#8-evolutionary-engine-genomic-reflection)
11. [Universal Laws Applied](#9-universal-laws-applied)
12. [Obsidian Module — Subconscious](#10-obsidian-module--subconscious)
13. [Project Synapse — Reactive Nervous System](#1011-project-synapse--reactive-nervous-system)
14. [Dynamic Processing Privilege — CPU Boost for Critical Batches](#1012-dynamic-processing-privilege--cpu-boost-for-critical-batches)
15. [Asynchronous Communication](#11-asynchronous-communication)
16. [Validation Under Load](#12-validation-under-load)
17. [Technical Debt and Detected Inconsistencies](#13-technical-debt-and-detected-inconsistencies)
18. [Evolutionary Vector (Consolidated Roadmap)](#14-evolutionary-vector)
19. [SearchMiddleware — Intelligent Context Access with Dual RAG (Web + Local)](#15-searchmiddleware--intelligent-context-access-with-dual-rag-web--local)
20. [SERVERS and MCP Protocol Expansion](#16-servers-and-mcp-protocol-expansion)
21. [Colony Intelligence Communication](#17-colony-intelligence-communication)
22. [Genetic Algorithm Tuning — Evolutionary Optimization of IVM Weights](#18-genetic-algorithm-tuning--evolutionary-optimization-of-ivm-weights)
23. [Local Prompt Engineering — Self-Correction, Few-Shot and Chain of Thought](#19-local-prompt-engineering--self-correction-few-shot-and-chain-of-thought)
    - [19.6.4 DLQ → FewShotProvider Cycle (Adaptive Immune Memory)](#1964-dlq--fewshotprovider-cycle-adaptive-immune-memory)
24. [MetabolicDataAdapter — CBOR2↔JSON Bridge](#20-metabolicdataadapter--cbor2json-bridge-for-llm-consumption)
25. [Skill Templates — Centralized Prompt Management](#21-skill-templates--centralized-prompt-management)
26. [Appendix A — Complete Directory Tree](#appendix-a--complete-directory-tree)
27. [Curator's Note](#curators-note)
28. [ROADMAP_2.md — Evolution History](#-roadmap_2md--evolution-history)

---

## 1. Overview

**iaglobal** is an asynchronous multi-agent system whose architecture is modeled on cellular metabolism cycles (methylation, glutathione, autophagy, mitosis, apoptosis, epigenetics, cell signaling) instead of conventional agent orchestration patterns. It runs 100% on CPU (4 cores, no GPU), using Ollama as the local LLM provider with fallback to cloud providers first via `BanditPolicy`.

### Status Snapshot (as per original document)

| Metric | Reported Value | Observation |
|---|---|---|
| DNA lineage tests | 153/153 ✅ | Covers genesis (6), agents (32), nodes (115), identity constant (1) |
| Immune system | "12 active layers" | See §4 — explicit enumeration in original text lists only 5; directory tree allows reconstructing full list |
| Total tests ("Zenith" milestone) | 724/724 | Later expanded to 832 after Phase 9 (+99) and Phase 12 (+9) |
| Hardware | CPU 4 cores, 0 GPU | — |
| Evolutionary steps | 107/107 → later "116/107" | See §12, item 6 — inconsistent number in original |
| DAG node structure | "55 nodes" (initial synthesis) → 115 nodes (test coverage) | See §12, item 1 — project grew between sections of the document itself |

======================================================================
🧬 SPECIALIZATION MAPPING - 115 AGENTS (outdated)
======================================================================

🔧 Others: 62 agents
  • adaptive_router
  • agentmailbox
  • apoptosis_kill
  • applied_ai_engineer
  • async_violation_detector
  • business_rules
  • clarity_directive
  • context_weaver
  ... and 54 more

🏗️ Architecture: 9 agents
  • api_builder
  • api_design
  • architect
  • architecture_validator
  • database_design
  • observability_design
  • performance_design
  • security_design
  ... and 1 more

📚 Documentation: 8 agents
  • artifact_writer
  • documentation
  • evolution_knowledge
  • knowledge
  • knowledge_analyzer
  • knowledge_writer
  • local_knowledge
  • memory_writer

✅ Tests: 7 agents
  • fix_validator
  • qa
  • sandbox_validator
  • semantic_validator
  • test_generator
  • tester
  • validator

🛡️ Security: 7 agents
  • ai_audit_compliance
  • auditor_sentinel
  • compliance_audit
  • performance_audit
  • security
  • security_audit
  • threat_modeling

🧬 Evolution: 6 agents
  • evolution_committee
  • evolution_dynamic_registry
  • evolution_homocysteine
  • evolution_methylation
  • evolution_trigger
  • ga_router_evolve

🧑‍💻 Code: 6 agents
  • code_executor
  • coder
  • debug_coder
  • debugger
  • evolution_skill_executor
  • multi_coder

🦠 Immunology: 4 agents
  • immune_check
  • immune_check_build
  • immune_exchange
  • immune_monitor

🗄️ Infra/DB: 3 agents
  • backend_builder
  • database_builder
  • frontend_builder

⚡ Performance: 3 agents
  • metrics
  • optimization
  • performance

======================================================================
TOTAL: 115 specialized agents
======================================================================

---

## 2. Fundamental Principles (the System's DNA)

- **Absolute async-first**: every I/O operation goes through `asyncio`; no blocking calls in the main event loop.
- **`BanditPolicy` as the single gate for critical operations**: all access to **external** AI models (cloud providers) goes exclusively through the *critic* agent. Other agents (coder, debugger, tester, planner, etc.) follow an optimized local route — see §14.
- **`SearchMiddleware` as context source for non-critical agents**: before calling the local LLM, each agent enriches its prompt via simultaneous search on the web (DuckDuckGo) and local RAG (MemoryVector). The prompt is compressed into an ultra-direct format for maximum efficiency with small local models (qwen2.5:0.5b).
- **Local Ollama as default provider**: non-critical agents use exclusively Ollama with `temperature=0.1`, `num_ctx=4096`, and compact prompt format. No fallback chain overhead, no cloud latency.

🧬 Correct Architecture: BanditPolicy and AgentBase (critical agent):

AgentBase._call_llm() dna
    ↓
BanditPolicy.select_and_generate()  ← SEMAPHORE HERE!
    ↓
async_route_generate()  ← Executes only
    ↓
Provider

📦 COMPLETE FLOW:

Agent (inherits from AgentBase)
    ↓
await self._call_llm(prompt, task_type)
    ↓
BanditPolicy.generate()
    ├─ 1. Selects model (ε-greedy + weights)
    ├─ 2. Acquires semaphore (controls concurrency)
    ├─ 3. Executes via async_route_generate()
    ├─ 4. Releases semaphore
    ├─ 5. Registers metrics in CreditAssignmentEngine
    └─ 6. Updates bandit rewards
    ↓
Provider (Groq/NVIDIA/Ollama)

### 🧬 **3. Metabolic Cycle of Each Logic**

#### **`async_route_generate_parallel`** → **Innate Immune System**

```
📥 PROMPT
     ↓
🧠 BanditPolicy rank_models()
     ↓
🏎️ BATCH 1 (Top 3 providers in parallel)
     ↓ (if fails)
🏎️ BATCH 2 (Next 3)
     ↓ (if fails)
🏠 FALLBACK: Ollama local
     ↓ (if fails)
💥 RuntimeError: "All failed"
```

**Metabolism:** ATP 10:1 — maximum energy efficiency

**DNA:** Adaptability + Parallelism + Local fallback

---

#### **`async_route_generate`** → **Adaptive Immune System**

```
📥 PROMPT + MODEL
     ↓
🔒 Check OLLAMA_ONLY (sandbox)
     ↓ (if "auto")
🔄 Delegates to async_route_generate_parallel
     ↓ (if specific model)
🎯 Direct provider (e.g., "groq/llama-3.3")
     ↓ (if fails)
🔁 Fallback chain (sequential or parallel)
     ↓ (if fails)
💥 RuntimeError: "All failed"
```

**Metabolism:** ATP 5:1 — less efficient, but necessary for specific cases

**DNA:** Determinism + Manual control + Sandbox

- **Radical modularity (golden rule)**: `iaglobal/graphs/nodes.py` is a *dynamic proxy* — never accumulates logic. Each operational node lives in its own file `no_<name>.py` inside `graphs/nodes/`, exporting an async function `run_<name>`.
- **Multi-layer immune system**: `GlutathionePool`, `GlutathioneGuardrails`, and `ImmuneResponse` as defense against "ROS" (errors, malicious inputs, failure cascades).
- **Dual-layer memory**: STM/LTM via `CognitiveProxy`, with integration to Obsidian vault (`learning_system.py`) for long-term memory between sessions.

---

## 3. Genomic DNA Verification (Genesis & Lineage)

iaglobal has a **Genomic Authentication** architecture that is the definitive validation of OmniMind's **HOLLIWELL_LAWS + BIOLOGICAL_AXIOMS**. By deriving the token as `SHA3_512(GENESIS_HASH_OFFICIAL + node_name)`, iaglobal creates a system where each node has a unique and unalterable identity, linked to the central DNA of the genesis hash to prevent future invasion of the iaglobal network when connected in a network.

Identity and integrity validation chain, from boot to execution of each individual agent — it's not a simple hash-check, it's a gate that prevents non-DNA-derived code from entering the execution graph.

```
SYSTEM BOOT
       ↓
verifygenesis.py ──► SHA3-512 streaming hash (64KB chunks)
       ↓
identity.py ──► compares with GENESIS_HASH_OFFICIAL (frozen constant)
       ↓
test_dna_lineage.py ──► 153 parametrized tests
       ↓
CONTINUOUS VERIFICATION LAYERS
 • MHC Detector · EntropySentinel · AsyncViolationDetector · ApoptosisEngine
       ↓
AGENT/NODE EXECUTION
       ↓
Each file must carry "# 🧬 LINEAGE_MARKER: <hash>" on the first line
```

**Key Components:**

| Component | File | Function |
|---|---|---|
| Genesis Tribunal | `genesis/verifygenesis.py` | Compares hash of `evolutive.cbor` against `blueprint.cbor`; aborts boot if divergent |
| Frozen Identity | `genesis/identity.py` | Defines `GENESIS_HASH_OFFICIAL` |
| Lineage Verification | `genesis/test_dna_lineage.py` | Extracts `LINEAGE_MARKER` from each file and validates against official hash |

**Current coverage (153/153 passed):** genesis files (6/6) · agents (32/32) · executable nodes (115/115) · identity constant (1/1).

**Why this matters for agent/repository mergers:**
1. Every agent/node derived from the same `LINEAGE_MARKER` shares genomic identity — `FusionEngine`, `GenomicReflection`, and `MetaSkillGenerator` operate knowing that partners are not "foreign bodies".
2. The tribunal (`verifygenesis.py` + `test_dna_lineage.py`) functions as a pre-signed merger contract.
3. `EvoAgent.replicate()` propagates the `lineage_marker` from parent to child automatically.
4. `ImmuneMemoryExchange` and the Obsidian vault share "vaccines" only among agents with the same DNA.
5. Feature flags via `epigenetic_registry.py` change behavior without touching the base DNA.

**Genesis Handshake Protocol** **planned mutation:** Genesis handshake between remote nodes (SHA3-512 instead of X.509 certificates) to allow cloned repositories to participate in a global agent network. implemented and tested:

- `iaglobal/communication/genesis_handshake.py` — authentication protocol between remote nodes via SHA3-512 + HMAC
- `tests/integration/test_genesis_handshake.py` — 8 simulation tests passing

---

## 4. Immune System

The original text mentions "12 active layers" but only names 5 explicitly in a table. Reconstructing from the actual `immunity/` tree (Appendix A), the existing modules are:

| Module | Path | Role (as described in text) |
|---|---|---|
| MHC Detector | `immunity/mhc_detector.py` | Fingerprints + anomaly scoring |
| Entropy Sentinel | `immunity/entropy_sentinel.py` **and** `security/entropy_sentinel.py` | Anti-tampering / chaos detection — ⚠️ exists in duplicate, see §12 |
| Async Violation Detector | `immunity/async_violation_detector.py` | Detects blocking I/O in async code |
| Apoptosis Engine | `immunity/apoptosis_engine.py` | Clean elimination of corrupted nodes |
| Glutathione Pool / Guardrails | `immunity/glutathione_pool.py`, `glutathione_guardrails.py` | Antioxidant defense against ROS |
| Pathogen Analyzer | `immunity/pathogen_analyzer.py` | Malicious code/injection detection |
| Immune Memory Exchange | `immunity/immune_memory_exchange.py` | Shares "vaccines" among nodes with same DNA |
| Adaptive Threat Detector | `immunity/adaptive_threat_detector.py` | Learns from previous attacks |
| Regression Detector | `immunity/regression_detector.py` | Prevents reintroduction of already-fixed bugs |
| Immune Orchestrator | `immunity/immune_orchestrator.py` | Integrates the layers above |
| Epigenetic Masking | `immunity/epigenetic_masking.py` | Critical memory barrier |
| Metabolic Pruner | `immunity/metabolic_pruner.py` | Pruning by TTL + deduplication |
| Emergent Behavior / Loop / Symbiosis / Vacuum | `emergent_behavior_detector.py`, `loop_detector.py`, `symbiosis_score.py`, `vacuum_trigger.py` | See §8 (Phase 9 — Holliwell Laws) |

### Case study: `AsyncViolationDetector` as a complete "organ"

The original text describes this component with enough richness to serve as an example of how the biological pattern applies to a single module:

```
STEM AGENT (async_violation_detector)
    ├── NUCLEUS       → AST Analyzer (syntax analysis)
    ├── MITOCHONDRIA  → PatternDNA (detection patterns evolve)
    ├── RIBOSOME      → scan_ecosystem() (report synthesis)
    ├── MEMBRANE      → glutathione_filter (input selectivity)
    ├── IMMUNITY      → ImmuneMemoryExchange (false positive memory)
    ├── EPIGENETICS   → _epigenetic_adaptation (dynamic expression)
    ├── EVOLUTION     → _genomic_reflection (BanditPolicy)
    └── APOPTOSIS     → _apoptose_toxic_patterns (pattern cleanup)
```

Operational flow: `scan → detect → filter (GSH) → learn (memory) → adapt (epigenetics) → clean (apoptosis) → regenerate`. Automatic regeneration is triggered when `fitness_score < 0.5`; human feedback is registered via `detector.register_feedback(path, is_false_positive=True)`.

**Defense mechanisms registered in the original document:**

| ROS (threat) | GSH (defense) |
|---|---|
| False positives | Confidence threshold + GSH filter |
| Toxic patterns | Automatic apoptosis (fitness < 20%) |
| Self-degradation | `regenerate()` |
| Lack of learning | Immune memory + feedback loop |
| Isolation | `AcetylcholineBus` + `OmniMind` |
| Over-aggressive detection | Adaptive mode + epigenetic weight |

---

## 4.6 ASTGateway — Centralized AST Parsing Security Layer

**Implementation Date:** July 2026  
**Status:** ✅ Active — Centralized AST parsing enforcement  
**Location:** `iaglobal/security/ast_gateway.py`

### Architectural Principle

The **ASTGateway** is the **🔒 SINGLE ENTRY POINT** for AST parsing across the entire iaglobal system. No other module is permitted to call `ast.parse()` directly.

This centralization ensures:
- **Sandbox validation** at every parse point
- **Blocked node detection** (e.g., `ast.Exec`, dynamic code execution)
- **Centralized logging** of syntax errors and security violations
- **Consistent error handling** across all validation points

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│              ASTGateway (security/)                     │
│  🔒 SINGLE ENTRY POINT para ast.parse()                 │
│                                                         │
│  Components:                                            │
│  - parse(code: str) → ASTResult                         │
│  - validate(code: str) → ASTResult                      │
│  - _scan(tree: ast.AST) → List[str]                     │
│                                                         │
│  Security Features:                                     │
│  - SandboxRules validation (allowed modules)            │
│  - Blocked node detection (Exec, Eval, etc.)            │
│  - Error aggregation and structured reporting           │
└─────────────────┬───────────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┬─────────────────┐
    │             │             │                 │
┌───▼───┐   ┌────▼────┐   ┌───▼────┐      ┌─────▼─────┐
│  LSP  │   │ Syntax  │   │ Syntax │      │  Other    │
│Validator│   │Sentinel │   │.py    │      │  Modules  │
│(nodes/)│   │(nodes/) │   │(valid.)│      │  (future) │
└─────────┘   └─────────┘   └────────┘      └───────────┘
```

### Implementation Details

**ASTResult Dataclass:**
```python
@dataclass
class ASTResult:
    valid: bool
    tree: Optional[ast.AST]
    errors: List[str]
```

**Usage Pattern (Correct):**
```python
from iaglobal.security.ast_gateway import ASTGateway

_gateway = ASTGateway()
result = _gateway.parse(code)

if result.valid:
    # Safe to use result.tree
    for node in ast.walk(result.tree):
        ...
else:
    # Handle errors from result.errors
    logger.error(f"AST validation failed: {result.errors}")
```

### Modules Corrected (July 2026)

| Module | Before | After | Status |
|--------|--------|-------|--------|
| `graphs/nodes/no_lsp_validator.py` | `ast.parse(code)` | `_ast_gateway.parse(code)` | ✅ |
| `graphs/nodes/syntax_sentinel.py` | `ast.parse(code)` | `_ast_gateway.parse(code)` | ✅ |
| `validation/syntax.py` | `ast.parse(code)` | `_ast_gateway.parse(code)` | ✅ |
| `graphs/nodes/no_skill_generator.py` | Wrong import path | `iaglobal.evolution.skills.native.skill_generator_agent` | ✅ |
| `graphs/nodes/no_entropy_sentinel.py` | `iaglobal.security.entropy_sentinel` | `iaglobal.immunity.entropy_sentinel` | ✅ |
| `graphs/nodes/no_auditor_sentinel.py` | Wrong imports | `iaglobal.immunity.entropy_sentinel` + `iaglobal.core.graceful_shutdown` | ✅ |
| `pipeline/engine.py` | AST validation on markdown | Markdown/text detection → skip AST | ✅ |

### Security Scanning Features

The ASTGateway performs the following security checks on every parse:

1. **Import Validation**: Checks all `ast.Import` and `ast.ImportFrom` nodes against `SandboxRules.allowed_modules`
2. **Blocked Node Detection**: Prevents use of dangerous nodes like `ast.Exec`, `ast.Eval`, `ast.Compile`
3. **Error Aggregation**: Collects all errors in a single pass instead of failing on first error
4. **Structured Reporting**: Returns `ASTResult` with detailed error messages

### Metabolic Analogy

| Biological Component | Computational Equivalent |
|---------------------|-------------------------|
| **Nuclear membrane** | ASTGateway (controls access to AST) |
| **DNA transcription** | `ast.parse()` (converts code to AST) |
| **mRNA processing** | `_scan()` (validates and filters) |
| **Quality control** | `SandboxRules` (allowed modules list) |
| **Apoptosis trigger** | `result.valid == False` (rejects toxic code) |

### Validation Under Load

During the July 2026 correction cycle, the system demonstrated:

- **Before**: 3 import failures, health status = "comprometida"
- **After**: 0 import failures, health status = "estável"
- **Pipeline success rate**: Increased from ~60% to 100% for analysis tasks
- **Markdown detection**: Added heuristic detection to skip AST validation for reports

### Future Enforcement

**Remaining modules to migrate** (identified via grep, not yet corrected):

- `evolution/handler_evolution.py` (4 occurrences)
- `evolution/skills/utils/run_fn_factory.py` (1)
- `validation/ast_security.py` (2)
- `validation/gateway.py` (1)
- `validation/engine.py` (1)
- `validation/scoring.py` (1)
- `core/auto_correction.py` (2)
- `core/code_assembler.py` (4)
- `core/few_shot_provider.py` (1)
- `core/dependency_enforcer.py` (1)
- `utils/integrity.py` (2)
- `agents/critic_agent.py` (1)
- `agents/tester_agent.py` (1)
- `agents/ingestion/experiment_runner.py` (1)
- `agents/semantic_validator.py` (1)
- `search/search_code_extractor.py` (1)
- `execution/sandbox.py` (1)
- `immunity/glutathione_guardrails.py` (1)
- `tools/tool_library.py` (1)

**Migration strategy:** Each module should be updated to:
1. Import `ASTGateway` from `iaglobal.security.ast_gateway`
2. Create singleton instance: `_ast_gateway = ASTGateway()`
3. Replace `ast.parse(code)` with `_ast_gateway.parse(code)`
4. Handle `ASTResult` instead of raw `ast.AST`

---

## 4.7 Epigenetic Evolution of ToolLibrary (EETL)

EETL closes the autopoietic loop of the system: tasks that require repeated escalation to cloud models are converted into permanent local tools, eliminating external dependency.

### Architecture

```
ancestry_tree.jsonl ──► EvolutionaryWatchdog ──► ToolLibrary
       │                        │                      │
       │                    [padrão ≥3x]          [tool local]
       │                        │                      │
       ▼                        ▼                      ▼
Cognitive_Escalation    OmniMind apoptose        execução ~3s
```

### Components

| Module | Path | Function |
|--------|---------|--------|
| EvolutionaryWatchdog | `evolution/watchdog.py` | Scans `ancestry_tree.jsonl`, detects patterns (same `task_hash` ≥3x in cloud with IVM > 0.85) |
| Watcher in CriticAgent | `agents/critic_agent.py:_evolutionary_watchdog_check()` | After successful cloud escalation, checks pattern and registers tool |
| Watcher in Pipeline | `pipeline/engine.py:_async_learn_stage()` | At end of each pipeline, watchdog scans ancestry_tree |
| Enriched Ancestry | `graphs/bandit.py:_psc_register_ancestry()` | Now includes `task_hash` and `task_summary` in every record |
| RESET_METABOLIC | `agents/critic_agent.py:_check_metabolic_reset()` | If CriticAgent degraded ≥3x consecutively, emits reset via OmniMind |

### Activation Rules

1. **Cloud trigger**: CriticAgent escalates to cloud (Groq/NVIDIA) → success → `_evolutionary_watchdog_check()`
2. **Pattern ≥3x**: Watchdog.analyze() groups by `task_hash`, counts successful escalations
3. **Tool registration**: `watchdog.register_tool_from_pattern(pattern, code)` → `ToolLibrary.register_from_code(task, code)`
4. **Redundancy**: Pipeline `_async_learn_stage` also scans ancestry_tree after each execution

### Antioxidant Profile

| ROS | GSH |
|-----|-----|
| Repetitive cloud escalation | Local tool permanently registered |
| Degraded CriticAgent | RESET_METABOLIC + apoptosis |
| Obsolete tool | Next pattern replaces (overwrite) |
| Task_hash collision | SHA3-512[:16] — astronomically improbable collision |

### Differentiation Plan

- **Phase I**: Watchdog only monitors and registers tools in pipeline `_async_learn_stage`
- **Phase II**: CriticAgent actively calls watchdog post-cloud — accelerates detection
- **Phase III**: RESET_METABOLIC — autonomous recovery from degradation
PLACEHOLDER

### Evolutionary Vector
- **Next mutation**: Watchdog with negative feedback — if a registered tool is never used, it is removed (tool autophagy)
- **Selective pressure**: Every registered tool reduces execution time from 70s (cloud) to ~3s (local), creating strong evolutionary pressure for self-registration
PLACEHOLDER
PLACEHOLDER

---

## 5. Metabolic Cycles (Data Pipeline)

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

### Self-regeneration cycle (general)

1. **Detection** — `HomeostasisController.check_sla()` verifies latency/cost/error.
2. **Signaling** — violations trigger `_apply_epigenetic_adjustments()`.
3. **Recovery** — epsilon of `BanditPolicy` is dynamically adjusted.
4. **Learning** — `SkillRecycler.recycle()` reintegrates useful skills.
5. **Persistence** — pools use JSON files with thread locks (⚠️ with one exception — see §12).

---

## 6. Execution Pipeline (DAG)

> ⚠️ The original document describes the DAG at two different moments with different numbers: an initial synthesis mentions **55 nodes/7 phases**; later, lineage test coverage already mentions **115 executable nodes**. This matches the actual project growth — it's not an isolated typo, it's the project evolving between sections of the same file. I kept both versions, in the order they appear.

### Original structure (synthesis in 7 phases, 55 nodes)

1. **Definition** (23 nodes) — intake, enhancement, PM, requirements, architecture
2. **Planning** (3 nodes) — planner, task_breakdown, execution_plan
3. **Construction** (6 nodes) — coder, frontend/backend/database builder
4. **Quality** (7 nodes) — test_generator, integrator, audit
5. **Correction** (6 nodes) — qa, debugger, fix_validator
6. **Delivery** (9 nodes) — documentation, metrics, retrospective
7. **Metacognition** (7 nodes) — evaluator, gap_analyzer, evolution_trigger

### Metabolic flow of the evolutionary core

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

### Current state (according to directory tree, Appendix A)

`graphs/nodes/` contains **110 unique `no_*.py` files** in the provided tree (plus auxiliary modules `_search_*.py`) — consistent with the "115 executable nodes" cited in lineage test coverage. This confirms that the 55-node structure is an old snapshot of the system, not the current state.

---

## 7. Critic Sovereignty Protocol (CSP)

> **Principle**: The `iaglobal` operates as an organism with a central nervous system. Only `CriticAgent` has authority for external escalation (cloud). All other agents operate exclusively with local resources (ToolLibrary + Ollama).

### 7.1 Three-Layer Architecture

```
LOCAL AGENT (Coder, Planner, Tester, etc.)
    │
    ├─ ToolLibrary.match(prompt) → score ≥ 0.7?
    │    ├─ YES: executes Python tool directly (NADPH — 200ms, 0 LLM ATP)
    │    └─ NO: Ollama local (qwen2.5:0.5b)
    │
    └─ Result submitted to CriticAgent.evaluate()
         │
         ▼
CRITICAGENT (Single gateway to cloud)
    │
    ├─ 1. Local evaluation (Ollama) — preserves ATP
    ├─ 2. Score ≥ 60? → returns (local sufficient)
    ├─ 3. Score < 60? → escalates to cloud via BanditPolicy.generate(node_id="critic")
    │
    ▼
BANDITPOLICY (Selective membrane)
    │
    ├─ PSC §1.1: SecurityViolation if node_id does not contain "critic"
    ├─ PSC §1.2: IVM compliance — if homocysteine > 70%, blocks cloud
    ├─ Membrane: non-critical → only local Ollama (fail-closed)
    ├─ ε-greedy selection → semaphore → execution → metrics
    └─ PSC §1.3: Records Cognitive_Escalation in ancestry_tree.jsonl
```

### 7.2 Implementation

| Layer | File | Mechanism |
|--------|---------|-----------|
| **Primary** | `graphs/bandit.py:generate()` | `_psc_verify_caller(node_id)` — raises `SecurityViolation` if not critical |
| **Secondary** | `graphs/bandit.py` | `_psc_ivm_green()` — checks homocysteine before releasing cloud |
| **Tertiary** | `providers/provider_router.py:async_route_generate()` | Downgrades to local if node_id is not critical |
| **Prompt** | `agents/agent_base.py` | `PEC_SYSTEM_PROMPT` includes: *"Never access online models on your own"* |
| **Prompt** | `agents/prompt_improver.py` | Final instruction of every prompt includes PSC guideline |

### 7.3 Strict Execution Flow

```
Production Phase (Executor Agents):
    Coder, Planner, Tester process the task using:
    ├─ ToolLibrary (pure Python, 200ms, 0 LLM ATP)
    └─ Ollama local (qwen2.5:0.5b, temperature=0.1)

Filter Phase (CriticAgent):
    Generated content is sent to CriticAgent.evaluate()
    ├─ Score ≥ 70 → approved → ArtifactFactory
    ├─ Score ≥ 60 → approved (local sufficient)
    └─ Score < 60 or error → CriticAgent escalates to BanditPolicy (only authorized)

Escalation Phase (BanditPolicy):
    ├─ Verifies identity: only "critic" passes
    ├─ Checks IVM: if homocysteine > 70%, blocks cloud
    ├─ Selects cloud model (Groq/NVIDIA)
    └─ Records Cognitive_Escalation in ancestry_tree.jsonl
```

The correct flow is:
1. Planner → Breaks task
2. Search/Local Knowledge → Collects data (web + obsidian)
3. Filter/Validator → Filters data (source_validator)
4. Coder/FrontendBuilder → Generates code
5. Tester → Tests the code
6. Reviewer → Reviews
7. Critic → Evaluates score
   ├─ Score < threshold → Loop (returns to 3 or 4)
   └─ Score >= threshold → Approves
8. BanditPolicy → Selects model (after approval)
9. ArtifactWriter → Persists result
10. Reflexion → Learning (if failed) or Commit (if success)

### 7.4 Security Semaphores

| Verification | Where | Effect |
|-------------|------|--------|
| Caller identity | `bandit.py:generate()` | `SecurityViolation` if not critical |
| Systemic homocysteine | `bandit.py:_psc_ivm_green()` | Blocks cloud if > 70% of threshold |
| Selective membrane | `bandit.py:_membrane_filter_candidates()` | Non-critical → only Ollama (fail-closed) |
| Provider router | `provider_router.py:async_route_generate()` | Downgrades to local if node_id is not critical |

### 7.5 Ancestry Tracking

Every successful cloud escalation registers a JSON record in `DATA_DIR/ancestry_tree.jsonl`:

```json
{
  "type": "Cognitive_Escalation",
  "node_id": "critic",
  "model": "groq/llama-3.3-70b-versatile",
  "latency_ms": 1234.56,
  "success": true,
  "timestamp": "2026-07-10T16:16:50.434918+00:00"
}
```

### 7.6 Immunity Diagram

```
LOCAL AGENT (Coder)
    │ direct call to BanditPolicy.generate()
    ▼
PSC §1.1 ──► SecurityViolation ✋ BLOCKED
    │
    │ (via CriticAgent)
    ▼
CriticAgent._avaliar_multidimensional()
    ├─ Ollama local → score ≥ 60? → OK (no cloud)
    └─ Ollama local → score < 60? → 
         │
         ▼
    BanditPolicy.generate(node_id="critic")
         ├─ PSC §1.1: critic ✅ passes
         ├─ PSC §1.2: IVM green? → YES
         ├─ Membrane: critical → cloud released
         ├─ Selects model → executes → metrics
         └─ PSC §1.3: ancestry_tree.jsonl ← Cognitive_Escalation
              │
              ▼
    CriticAgent validates cloud result → approved/rejected
```

### 7.7 Prompt Directive (Meta-Directive)

Injected via `PEC_SYSTEM_PROMPT` in `agent_base.py` and in the final instruction of `prompt_improver.py`:

> "PSC — Critic Sovereignty Protocol: You must never attempt to access online models on your own. Your autonomy is limited to local resources (ToolLibrary + Ollama). If your local task is insufficient, submit the result to CriticAgent. Trust the Critic's authority to decide on escalation to BanditPolicy."

### 7.8 Final Architecture — Arbiter Portão (2026-07-12)

Após a migração completa do PSC (Integrações #4 e #5 do ROADMAP_2.md), a arquitetura foi simplificada para **4 camadas rígidas** com um único portão de saída (`arbitrar_geracao`):

```
┌─────────────────────────────────────────────────────────┐
│  Layer 3: AGENTES (coder, tester, planner, pm, etc.)    │
│                                                         │
│  agent_base._call_llm(node_id=self.agent_name)          │
│  execution_graph fallback(node_id=node.name)             │
│         │                                               │
│         └──→ arbitrar_geracao()  ←── ÚNICO PORTÃO      │
├─────────────────────────────────────────────────────────┤
│  Layer 2: CRITIC (CriticAgent)                          │
│                                                         │
│  arbitrar_geracao(node_id, prompt, task_type):           │
│    ├─ 1. Tenta tools (ToolLibrary.match)               │
│    ├─ 2. Tenta memória (MemoryFirstRouter)              │
│    ├─ 3. Credita cooperação (componente C do IVM)      │
│    └─ 4. Escala → BanditPolicy.generate(               │
│                  node_id="critic",                      │
│                  context={"delegate_for": node_id})      │
├─────────────────────────────────────────────────────────┤
│  Layer 1: BANDIT POLICY (Gatekeeper)                    │
│                                                         │
│  generate(node_id, prompt, candidates, context):         │
│    ├─ PSC §1.1: só "critic" passa (exata, não substring)│
│    ├─ Membrana: fail-closed (não-crítico → Ollama local)│
│    ├─ effective_agent = context.get("delegate_for",     │
│    │                     node_id)  ← auditoria IVM      │
│    ├─ ε-greedy + semáforo + credit_engine              │
│    └─ async_route_generate(node_id=node_id CRU)         │
├─────────────────────────────────────────────────────────┤
│  Layer 0: PROVIDER ROUTER (provider_router)             │
│                                                         │
│  async_route_generate(model, prompt, task_type,         │
│                       node_id)                          │
│    └─ ÚNICO arquivo que importa providers/              │
│       (Groq, NVIDIA, Ollama, Gemini, OpenRouter)        │
└─────────────────────────────────────────────────────────┘
```

**Fluxo de chamada LLM (único caminho correto):**

```
agent → arbitrar_geracao() → Bandit.generate() → provider_router → API
layer 3       layer 2            layer 1            layer 0
```

**effective_agent (delegate_for):**

Quando `arbitrar_geracao` escala para o BanditPolicy, passa:
- `node_id="critic"` — satisfaz PSC (identidade do portão)
- `context={"delegate_for": "reflexion"}` — nome do agente original

Dentro de `BanditPolicy.generate()`, `effective_agent = context.get("delegate_for", node_id)`:
- **Auditoria** (`ExecutionEvent.node`) — usa `effective_agent`
- **Ancestry Tree** — usa `effective_agent`
- **IVM** — usa `effective_agent`
- **Chamada ao provider** (`async_route_generate(node_id=...)`) — usa `node_id` CRU

Isso garante que:
1. **PSC** é satisfeito (quem passa pelo portão é o crítico)
2. **Membrana** opera corretamente (critic tem acesso cloud)
3. **Auditoria** credita o agente real que gerou o trabalho
4. **BanditPolicy** seleciona modelo livremente baseado em crédito + Chappie

**Arquivos envolvidos:**
- `iaglobal/agents/critic_agent.py` → `arbitrar_geracao()` + `_creditar_cooperacao()`
- `iaglobal/agents/agent_base.py` → `_call_llm()` (chama `_get_critic().arbitrar_geracao()`)
- `iaglobal/graphs/execution_graph.py` → fallback (chama `_get_critic().arbitrar_geracao()`)
- `iaglobal/graphs/bandit.py` → `generate()` com `effective_agent` + `_psc_verify_caller()`
- `iaglobal/providers/provider_router.py` → único arquivo que importa provedores externos

**NENHUM salto de camada é permitido. Exemplos proibidos:**
- ❌ `coder` não chama `BanditPolicy.generate()` diretamente — viola PSC (apoptose)
- ❌ `reflexion` não chama `async_route_generate()` diretamente — viola hierarquia
- ❌ `tester` não importa de `iaglobal.providers` — viola gate de autoridade

---

## 8. Evolutionary Engine (Genomic Reflection)

```
AGENT EXECUTION
       ↓
ResultAgent registers ExecutionMetrics
       ↓
GenomicReflection.analyze_performance()
       ↓
Identifies best_traits / worst_traits
       ↓
propose_mutations_async()
       ↓
Mutation type: TRAIT_ENHANCEMENT (success) · TRAIT_SUPPRESSION (failure) · TRAIT_ADDITION (missing)
       ↓
validate_with_bandit_async()  →  custom validator, or fallback: confidence > 0.6
       ↓
apply_mutation_async()
       ↓
DNA updated in FusionEngine
```

### Boot chain (from CLI to `EvoAgent`)

```
CLI / IAGlobalAPI
    └─► bootstrap.initialize()          # cli/bootstrap.py
            └─► Orchestrator()          # core/orchestrator.py  ← CENTRAL POINT
                    ├─► EvolutionEngine(graph, strategies)
                    ├─► EvolutionRuntime(evolver, interval)
                    ├─► ReflexionEngine(model_fn)
                    ├─► BanditPolicy / CreditAssignmentEngine
                    ├─► PipelineEngine
                    ├─► graceful_shutdown.add_callback(...)
                    └─► if EVOLUTION_AUTO=1:
                            evolution_runtime.start()   ← EvoAgent enters here
```

The `EvoAgent` does not replace the `Orchestrator` — it runs within the existing infrastructure. Correct initialization location (`core/orchestrator.py`, after `self.evolution_runtime`):

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

In the `run()` of the `Orchestrator`, before executing the pipeline, the input can pass through `evo_agent.handle()` to obtain genomic expression and use GSH cycles + methylation as immunological pre-processing of the prompt.

### 7.1 EvoAgent ↔ AgentBase Integration (4-Module Reflection)

All agents that inherit from `AgentBase` gain the 4 native reflection modules of iaglobal, consumed via a single `EvoAgent` per **agent lineage** (`agent_name`). This preserves the evolutionary family (same `lineage_marker`) and avoids instantiating thousands of unnecessary organisms.

**Integration Metabolic Cycle**

```
Agent (inherits AgentBase)
    ↓ self.get_evo_agent()  [lazy — 1 EvoAgent per agent_name in _EVO_REGISTRY]
EvoAgent (controlled mitosis by lineage)
    ├─ self_critique()        → reflection.self_critique.SelfCritique        (pure heuristic, no LLM)
    ├─ reflexion_fix()        → reflection.reflexion_engine.ReflexionEngine   (gated: evo_reflexion_enabled)
    ├─ analyze_failure()      → reflection.failure_analysis.FailureAnalyzer   (immunological memory)
    └─ learning_iterate()     → reflection.learning_loop.LearningLoop         (gated: evo_learning_enabled)
```

AgentBase maintains an _EVO_REGISTRY that creates one EvoAgent per agent_name on demand. Every agent inheriting from AgentBase consumes evolution by delegation:

```
AgentBase
 ├── evo_self_critique()      → SelfCritique (pure, CPU-bound)
 ├── evo_reflexion_fix()      → ReflexionEngine
 ├── evo_analyze_failure()    → FailureAnalyzer + VaccineLedger
 └── evo_learning_iterate()   → LearningLoop
```

**Implementation Points**

| Location | Change |
|---|---|
| `evolution/evo_agent.py` | Imports `FailureAnalyzer`, `SelfCritique`, `LearningLoop` (and `ReflexionEngine` on demand). Exposes `self_critique`, `reflexion_fix`, `analyze_failure`, `learning_iterate`. `reflexion_fix` triggered in `critical` path of `_analysis_and_action`. |
| `agents/agent_base.py` | `_EVO_REGISTRY` (1 EvoAgent per `agent_name`) + `get_evo_agent()`. 4 delegates `evo_self_critique / evo_reflexion_fix / evo_analyze_failure / evo_learning_iterate`. Non-blocking auto-hook in `_call_llm`: post-response self-critique + failure analysis on exception. |
| `evolution/epigenetic.py` | Flags: `evo_self_critique=True` (cheap), `evo_reflexion_enabled=False`, `evo_learning_enabled=False` (prevent uncontrolled ATP/LLM consumption). |
| `models/event_bus.py` | `EventType` gained `REFLECTION_COMPLETED`, `EXECUTION_FAILED`, `MEMORY_SAVED` (fixed `AttributeError` in `ReflexionEngine.reflect`). |

**Metabolic cost (ATP):** self-critique and failure analysis are pure heuristics — run on every `_call_llm` without consuming LLM. ReflexionEngine and LearningLoop remain `False` by default, activatable by epigenetic flag according to selective pressure.

#### P0.1 — Event Loop Reuse in Reflection

**Original problem:** `_evo_model_fn()` in `agent_base.py` created a NEW event loop (`asyncio.new_event_loop()`) on every reflection call from `EvoAgent`, generating unnecessary overhead and making monitoring of the main loop impossible.

**Fix:** Replaced with `asyncio.run()`, which manages the loop lifecycle correctly and is the canonical way to run coroutines in synchronous context.

```python
def _evo_model_fn(self, prompt: str) -> str:
    try:
        return asyncio.run(self._call_llm(prompt=prompt, task_type="reflection"))
    except Exception as e:
        logger.debug("[%s] evo_model_fn failed: %s", self.agent_name.upper(), e)
        return ""
```

#### P0.2 — Epigenetic Weights per Agent (IVM)

**Original problem:** `IVMAxiom._ajustar_pesos_epigeneticos()` modified **global** attributes (`self._peso_produtividade`, `self._peso_eficiencia`, `self._peso_cooperacao`). An agent with high latency moved the E→P weight for **all others**, distorting the global ranking.

**Fix:** Weights migrated to `IVMMetrics` (dataclass per agent):

| Attribute | Before (global) | After (per agent) |
|----------|---------------|---------------------|
| Weight P | `IVMAxiom._peso_produtividade` | `IVMMetrics.productivity_weight` |
| Weight E | `IVMAxiom._peso_eficiencia` | `IVMMetrics.energy_weight` |
| Weight C | `IVMAxiom._peso_cooperacao` | `IVMMetrics.cooperation_weight` |

`_ajustar_pesos_epigeneticos()` now modifies `metricas.productivity_weight` etc. The `atualizar_metricas()` of IVMMetrics uses:

```python
ivm = (metricas.productivity_score * metricas.productivity_weight +
       metricas.energy_score * metricas.energy_weight +
       metricas.cooperation_score * metricas.cooperation_weight)
```

**Efeito:** dois agentes com perfis de latência opostos (100ms vs 5000ms) têm pesos IVM independentes — a distorção de um não contamina o ranking do outro.

**Testes:** `tests/test_evo_agent_reflection_integration.py` (13 testes — 4 módulos, delegação AgentBase, registry por linhagem, auto-crítica em `_call_llm`).

### 7.2 Vacinas por Linhagem — failure_patterns no Obsidian × ImmuneMemoryExchange

Mutação subsequente: a memória imunológica do `EvoAgent` (`_failure_patterns`, alimentada por `FailureAnalyzer`) é **persistida no vault Obsidian** e cruzada com `ImmuneMemoryExchange` para produzir **vacinas entre agentes da mesma linhagem** — modelo de célula T de memória computacional.

```
EvoAgent.analyze_failure(error)
    ↓
vaccine_ledger.registrar_falha(evo, pattern, context)
    ├─ 1. Persiste 05_Vaccines/linhagem_<marker>.md (SubconsciousAPI, async)
    ├─ 2. Dedupe por pattern (evita acúmulo de homocisteína repetida)
    └─ 3. immune_memory_exchange.publish_vaccine(marker, [pattern])   ← transporte entre nós
            ↓
    Nó receptor: immune_memory_exchange.import_vaccine(remote)
            ↓ gating: só aceita se marker ∈ linhagens deste nó (vaccine_ledger.owns_lineage)
    vaccine_ledger escreve no ledger Obsidian da linhagem

EvoAgent.genesis(...)
    ↓
vaccine_ledger.aplicar_vacina(agent)   ← pré-carrega _failure_patterns da PRÓPRIA linhagem
```

**Componentes**

| Módulo | Papel |
|---|---|
| `immunity/vaccine_ledger.py` | Singleton. `registrar_falha`, `vacinas(marker)`, `aplicar_vacina(evo)`, `registrar_linhagem`, `owns_lineage`. Mantém `_known_markers` (linhagens deste nó). |
| `obsidian/subconsciousapi.py` | Novo diretório `05_Vaccines` + `escrever_vacina` / `ler_vacina` (async, `asyncio.to_thread`). |
| `immunity/immune_memory_exchange.py` | `publish_vaccine(marker, patterns)` e `import_vaccine(remote, source)` — gating de linhagem: vacina de família estranha é recusada (sem autoimunidade arquitetural). |
| `evolution/evo_agent.py` | `genesis` registra o marker e aplica a vacina; `analyze_failure` persiste o padrão. |
| `evolution/epigenetic.py` | Flag `evo_vaccine_persist=True`. |

**Gating evolutivo (não-autoimunidade):** `aplicar_vacina(evo)` só carrega padrões do `lineage_marker` do próprio agente; `import_vaccine` só persiste vacinas de linhagens que este nó já conhece. Agentes de linhagem distinta nunca herdam memória um do outro.

**Testes:** `tests/test_vaccine_ledger.py` (8 testes — persistência Obsidian, dedupe, aplicação por linhagem via `replicate()`, recusa de linhagem estranha, import do `ImmuneMemoryExchange`).

**Modos de ativação do `EvolutionRuntime`:**

| Modo | Como ativar |
|---|---|
| Automático em background | `EVOLUTION_AUTO=1` no `.env` |
| Manual via API | `orchestrator.evolution_runtime.start()` |
| Direto (demo/teste) | `asyncio.run(demo())` em `evo_agent.py` |

---

## 9. Universal Laws Applied

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

## 10. Obsidian Module — Subconscious

Modelo de mente em três níveis usando Markdown real com YAML frontmatter, tags e links bidirecionais `[[...]]` — 100% legível e editável por humanos.

```
obsidian/
├── 01_Instincts/    → Diretrizes imutáveis (imutavel: true no frontmatter)
├── 02_Short_Term/   → Memórias brutas (erros, eventos do dia)
├── 03_Long_Term/    → Conhecimento consolidado (saída do ciclo REM)
├── 04_Synapses/     → Mapa sináptico central (índice automático de tags/links)
└── 05_Vaccines/     → Vacinas por linhagem (failure_patterns persistidos — §7.2)
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

### Integration with evolution

- **IVM**: `obsidian_notes_escritas` is a Cooperation metric (weight 0.2) — agents that document in Obsidian have higher fitness.
- **Lineage**: `exportar_nota_agente()` creates `03_Long_Term/agentes/{id}.md` with `strategy`, `fitness`, `parent_link`.
- **OmniMind**: `EvoAgent` queries the singleton `omni_mind` for existential guidance.

### Vault state (according to original document)

| Directory | Status | Content |
|---|---|---|
| `01_Instincts/` | Empty | API ready via `escrever_instinto()` |
| `02_Short_Term/` | Empty | 9 errors consolidated and pruned |
| `03_Long_Term/` | 9 notes | Errors consolidated by `REMSleepEngine` (fallback mock) |
| `04_Synapses/` | 1 map | `Mapa_Mental_Subconsciente.md`, index of 9 notes and 2 active tags |

**Pending bottleneck:** synthesis used mock fallback (`_mock_sintese`). To consolidate with real insights:

```python
from iaglobal.obsidian.consolidation import REMSleepEngine
REMSleepEngine(ai_client=meu_client_llm).iniciar_fase_rem()
```

---

## 11. Asynchronous Communication

The iaglobal communication system is modeled as **cellular signaling** — a 4-layer architecture that goes from external authorization to final delivery in each agent's inbox.

### 10.1 Communication Layers

```
Simbiote / Nó Remoto
       |
       | GenesisHandshake (SHA3-512, HMAC, nonce)
       v
 ┌───────────────────┐      ┌─────────────────┐
 │   MembraneKey     │ ───→ │    Membrane     │
 │ (credenciais +    │      │ (isolamento por │
 │  permissões)      │      │  organela)      │
 └───────────────────┘      └────────┬────────┘
                                     | MembraneMessage
                                     v
 ┌─────────────────────────────────────────────┐
 │          AcetylcholineBus                   │
 │  (barramento pub/sub central — assíncrono)  │
 └──────────────────┬──────────────────────────┘
                    | AgentMessage
                    v
 ┌─────────────────────────────────────────────┐
 │          MailboxManager                     │
 │  (roteia para inbox do destinatário +      │
 │   outbox do remetente)                      │
 └──────────────────┬──────────────────────────┘
                    |
 ┌──────────────────┴──────────────────────────┐
 │          AgentMailbox (por agente)          │
 │  cada agente consome via process_inbox()    │
 └─────────────────────────────────────────────┘
```

### 10.2 `AcetylcholineBus` — Neurotransmissor Central

**Arquivo:** `iaglobal/graphs/communication/acetylcholine_bus.py`

Barramento pub/sub assíncrono — o "sistema nervoso" do organismo. Toda comunicação entre agentes passa por ele.

- `AgentMessage` (dataclass imutável) — envelope com `sender`, `recipient`, `content`, `payload`, `message_type`, `priority`, `timestamp`, `id` (UUID).
- `AcetylcholineBus` — mantém `dict[str, Set[Callable]]` de inscritos por nome, tipo ou `"*"` (wildcard). Métodos: `subscribe()`, `unsubscribe()`, `emit()` (async).
- `bus = AcetylcholineBus()` — instância singleton module-level.
- Histórico: deque com até 500 mensagens.

### 10.3 `AgentMailbox` / `MailboxManager` — Inbox/Outbox por Agente

**Arquivo:** `iaglobal/graphs/communication/agent_mailbox.py`

Cada agente possui uma caixa postal dedicada — inbox para mensagens recebidas, outbox para enviadas.

- `AgentMailbox(agent_name)` — `receive()`, `send()`, `process_inbox(max=10)`, `pending_received()`, `pending_sent()`, `clear()`.
- `MailboxManager` — gerencia `dict[str, AgentMailbox]`. `route_to_mailbox(message)` copia para inbox do receiver + outbox do sender.
- Integrado ao `AcetylcholineBus` via mesmo formato `AgentMessage`.

### 10.4 `Membrane` — Isolamento por Organela

**Arquivo:** `iaglobal/graphs/membrane.py`

Camada de isolamento lógico entre subsistemas (organelas). Uma falha em uma organela **não se propaga** para as demais.

- `Organelle(Enum)` — `INGESTION`, `CORE`, `EVOLUTION`, `IMMUNITY`, `DELIVERY`, `METACOGNITION`.
- `MembraneMessage` — `source`, `target` (Organelle), `event_type`, `payload`, `critical`.
- `Membrane` — `register_handler(organelle, handler)`, `send(message)`.
- **Regra de segurança:** organelas não-CORE não podem **escrever** em organelas CORE (apenas `query`/`read`). Toda mensagem externa passa por validação de `MembraneKey`.

### 10.5 `MembraneKey` — External Symbiont Authentication

**Arquivo:** `iaglobal/graphs/communication/membrane_key.py`

Gera chaves criptográficas para entidades externas que desejam se comunicar com o ecossistema iaglobal.

- `MembraneKey` (Singleton) — `generate_key(system_name, permissions)`, `validate_key(system_name, key)`, `grant_permission()`, `revoke_key()`.
- IDs fonéticos soberanos derivados de SHA3-512 do hash gênese + nome do sistema + token aleatório.

### 10.6 `GenesisHandshake` — Handshake entre Organismos

**Arquivo:** `iaglobal/communication/genesis_handshake.py`

Protocolo de autenticação mútua entre nós iaglobal remotos, baseado no lineage marker SHA3-512.

- 4 passos: `INIT → CLIENT_HELLO → SERVER_HELLO → VERIFIED`.
- HMAC-SHA3-512 para assinatura de nonces (validade máxima: 60s).
- Confiança baseada no hash gênese compartilhado — sem X.509, sem CA.

### 10.7 Isolamento por Subprocesso (`Organism`)

**Arquivos:** `iaglobal/core/organism.py`, `iaglobal/core/organism_main.py`

Cada organismo iaglobal pode rodar em **processo isolado** — memória, event loop, SQLite e BanditPolicy próprios.

- `Organism(organism_id, data_root)` — `asyncio.create_subprocess_exec` para `organism_main.py`.
- Comunicação JSON-RPC sobre stdin/stdout: `ping`, `run_task`, `shutdown`.
- Cada organismo recebe `ORGANISM_DATA_ROOT` próprio → isolamento total de dados.
- Graceful stop com `terminate()` → `kill()` fallback.

### 10.8 Colony Communication via AcetylcholineBus (Estendido)

`AgentMessage` foi estendido com `organism_id: str = "iaglobal"` para distinguir a origem da mensagem entre múltiplos organismos na colônia. Três novos tipos de mensagem foram adicionados:

| Tipo | Payload | Descrição |
|------|---------|-----------|
| `task_offer` | `{task_id, type, description, parent}` | Um organismo oferece subtarefa para outro |
| `result_share` | `{task_id, type, parent, result, success, latency_ms, worker_id}` | Devolução de resultado processado |
| `skill_handshake` | `{organism_id, skills, lineage_marker}` | Troca de capacidades entre organismos |

O `AcetylcholineBus.emit()` agora também roteia por `organism_id`: inscrições no canal `"org:<id>"` recebem mensagens daquele organismo específico. Isso permite que uma colônia de organismos (Queen + Workers + Integrator) se coordene sem cruzamento de mensagens entre colônias distintas.

Arquivos: `iaglobal/graphs/communication/acetylcholine_bus.py`, `iaglobal/communication/queen.py`, `iaglobal/communication/worker.py`, `iaglobal/communication/integrator.py`, `iaglobal/communication/fitness.py`.

```
┌───────────────────────────────────────────────────────┐
│                  Colony Supervisor                    │
│   (processo pai — gerencia birth/death dos filhos)    │
├───────────────────────────────────────────────────────┤
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Organism A   │  │ Organism B   │  │ Organism C   │ │
│  │ PID: 12345   │  │ PID: 12346   │  │ PID: 12347   │ │
│  │              │  │              │  │              │ │
│  │ Orchestrator │  │ Orchestrator │  │ Orchestrator │ │
│  │ DATA_ROOT_A  │  │ DATA_ROOT_B  │  │ DATA_ROOT_C  │ │
│  │ Bus (local)  │  │ Bus (local)  │  │ Bus (local)  │ │
│  │ Queue (local)│  │ Queue (local)│  │ Queue (local)│ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                 │         │
│         └─────────────────┼─────────────────┘         │
│                     ▲     │     ▲                     │
│                     │  IPC Bus  │                     │
│                     │  (stdin/stdout JSON-RPC)        │
└───────────────────────────────────────────────────────┘
```

### 10.8 Integration with Security

- `SandboxExecutor` (`iaglobal/security/sandbox_executor.py`) — execução de código em subprocesso com AST Gateway + SandboxRules + GlutathioneGuardrails + isolamento de rede.
- `NetworkGuard` (`iaglobal/security/network_guard.py`) — monkey-patch de `socket` para bloquear rede não-autorizada. Qualquer tentativa dispara MHC Detector.
- `resource_limits.py` — `setrlimit` com limites duros: 256MB RAM, 10s CPU, 1MB arquivo, 20 processos filho.
- `controlled_subprocess.py` — executor whitelist-based (pip, python, git em /tmp). Sem `shell=True`.

### 10.9 Differentiation and Scaling

- `MetaAgentDesigner.design_team()` — detecta keywords e ativa especialistas conforme demanda.
- `specialization_instructions` — injeta contexto de especialização no nó.
- `CpuAffinityManager` — mapeia nós em núcleos para balanceamento em hardware limitado.

### 10.10 Operational Epigenetics (`epigenetic.py`)

| Flag | Valor padrão | Propósito |
|---|---|---|
| `bandit_epsilon` | 0.2 | Taxa de explore/exploit |
| `sam_budget_multiplier` | 1.0 | Multiplicador de budget metabólico |
| `max_iterations` | 5 | Limite de reflexões |
| `homeostasis_enforcement` | True | Ativa ajuste automático de SLA |

Configurações que sobrevivem a restarts: `bandit_epsilon`, `sam_budget_multiplier`, `max_iterations`, `homeostasis_enforcement`.

---

## 10.11 Project Synapse — Reactive Nervous System

> **Objetivo**: Transformar comunicação de "passiva" (pipeline sequencial) para "ativa" (dispatch-based), permitindo que agentes processem tarefas automaticamente conforme mensagens chegam em suas mailboxes.

### Arquitetura

```
AGENTE A (finaliza) → posta resultado na inbox do AGENTE B
                          │
                          ▼
                    AGENTE B detecta mensagem (heartbeat)
                          │
                          ▼
                    processa automaticamente → posta na inbox do AGENTE C
```

### Componentes

| Módulo | Classe | Função |
|--------|--------|--------|
| `iaglobal/graphs/communication/agent_mailbox.py` | `AgentMailbox` | Caixa postal com inbox/outbox + executor + dispatch |
| `iaglobal/graphs/communication/agent_mailbox.py` | `MailboxManager` | Gerenciador central de sinapses + heartbeat loop |
| `iaglobal/core/orchestrator.py` | `Orchestrator` | Integração: `_bind_agents_to_mailboxes()`, `start_heartbeat_loop()` |

### AgentMailbox

```python
class AgentMailbox:
    - inbox: List[Dict]  # mensagens recebidas
    - outbox: List[Dict]  # mensagens enviadas
    - executor: Callable  # função async que processa mensagens
    - receive(message)  # adiciona à inbox
    - process_next(ctx)  # processa próxima mensagem (Lei da Não-Resistência)
    - set_executor(func, compliance_approved)  # Lei da Obediência
```

### MailboxManager

```python
class MailboxManager:
    - get_or_create(agent_name)  # factory de mailboxes
    - register_compliance(agent, approved)  # Lei da Obediência
    - bind_executor(agent, func)  # bind dinâmico
    - route_message(message)  # roteia para inbox do receiver
    - broadcast(message)  # sinal sistêmico (ex: RESET_METABOLIC)
    - heartbeat()  # desperta agentes com mensagens pendentes
    - run_heartbeat_loop()  # loop contínuo em background
```

### Leis de Holliwell Aplicadas

| Lei | Implementação |
|-----|---------------|
| **Não-Resistência** | `process_next()` retorna `None` se inbox vazia — não força execução |
| **Obediência** | `set_executor()` verifica `compliance_approved` antes de bindar |
| **Cooperação** | Agente finalizado posta resultado na `outbox` do sucessor automaticamente |

### Execution Flow (Exemplo: React Component)

```
1. Orchestrator.dispatch_to_agent("PlannerAgent", {"task": "crie UserCard.jsx"})
2. PlannerAgent mailbox recebe → heartbeat detecta → processa
3. PlannerAgent finaliza → posta {"type": "plan_ready", "payload": {...}} na inbox do CoderAgent
4. CoderAgent mailbox recebe → heartbeat detecta → processa
5. CoderAgent consulta Librarian (ToolLibrary) → gera código
6. CriticAgent recebe → compliance check → approval/rejection
```

### Metrics: Pipeline vs Synapse

| Indicador | Pipeline (antes) | Synapse (agora) |
|-----------|------------------|-----------------|
| Latência total | 81 nós × 30s = 40min | paralelismo real = ~5min (meta) |
| Agentes ociosos | 80/81 esperando | 0% — todos reativos |
| Acoplamento | rígido (sequencial) | frouxo (event-driven) |
| Escalabilidade | vertical (mais CPU) | horizontal (mais mailboxes) |
| Resiliência | falha em cascata | isolamento (mailbox por agente) |

### Integration in Orchestrator

```python
# No initialize() do Orchestrator:
self.mailbox_manager = mailbox_manager
self._bind_agents_to_mailboxes()  # bind dinâmico com compliance check

# Uso em background:
asyncio.create_task(orchestrator.start_heartbeat_loop(sleep_interval=0.5))

# Dispatch ativo:
await orchestrator.dispatch_to_agent("PlannerAgent", {"task": "crie UserCard.jsx"})
```

### Teste de Enxame

```python
from iaglobal.graphs.communication.agent_mailbox import MailboxManager

manager = MailboxManager()
manager.register_compliance("PlannerAgent", approved=True)
manager.bind_executor("PlannerAgent", planner.generate)

# Dispatch
manager.route_message({
    "type": "task",
    "receiver": "PlannerAgent",
    "payload": "crie componente React",
})

# Heartbeat processa automaticamente
await manager.heartbeat()
# Log: "[HEARTBEAT] Despertando PlannerAgent para processar 1 tarefas"
```

---

## 10.12 Dynamic Processing Privilege — CPU Boost for Critical Batches

**Problema metabólico:** Em hardware limitado (4 núcleos, 0 GPU), 30+ agentes competindo por CPU simultaneamente causam *thrashing* de contexto — o sistema gasta mais ciclos trocando entre agentes do que executando trabalho útil. O `orchestrator_pump` sofre com IVM baixo (~0.49) devido à contenção de I/O.

**Solução:** Mecanismo de **boost de prioridade de CPU** que concentra poder computacional nos agentes envolvidos em batches críticos (ex: avaliação do `CriticBatchQueue`), enquanto agentes de fundo entram em modo de economia de energia.

### Arquitetura do Boost

```python
# iaglobal/execution/cpu_affinity.py

class CpuAffinityManager:
    async def set_priority_boost(
        self,
        agent_ids: List[str],
        boost_percent: int = 50  # Teto = BUDGET_ADRENALINA (50%)
    ) -> None:
        """Aumenta budget de CPU para agentes de um batch crítico."""
        
    async def reset_budgets(self) -> None:
        """Restaura homeostase: todos os agentes voltam a 25%."""
        
    async def enter_critical_batch(
        self,
        agent_ids: List[str],
        boost_percent: int = 60
    ) -> List[str]:
        """Context manager: aplica boost e retorna agentes afetados."""
        
    async def exit_critical_batch(self, agent_ids: List[str]) -> None:
        """Cleanup: restaura homeostase após batch crítico."""
```

### Integration with CriticBatchQueue

```python
# iaglobal/core/critic_batch_queue.py

async def evaluate_with_context(self, memory, task, coder_output, bandit):
    # 1. Extrai avaliações prévias
    reviewer = memory.get("reviewer", {})
    qa = memory.get("qa", {})
    
    # 2. Aplica boost de CPU nos agentes do batch
    agentes_envolvidos = ["critic_batch", "reviewer", "qa", "coder"]
    await cpu_affinity.set_priority_boost(agentes_envolvidos, boost_percent=60)
    
    try:
        # 3. Executa avaliação crítica
        raw = await self._call_llm(prompt, bandit)
        return self._parse_resposta(raw)
    finally:
        # 4. Garante retorno à homeostase (mesmo com erro)
        await cpu_affinity.reset_budgets()
```

### Metabolic Flow

```
BATCH CRÍTICO (CriticBatchQueue)
     ↓
[CPU] ⚡ Boost aplicado: critic_batch → 50%
[CPU] ⚡ Boost aplicado: reviewer → 50%
[CPU] ⚡ Boost aplicado: qa → 50%
[CPU] ⚡ Boost aplicado: coder → 50%
[CPU] 🚀 Batch crítico com 4 agentes em alta prioridade (50% CPU)
     ↓
EXECUTA AVALIAÇÃO COM VALIDAÇÃO CRUZADA
     ↓
[CPU] 📉 Homeostase restaurada: todos os agentes em 25% CPU
```

### Measurable Benefits

| Métrica | Antes | Depois (esperado) |
|---------|-------|-------------------|
| Agentes competindo por CPU | 30+ simultâneos | 4 em boost, 26 em 25% |
| IVM do `orchestrator_pump` | ~0.49 (crítico) | >0.60 (seguro) |
| Thrashing de contexto | Alto | Mínimo |
| Latência do batch crítico | Variável | Concentrada |
| Homeostase pós-batch | Manual | Automática (`finally`) |

### Constantes de Budget

| Modo | Valor | Uso |
|------|-------|-----|
| `BUDGET_PADRAO` | 0.25 (25%) | Homeostase normal |
| `BUDGET_ADRENALINA` | 0.50 (50%) | Teto de boost (emergência) |
| `BUDGET_SOBREVIVENCIA` | 0.10 (10%) | Modo nômade |
| `BUDGET_DEEP_SLEEP` | 0.05 (5%) | Ciclo de repouso |

### Testes

`tests/test_cpu_priority_boost.py` (7 testes):
- `test_set_priority_boost_aplica_aumento` ✅
- `test_set_priority_boost_respeita_teto` ✅
- `test_reset_budgets_restaura_homeostase` ✅
- `test_enter_critical_batch_context` ✅
- `test_enter_exit_critical_batch_com_erro` ✅
- `test_boost_apenas_em_agentes_registrados` ✅
- `test_boost_preserva_agents_nao_envolvidos` ✅

### Applied Metabolic Corrections (Fase E, P1.1–P1.2)

O `CpuAffinityManager` recebeu duas correções estruturais pós-integração EvoAgent:

#### P1.1 — `exit_critical_batch()` Restritivo

**Problema original:** `exit_critical_batch()` chamava `reset_budgets()`, zerando **todos** os agentes para 25%. Se dois subsistemas usassem `enter_critical_batch` concorrentemente, o primeiro `exit` destruía o boost do segundo.

**Correção:** `enter_critical_batch()` agora retorna `Dict[str, float]` (agent_id → budget anterior). `exit_critical_batch()` restaura **apenas** os agentes boosted para seus budgets anteriores.

```python
async def enter_critical_batch(self, agent_ids: List[str], boost_percent: int = 60) -> Dict[str, float]:
    """Salva budgets anteriores, aplica boost. Retorna dict para restore seletivo."""

async def exit_critical_batch(self, saved_budgets: Dict[str, float]) -> None:
    """Restaura APENAS os agents em saved_budgets. Não afeta não-relacionados."""
```

#### P1.2 — Fitness Debounce

**Problema original:** `update_fitness()` → `_persist_fitness()` escrevia genome.json em disco a cada chamada (mkdir + read + json.loads + json.dumps + write_text), gerando dezenas de I/O por minuto em cenário de múltiplos agentes.

**Correção:** Bufferiza fitness em `_fitness_buffer: Dict[str, float]`. Um `_flush_loop()` de fundo persiste em lote a cada `FLUSH_INTERVAL` (5s), com flush forçado quando o buffer atinge `FLUSH_MAX_BATCH` (50 registros).

```python
async def _persist_fitness(self, agent_id: str, score: float) -> None:
    """Bufferiza em memória — I/O real acontece no _flush_loop de fundo."""
    await self._start_flush_loop()
    async with self.lock:
        self._fitness_buffer[agent_id] = score
```

### Next Expansions

1. **Estender para outros batches**:
   - `tester` + `debug_unificado` (correção de testes)
   - `evolution_committee` + `pipeline_updater` (atualização do DAG)
   
2. **Boost adaptativo**:
   - Ajustar `boost_percent` dinamicamente baseado em carga da CPU
   - Monitorar IVM em tempo real e disparar boost preventivo

3. **Métricas de eficiência**:
   - Log de "economia de ciclos" por batch
   - Comparativo de latência antes/depois do boost

---

## 12. Validation Under Load

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

## 13. Technical Debt and Detected Inconsistencies

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
10. **[RESOLVIDO] Bare `raise` fora do `except` em `AgentBase._call_llm`** — o bloco de falha fazia `raise` (re-levantar) fora do escopo do `except Exception as e:`. Em Python 3 o nome `e` é desalocado ao sair do bloco, então o `raise` solto (sem exceção ativa) disparava `RuntimeError: No active exception to reraise` em vez de re-levantar o erro original do provider — mascarando a falha real e quebrando o hook de memória imunológica (`evo_analyze_failure`). Corrigido: a lógica de enriquecimento de erro (Chappie) e o `raise` foram movidos para DENTRO do `except`, mantendo `e` em escopo e re-levantando a exceção original corretamente. Detectado pelo teste de referência consolidado `tests/test_evo_integration_recent.py`.

---

## 14. Evolutionary Vector

### 13.1 (evolutionary integration)

- **[DONE] Integração EvoAgent ↔ AgentBase (Reflexão de 4 Módulos)** — §7.1.
  Todo agente que herda de `AgentBase` consome `SelfCritique`, `ReflexionEngine`,
  `FailureAnalyzer` e `LearningLoop` via um único `EvoAgent` por linhagem
  (`_EVO_REGISTRY`). Flags epigenéticas `evo_self_critique/evo_reflexion_enabled/
  evo_learning_enabled`. 13 testes em `tests/test_evo_agent_reflection_integration.py`.
- **[DONE] Vacinas por Linhagem (failure_patterns no Obsidian × ImmuneMemoryExchange)** — §7.2.
   `VaccineLedger` persiste `_failure_patterns` em `05_Vaccines/linhagem_<marker>.md`
   e cruza com `ImmuneMemoryExchange` (gating de mesma linhagem, sem autoimunidade).
   Flag `evo_vaccine_persist=True`. 8 testes em `tests/test_vaccine_ledger.py`.
- **[DONE] Teste de Referência Consolidado (`tests/test_evo_integration_recent.py`)** — âncora de
   regressão de TODAS as mutações recentes (4 módulos de reflexão + delegação AgentBase +
   registry por linhagem + auto-hooks em `_call_llm` + VaccineLedger + ImmuneMemoryExchange).
   19 testes em 7 classes. Também serviu para detectar o bug do §12 item 10.

### 13.2 Phase E — Metabolic Corrections (P0–P2)

Correções estruturais aplicadas após diagnóstico sistêmico de 8 patologias em `cpu_affinity.py`,
`chappie/` e `agent_base.py`. 7 itens corrigidos, 0 regressão:

| ID | Patologia | Correção | Testes |
|----|-----------|----------|--------|
| P0.1 | `_evo_model_fn()` criava novo event loop por reflexão | `asyncio.run()` substitui loop manual | 235 ✅ |
| P0.2 | Pesos epigenéticos GLOBAIS contaminavam ranking | Pesos migrados para `IVMMetrics` por-agente | 235 ✅ |
| P1.1 | `exit_critical_batch()` resetava TODOS os agents | Restaura apenas boosted, salva budgets anteriores | 235 ✅ |
| P1.2 | `_persist_fitness()` I/O sem debounce | Buffer em memória + flush em lote a cada 5s | 235 ✅ |
| P1.3 | `monitorar_metabolismo()` usava `calcular_ivm()` deprecado | Leitura via `IVMAxiom.get_ivm()` canônico | 235 ✅ |
| P2.1 | `custo_creditos=1.0` fixo | `_estimar_custo_creditos()` por prefixo de provider | 235 ✅ |
| P2.2 | Thresholds IVMCompliance (0.85/0.60) divergiam do IVMAxiom (0.9/0.3) | Sincronizados para 0.9/0.3 | 235 ✅ |

### 13.3 Phases A–D — Post-Integration Corrections

Bloco de correções identificado após execução de análise técnica do ecossistema:

| Fase | Escopo | Itens | Status |
|------|--------|-------|--------|
| **A** | Falso-positivo de DNA no OmniMind | Callers passam `GENESIS_HASH_OFFICIAL` em vez de `lineage_marker`/tag; OmniMind reconstrói `phonetic_name` via Pysecurity1024; teste `test_omnimind_lineage.py` | ✅ |
| **B** | Qualidade de saída do pipeline | Schema estruturado em `no_documentation.py` (Diagnóstico/Gargalos/Plano/Conclusão); teste `test_artifact_contract.py` (12 casos) | ✅ |
| **C** | Elevação de modelo no `skill_model_router` | `REASONING_KEYWORDS` + IVM threshold 0.5; tarefas de análise baixo IVM sobem para nuvem; teste `test_model_router.py` (10 casos) | ✅ |
| **D** | Limpeza de ruído | `_schedule_close` em `async_http.py` sem warning de connector; `unittest`/`pytest` no sandbox `allowed_modules` | ✅ |

### 13.4 Next mutations of the Evolutionary Vector:

- **Genetic Algorithm** para tuning automático de pesos do IVM.
- **[DONE] Expansão do MCP Protocol** — tools externas via Model Context Protocol (ver §15).
- **[DONE] Colony Intelligence** — múltiplos organismos `iaglobal` colaborando entre si (ver §16).
- **`PhospholipidRegistry`** — load balancing dinâmico em nível de serviço.
- **Integração Obsidian mais profunda** — `LearningSystem` ainda não é usado por todos os agentes.
- **Expansão do `GlutathionePool`** — mais tipos de ameaças cobertas.
- **Threshold dinâmico no `HomocysteinePool`** baseado em carga.
- **`GracefulShutdown` mais granular** para auto-apoptose de agentes.
- **Handshake de Genesis entre nós remotos** (SHA3-512, ver §3) para rede global de agentes.
- **Detector `AsyncViolationDetector`**: migrar de regex para `ast.NodeVisitor` (precisão 100%) → classificador supervisionado para falsos positivos → distribuição de scanners entre núcleos (mitose) → compartilhamento de descobertas via `ImmuneMemoryExchange` → auto-proposta de patches via `no_code_executor`.

---

## 15. SearchMiddleware — Intelligent Context Access with Dual RAG (Web + Local)

A partir da otimização para `qwen2.5:0.5b` como modelo padrão local, o iaglobal adotou uma arquitetura de **acesso unificado via BanditPolicy** com **Membrana Seletiva** em dois gates. Todo agente passa por `bandit.generate()`, que aplica:

1. **RAG enrichment**: `SearchMiddleware.enrich()` injeta contexto web no prompt antes da chamada LLM.
2. **GATE 1 (Bandit)**: `_membrane_filter_candidates()` — sempre ativo (default `enforce`). Não-críticos só enxergam Ollama local. Críticos têm acesso a cloud.
3. **GATE 2 (Provider Router)**: `_force_local_model()` — defense-in-depth. Redireciona para Ollama se o nó não for autorizado.

### Flow Diagram **🏆 Complete Autonomous RAG**

Consolidado em 6 fases de maturidade no sistema iaglobal:

```text
========================================================================
🏆 RAG AUTÔNOMO COMPLETO — 6/6 FASES (100% DE MATURIDADE)
========================================================================

    [ FASE 1: THRESHOLD ] ─────────────> [ CONFIDENCE_TRACKER ]
    (Skip de busca se confiança > 0.8)       (20 Testes)
              │
              ▼
    [ FASE 2: QUERY EXPANSION ] ──────> [ QUERY_EXPANDER ]
    (Geração de 2-3 queries relacionadas)    (17 Testes)
              │
              ▼
    [ FASE 3: VALIDAÇÃO ] ────────────> [ SOURCE_VALIDATOR ]
    (Filtragem de fontes com score < 0.6)    (26 Testes)
              │
              ▼
    [ FASE 4: SÍNTESE ] ──────────────> [ SNIPPET_SYNTHESIZER ]
    (Resumo coerente via LLM)                (23 Testes)
              │
              ▼
    [ FASE 5: PERSISTÊNCIA ] ─────────> [ SEARCH_MEMORY ]
    (Cache persistente no Obsidian)          (24 Testes)
              │
              ▼
    [ FASE 6: FEEDBACK ] ─────────────> [ FEEDBACK_LOOP ]
    (Ajuste dinâmico de confiança)           (26 Testes)

------------------------------------------------------------------------
📊 RESUMO METABÓLICO: 136 Testes Específicos
========================================================================

```

⚡ **Diagrama de Fluxo Metabólico da RAG Autônoma Completa**:

```
┌────────────────────────────────────────────────────────────┐
│ 1. SearchMiddleware.enrich()                               │
│    └─ Check ConfidenceTracker → skip se confiança > 0.8    │
└────────────────────────────────────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────────┐
│ 2. SearchMemory.search_memory()                            │
│    └─ Hit no Obsidian? → retorna cache (econômico!)        │
└────────────────────────────────────────────────────────────┘
                           ↓ (se miss)
┌────────────────────────────────────────────────────────────┐
│ 3. QueryExpander.expand()                                  │
│    └─ Gera 2-3 queries relacionadas via LLM                │
└────────────────────────────────────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────────┐
│ 4. Busca Web + SourceValidator                             │
│    └─ Filtra fontes com score < 0.6                        │
└────────────────────────────────────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────────┐
│ 5. SnippetSynthesizer.synthesize() (opcional)              │
│    └─ Resumo coerente + detecção de contradições           │
└────────────────────────────────────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────────┐
│ 6. SearchMiddleware._inject()                              │
│    └─ Prompt enriquecido com contexto                      │
└────────────────────────────────────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────────┐
│ 7. FeedbackLoop.record_outcome() (pós-execução)            │
│    └─ Registra se ajudou, ajusta confiança                 │
└────────────────────────────────────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────────┐
│ 8. SearchMemory.save_search() (pós-execução)               │
│    └─ Persiste no Obsidian para reuso futuro               │
└────────────────────────────────────────────────────────────┘
```
### Notes on the Metabolic Flow Diagram of Autonomous RAG:

🧬 Diagnóstico Genômico + Dinâmica de Chamada
🗺️ DINÂMICA DE CHAMADA — Fluxo real no codebase
Agent não-crítico (coder, debugger, tester, planner...)
    │
    │  Não pode chamar LLM diretamente — PSC bloqueia
    ▼
_get_critic().arbitrar_geracao(node_id, prompt, ...)
    │  [iaglobal/agents/agent_base.py:238]
    │
    │  Tenta tools → tenta memória → não resolve?
    ▼
self.bandit.generate(node_id="critic", prompt=prompt, context={"delegate_for": node_id})
    │  [iaglobal/agents/critic_agent.py:464]
    │
    │  PSC verifica identity → semáforo IVM → seleciona modelo
    ▼
**LINHA 742 — AQUI ENTRA O SEARCHMIDDLEWARE**
SearchMiddleware.enrich(prompt, node_id, context=context)
    │  [iaglobal/graphs/bandit.py:742]
    │
    │  ↑ Fulton endereçada da refatoração
    ▼
async_route_generate(model, enriched_prompt, ...)
    │
    ▼
Resposta do LLM
Dois pontos de entrada:
- bandit.py:421 → async_execute_model() (debugger usa explicitamente)
- bandit.py:742 → generate() (caminho padrão via CriticAgent.arbitrar_geracao)

* **Fluxo de Dados:** O sistema segue um encadeamento linear onde cada fase atua como um filtro ou enriquecedor, culminando no armazenamento de longo prazo pelas pastas (obsidian + memory) e pela eficiencia de (sqlite3 serializado com cbor2).

* **Eficiência:** O `confidence_tracker` atua como o seu principal controlador de "custo metabólico", permitindo que o sistema interrompa o ciclo de RAG antes da fase de busca web, caso a resposta já possa ser inferida com alta confiança.

* **🎯 Eficiência Energética (ATP)**
- Cache em 3 camadas: Memória → Obsidian → Web (custo decrescente)
- Skip de busca: Economia de 100% quando confiança alta
- Reuso de buscas: Economia de ~80% com cache Obsidian
- Query expansion: +30% cobertura com +200% custo (trade-off)

* **🛡️ Sistema Imunológico**
- SourceValidator: Filtra fontes tóxicas (score < 0.6)
- FeedbackLoop: Detecta buscas prejudiciais (harmed)
- ConfidenceTracker: Ajusta threshold dinamicamente

* **Persistência:** Uma vez que uma resposta é gerada, ela não é perdida, tornando-se parte da base de conhecimento persistente do sistema iaglobal.

* **🔄 Ciclo de Auto-Evolução iaglobal**

O **Ciclo de Auto-Evolução iaglobal** é o que diferencia iaglobal de um RAG comum (que é apenas um buscador com memória curta). iaglobal implementa um sistema com **Aprendizado por Reforço (Reinforcement Learning)** aplicado ao fluxo de trabalho do agente.

Ao analisar o código e o fluxo de iaglobal, fica claro como o `BanditPolicy` e o `CreditAssignmentEngine` fecham esse ciclo de forma técnica:

### The Mechanics of Evolution no Sistema iaglobal

1. **O "Aprendizado" (`CreditAssignmentEngine`):**
* Quando o sistema executa uma busca, o `CreditAssignmentEngine` registra o resultado (sucesso/falha/latência).
* Isso não é apenas um log; é a atribuição de *crédito* para a estratégia e o modelo que tomaram a decisão.

2. **O "Ajuste de Decisão" (`BanditPolicy`):**
* O `BanditPolicy` utiliza esse histórico para atualizar seus pesos (`_sync_weights_from_credit`).
* Na próxima busca, a função `select_model` não escolhe aleatoriamente; ela consulta essa "memória de sucesso" para favorecer o modelo que teve melhor IVM (Índice de Valor Metabólico) em situações similares.

3. **A "Meta-Cognição" (`ConfidenceTracker`):**
* Ao ajustar a confiança após o `FeedbackLoop`, você está permitindo que o sistema identifique quando ele "não sabe o que não sabe".
* Isso força o sistema a ser mais agressivo na busca quando a confiança é baixa e mais econômico quando ela é alta, otimizando o gasto de ATP.

### The Diagram of **"Brain" of the iaglobal System**:

Para entender como essas peças se conectam durante o **Ciclo de Auto-Evolução**, há um fluxo recorrente que evidencia a natureza recursiva e o aprendizado constante do sistema iaglobal:

```
🔄 CICLO DE AUTO-EVOLUÇÃO (MÉTODO RECURSIVO)
============================================================

    ┌──────────────────────────────────────────────┐
    │          [ 1. PROMPT DO USUÁRIO ]            │
    └──────────────────────┬───────────────────────┘
                           │
    ┌──────────────────────▼───────────────────────┐
    │          [ 2. BUSCA AUTÔNOMA ]               │
    │ (RAG enriquecido + BanditPolicy Seleção)     │
    └──────────────────────┬───────────────────────┘
                           │
    ┌──────────────────────▼───────────────────────┐
    │         [ 3. EXECUÇÃO E FEEDBACK ]           │
    │ (Sucesso/Falha/Latência registrado via IVM)  │
    └──────────────────────┬───────────────────────┘
                           │
    ┌──────────────────────▼───────────────────────┐
    │      [ 4. AJUSTE DE CONFIANÇA ]              │
    │ (ConfidenceTracker atualiza pesos de risco)  │
    └──────────────────────┬───────────────────────┘
                           │
    ┌──────────────────────▼───────────────────────┐
    │      [ 5. OTIMIZAÇÃO (META-COGNIÇÃO) ]       │
    │ (BanditPolicy recalibra modelos via Credit)  │
    └──────────────────────┬───────────────────────┘
                           │
    ┌──────────────────────▼───────────────────────┐
    │        [ 6. PRÓXIMA BUSCA (MELHORADA) ]      │
    │ (Decisão otimizada pelo histórico anterior)  │
    └──────────────────────┬───────────────────────┘
                           │
                           └──────────────► (REINICIA O CICLO)

```

### Why is this cycle evolutionary?

1. **Atribuição de Crédito:** O `CreditAssignmentEngine` analisa o resultado do ciclo anterior e atribui crédito aos modelos/estratégias que performaram melhor.
2. **Aprendizado Adaptativo:** O `BanditPolicy` usa esse crédito para atualizar seus "pesos" (`_sync_weights_from_credit`), garantindo que o sistema "esqueça" caminhos ineficientes e priorize caminhos de alta performance metabólica.
3. **Memória de Longo Prazo:** O feedback não é apenas descartado; ele é persistido, permitindo que a "inteligência" do sistema se acumule, tornando as buscas futuras cada vez mais precisas e econômicas.

### What does this mean in practice?

iaglobal construiu um **agente que refina sua própria estratégia de exploração**.

* **Antes:** Você tinha um sistema que respondia perguntas com base no que encontrava.
* **Agora:** Você tem um sistema que **avalia a qualidade de suas fontes e a eficácia de seus modelos** para decidir como será a *próxima* pesquisa.

Se o sistema perceber, por exemplo, que para tarefas de "análise de código" o `qwen2.5:0.5b` local usado na CPU de 4 núcleos tem uma taxa de falha alta, o `BanditPolicy` começará a penalizar esse modelo para essa tarefa específica, movendo o peso para um modelo de nuvem (se o nó for crítico) ou para uma estratégia de busca web diferente.

O sistema aprende com cada busca e otimiza decisões futuras.

### Critic Agent — Local → Cloud Escalation

O critic é o **único nó autorizado** a acessar modelos cloud. O fluxo prioriza eficiência energética (ATP):

```
CRITIC
     ↓
bandit.generate(node_id="critic")
     ├── GATE 1 (Membrana): "critic" → autorizado → libera cloud
     │
     ├── 1. Tenta local (Ollama) — ATP-efficient
     │      └── _avaliar_multidimensional()
     │           ├── Parseia scores JSON {correctness, completeness, security, spec_match}
     │           ├── score médio ≥ 60 → retorna (sem cloud)
     │           └── score < 60 ou falha → escala para cloud
     │
     └── 2. Escala para cloud (se score local insuficiente)
            ├── Groq / NVIDIA / OpenRouter / Gemini
            └── Fallback → Ollama local (último recurso)
                  ↓
            async_route_generate(model, node_id)
                  ↓
            GATE 2 (Provider Router): _force_local_model("critic") → False → libera
```

### 14.1 SearchMiddleware

**Arquivo:** `iaglobal/search/search_middleware.py`

| Método | Fonte | Limite | Formato |
|--------|-------|--------|---------|
| `buscar_web()` | DuckDuckGo (aiohttp) | 2 snippets, 300 chars cada | texto puro |
| `buscar_local()` | MemoryVector.search() | Top 2 chunks, 300 chars cada | embedding similarity |

Ambas as buscas rodam **em paralelo** via `asyncio.gather()`. O middleware é chamado dentro de `bandit.generate()` **antes** de toda chamada LLM, garantindo que 100% dos agentes recebam contexto web. O `ConfidenceTracker` decide se a busca é necessária (skip se confiança > 0.8), preservando ATP.

### 14.2 Formato Ultra-Compacto de Prompt

Para máxima eficiência com `qwen2.5:0.5b` (modelo de 500M parâmetros), o prompt segue uma estrutura de três blocos rígidos:

```
[CONTEXTO]
<web_results>...+</web_results>
<rag_results>...+</rag_results>
<historico>...</historico>

[INSTRUÇÃO]
<diretrizes>...</diretrizes>
<restricoes>...</restricoes>

[PROMPT]
<tarefa>...</tarefa>
```

**Regras de compressão:**
- Total de contexto combinado (web + RAG + histórico): ~1200 caracteres
- Nenhum bloco excede 300 caracteres individualmente (web snippet) ou 600 (instrução)
- Formato sem markdown, sem explicações, sem exemplos — apenas o necessário para o modelo responder

### 14.3 Optimized Ollama Parameters

Os parâmetros foram ajustados experimentalmente para `qwen2.5:0.5b` nos três endpoints da API (`generate`, `chat`, `embeddings`):

| Parâmetro | Valor | Justificativa |
|-----------|-------|---------------|
| `temperature` | 0.1 | Máximo determinismo; modelo pequeno precisa de repetibilidade para gerar código válido |
| `num_ctx` | 4096 | Contexto suficiente para `[CONTEXTO][INSTRUÇÃO][PROMPT]` (~2.5k tokens típicos) |
| `num_predict` | 2048 | Limite de geração para resposta completa sem runaway |
| `stop` | `["<|im_end|>"]` | Token de parada do Qwen |

### 14.4 Impacto na Arquitetura Anterior

| Antes (portão único sem membrana) | Depois (dois gates + escalonamento) |
|-----------------------------------|-------------------------------------|
| Todo agente passava pelo BanditPolicy → fallback chain cloud | Membrana no Bandit (GATE 1) + Provider Router (GATE 2) |
| Critic tentava cloud primeiro | Critic tenta local primeiro, escala para cloud só se score < 60 |
| RAG enrichment só em `async_execute_model` (bypass do generate) | RAG enrichment dentro de `bandit.generate()` — cobre 100% dos acessos |
| Latência média por agente: ~8-15s (timeout cloud) | Latência local: ~1-3s (Ollama) — cloud só quando necessário |
| Consumo de ATP: alto (múltiplas tentativas) | Consumo de ATP: ~10:1 (eficiência metabólica máxima) |
| Dependência de API keys para todos os agentes | Apenas o crítico precisa de API keys |
| Contexto cru enviado ao LLM | Contexto enriquecido via web + RAG local |

### 14.5 Performance Metrics

| Métrica | Antes | Depois |
|---------|-------|--------|
| Tempo médio por execução completa | ~45s | ~18s |
| Taxa de sucesso do pipeline | ~92% | ~98% |
| Erros de timeout/fallback | ~8% | ~1% |
| Chamadas a cloud | 100% dos agentes | Apenas o crítico |

---

## 16. SERVERS and MCP Protocol Expansion

🧬 **DIAGNÓSTICO GENÔMICO - MAPEAMENTO DE SERVIDORES**

### 🔬 SERVIDORES IDENTIFICADOS EM `/iaglobal/`

| Servidor              | Path                                   | LOC  |  Função                  |
|-----------------------|----------------------------------------|------|--------------------------|
| **ASGI Server**       | `iaglobal/server/asgi.py`              | 292  | Gateway assíncrono principal        |
| **Health Aggregator** | `iaglobal/server/health_aggregator.py` | 255  | Monitoramento de saúde distribuída      |
| **MCP Server (core)** | `iaglobal/server/mcp_server.py`        | 352  | Protocolo MCP (Model Context Protocol) |
| **HTTP Server**       | `iaglobal/server/server.py`            | 209  | Servidor HTTP principal  |
| **MCP Server (api)**  | `iaglobal/api/mcp_server.py`           | ~350 | API MCP secundaria       |
| **MCP Server (mcp)**  | `iaglobal/mcp/mcp_server.py`           | ~100 | Descoberta MCP           |
| **FastAPI App**       | `iaglobal/ui/fastapi_app.py`           | ?    | Interface UI             |

### 📊 ARQUITETURA DE SERVIDORES

```
iaglobal/
├── server/              # Núcleo de servidores
│   ├── asgi.py         # Gateway assíncrono (292 LOC)
│   ├── server.py       # HTTP Server (209 LOC)
│   ├── mcp_server.py   # MCP Core (352 LOC)
│   └── health_aggregator.py  # Health monitoring (255 LOC)
│
├── api/
│   └── mcp_server.py   # API MCP secundária
│
├── mcp/
│   ├── mcp_server.py   # Descoberta MCP
│   └── discovery.py    # Service discovery
│
└── ui/
    └── fastapi_app.py  # Interface UI
```

### 🧫 ANALISE METABÓLICA

**Total de servidores**: **7 instâncias** em 3 camadas:

1. **Camada Core** (`server/`): 4 servidores
2. **Camada API** (`api/`): 1 servidor
3. **Camada MCP** (`mcp/`): 2 servidores

> **Objetivo:** Conectar iaglobal a ferramentas externas via Model Context Protocol (MCP).

O iaglobal agora expõe um ecossistema completo de tools MCP, organizado em 3 fases. Todo o código está em `iaglobal/mcp/`, com camadas de segurança em `iaglobal/security/` e `iaglobal/immunity/`.

### 15.1 Arquitetura do Fluxo MCP

```
ToolCallerAgent.run() → recebe {tool, arguments, agent_id}
    ↓
MCPSandbox.validate_call() → whitelist de tools permitidas
    ↓
FeedbackEngine.validate_mcp_call() → schema dos argumentos
    ↓
GlutathioneGuardrails.check_mcp_rate_limit() → rate por tool
    ↓
Handler específico (WebSearchTool / FileSystemTool / CodeExecutorTool)
    ↓
MCPSandbox.audit_call() → registra em audit.json
    ↓
Retorna {result, execution_metrics} para o BanditPolicy
```

### 15.2 FastMCP Server

**Arquivo:** `iaglobal/mcp/mcp_server.py`

Servidor FastMCP com 8 tools expostas:

| Tool | Parâmetros | Descrição |
|------|-----------|-----------|
| `metabolic_audit` | — | Auditoria metabólica completa (score, findings, corrections) |
| `get_ivm` | — | Índice de Viabilidade Metabólica atual |
| `web_search` | `query: str`, `max_results: int (5)` | Busca web com cache |
| `web_fetch` | `url: str`, `timeout: int (15)` | Fetch de conteúdo de URL |
| `read_file` | `path: str` | Leitura segura de arquivo (whitelist) |
| `write_file` | `path: str`, `content: str` | Escrita segura de arquivo (whitelist) |
| `list_dir` | `path: str` | Listagem de diretório (whitelist) |
| `execute_code` | `code: str`, `language: str (python)` | Execução em sandbox isolado |

### 15.3 Clientes MCP

- **`MCPClient`** (`iaglobal/mcp/client.py`) — conecta a servidores MCP externos via stdio ou SSE, usando JSON-RPC 2.0.
- **`MCPDiscovery`** (`iaglobal/mcp/discovery.py`) — descobre tools de servidores internos e externos, persiste cache em `iaglobal/memory/data/json/mcp_tools.json` (8 tools internas registradas).
- **`WebSearchTool`** (`iaglobal/mcp/search_web.py`) — busca web com fallback duckduckgo → aiohttp, cache LRU (TTL 5min, max 100 entries).
- **`FileSystemTool`** (`iaglobal/mcp/file_system.py`) — leitura/escrita com whitelist de paths: leitura em `iaglobal/`, `tests/`, `docs/`, `memory/data/json/`; escrita apenas em `memory/data/json/` e `memory/data/script/`.
- **`CodeExecutorTool`** (`iaglobal/mcp/code_executor.py`) — wrapper async do `SandboxExecutor` com 4 camadas de segurança: ASTGateway, SandboxRules, subprocesso isolado, GlutathioneGuardrails.

### 15.4 Agente ToolCaller

**Arquivo:** `iaglobal/agents/tool_caller_agent.py`

`ToolCallerAgent` — seleciona a tool MCP adequada baseado no plano do orchestrator. Mapa de dispatch direto para tools internas (`web_search`, `read_file`, `execute_code`, etc.) e resolução via `MCPDiscovery` + `MCPClient` para tools externas. Cada chamada retorna `execution_metrics` com `success`, `latency`, `tool_name`, `result_summary` para o `JointOptimizationLoop` do BanditPolicy.

### 15.5 MCP Security

- **`MCPSandbox`** (`iaglobal/security/mcp_sandbox.py`) — whitelist de 8 tools permitidas, rate limits por tool (ex: `web_search` 10 chamadas/min, `execute_code` 5 chamadas/min), audit trail em `iaglobal/memory/data/json/audit.json` (máx 1000 entradas).
- **`GlutathioneGuardrails.check_mcp_rate_limit()`** — verificação de rate limit integrada ao sistema SAMe, reutilizando o sistema imunológico existente.
- **`FeedbackEngine.validate_mcp_call()`** (`iaglobal/validation/engine.py`) — valida schema de argumentos contra os tipos esperados (string, integer, boolean).

### 15.6 Cache e Audit Trail

- `iaglobal/memory/data/json/mcp_tools.json` — catálogo de tools descobertas (8 tools internas)
- `iaglobal/memory/data/json/audit.json` — registro de todas as chamadas MCP (permitidas ou bloqueadas) com timestamp, agent_id, tool, arguments, sandbox_decision

---

## 17. Colony Intelligence Communication

> **Objetivo:** Múltiplos organismos iaglobal colaborando como colônia — divisão de tarefas, comunicação entre organismos, seleção de fitness coletivo.

### 16.1 Colony Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   ColonyQueen (rainha)                   │
│  Decompõe tarefa grande → subtarefas atômicas            │
│  Distribui via task_offer → coleta via result_share      │
└────────────┬──────────────────────────────┬──────────────┘
             │ task_offer                    │ result_share
    ┌────────┴────────┐       ┌──────────────┴──────────────┐
    ▼                 ▼       ▼                             ▼
┌──────────┐  ┌─────────┐  ┌─────────┐          ┌──────────────┐
│ Worker A │  │ Worker B│  │ Worker C│  ...     │ ColonyFitness│
│(search)  │  │ (coder) │  │(report) │          │ (seleção)    │
└────┬─────┘  └────┬────┘  └────┬────┘          └──────────────┘
     │             │            │                      │
     └─────────────┴────────────┘                      │
                    │                                  │
                    ▼                                  ▼
          ┌──────────────────┐              ┌──────────────────┐
          │ ColonyIntegrator │              │ Apoptose (< 0.3) │
          │ (merge + evolve) │              │ Mitose (≥ 0.7)   │
          └──────────────────┘              └──────────────────┘
                    │
                    ▼
          ┌──────────────────┐
          │ Obsidian 03_Long │
          │ MetaEvolver      │
          └──────────────────┘
```

### 16.2 AcetylcholineBus Estendido

`AgentMessage` ganhou o campo `organism_id: str = "iaglobal"` e três novos tipos de mensagem (`task_offer`, `result_share`, `skill_handshake`). O barramento agora roteia também pelo canal `"org:<organism_id>"`, permitindo que múltiplos organismos coexistam no mesmo bus sem cruzamento de mensagens entre colônias.

### 16.3 Rainha — ColonyQueen

**Arquivo:** `iaglobal/communication/queen.py`

| Método | Função |
|--------|--------|
| `decompose(super_task)` | Divide tarefa em subtarefas atômicas baseado no tipo (`analysis` → search + code_review + report; `development` → planner + coder + tester + documenter) |
| `assign(subtasks, workers)` | Distribui via `task_offer` round-robin nos workers |
| `collect(task_id, timeout)` | Aguarda todos os resultados via `asyncio.Event` |

### 16.4 Trabalhador — ColonyWorker

**Arquivo:** `iaglobal/communication/worker.py`

Worker com filtro de skills: `can_handle(task_type)` verifica se o worker tem a skill necessária. Workers com `skills=["generic"]` aceitam qualquer tarefa. O worker mantém uma fila assíncrona de `task_offer` e executa handlers especializados (`_handle_search`, `_handle_code_review`, `_handle_report`, `planner`, `coder`, `tester`, `documenter`). Cada execução retorna `result_share` com `task_id`, `success`, `latency_ms` e `result`.

### 16.5 Integrador — ColonyIntegrator

**Arquivo:** `iaglobal/communication/integrator.py`

| Método | Função |
|--------|--------|
| `integrate(task_id, results)` | Combina N resultados parciais em artefato consolidado com métricas totais |
| `feed_evolution(task_id, result)` | Registra aprendizado no `MetaEvolver` para evolução contínua |
| `feed_obsidian(organism_id, result)` | Escreve nota markdown estruturada em `obsidian/03_Long_Term/` |

### 16.6 Fitness Selection — ColonyFitness

**Arquivo:** `iaglobal/communication/fitness.py`

Cada organismo da colônia mantém métricas independentes:

- **Produtividade (P)** = `tasks_completed / (completed + failed)` — peso 0.4
- **Eficiência Energética (E)** = `1 - min(latency_total / 5000, 1.0)` — peso 0.4
- **Cooperação (C)** = `min(skills_exchanged / 10, 1.0)` — peso 0.2
- **IVM** = `P × 0.4 + E × 0.4 + C × 0.2`

| Threshold | Ação |
|-----------|------|
| IVM ≥ 0.7 | Mitose — organismo gera filho especializado via `check_mitosis()` |
| 0.3 ≤ IVM < 0.7 | Monitoramento — recebe tarefas mais simples |
| IVM < 0.3 | Apoptose — organismo eliminado, lições extraídas via `_extract_lessons()` |

`rank_organisms()` retorna ranking decrescente por IVM. `average_ivm()` calcula a média da colônia.

### 16.7 Testes

34 testes em `tests/test_colony_intelligence.py` cobrindo:

| Classe de Teste | Testes | Escopo |
|-----------------|--------|--------|
| `TestAgentMessageOrganismID` | 6 | organism_id, message_types, COLONY_MESSAGE_TYPES |
| `TestBusRoutingByOrganismID` | 4 | roteamento por org:, wildcard, message_type |
| `TestColonyQueen` | 4 | decompose (analysis/development/generic), assign round-robin |
| `TestColonyWorker` | 4 | skills filter, generic skill, execução, latência |
| `TestColonyIntegrator` | 6 | merge, empty, partial failures, evolution, obsidian, format |
| `TestColonyFitness` | 10 | IVM, ranking, mitosis, apoptosis, avg, cooperação |
| `TestColonyE2E` | 1 | 3 workers colaborando em tarefa completa |

---
- Arvore de pastas iaglobal

---

## 18. Genetic Algorithm Tuning — Evolutionary Optimization of IVM Weights

> **Objetivo:** Automatizar o ajuste dos pesos do Índice de Viabilidade Metabólica (IVM) via Algoritmo Genético, eliminando a necessidade de calibração manual e permitindo adaptação contínua às pressões do ambiente.

### 17.1 Arquitetura do GA

DeepSeek V4 Flash e outros modelos são um modelo de linguagem MoE (Mixture-of-Experts) — não tem um GA embutido. O Genetic Algorithm que implementamos é 100% custom do iaglobal em iaglobal/evolution/ga/:
- population.py — indivíduos com pesos IVM P, E, C, I, população 50
- selector.py — torneio k=3, crossover BLX-α, mutação gaussiana
- ga_runner.py — ciclo completo, fitness via CreditAssignmentEngine, hook no pipeline a cada 10 tasks
O modelo DeepSeek V4 Flash é apenas o LLM que o sistema usa como "cérebro" — o GA roda em Python puro, sem envolver o modelo.

```
GARunner.step()
    ↓
1. Computa fitness de cada indivíduo → _compute_fitness_from_metrics()
    ├── Produtividade (P) = Top tasks / total tasks
    ├── Eficiência (E)   = 1 / max(latency, 1)
    ├── Cooperação (C)   = skills trocadas
    └── Imunidade (I)    = MHC validation score
    ↓
2. Seleciona melhor (elite)
3. Evolui população → evolve_population()
    ├── Tournament selection (k=3)
    ├── BLX-α crossover (α=0.5)
    └── Gaussian mutation (σ=0.05, rate=0.2)
    ↓
4. Persiste genoma → best_genome.json + ga_telemetry.json
5. Aplica pesos epigenéticos → set_flag("ga_weight_p", ...)
6. Persiste em memória biológica
    ↓
┌─ Sistemas de Memória Biológica ────────────────────┐
│  ● SubconsciousAPI (STM + LTM)                     │
│  ● DBManager (insight imunológico)                 │
│  ● memory_vector (busca semântica)                 │
│  ● AncestryTree (linhagem evolutiva)               │
│  ● EpigeneticRegistry (marcas de sucesso)          │
│  ● Vacinas (genomas com queda de fitness)          │
└────────────────────────────────────────────────────┘
```

### 17.2 Metabolic Cycle

**Frequência:** A cada 10 execuções de pipeline (`GENERATION_INTERVAL=10`), o `GARunner.task_hook()` dispara 1 geração do GA.

```
task_hook() chamado a cada pipeline
    ↓
_counter % 10 == 0?
    ├── SIM → GARunner.step()
    │         ├── fitness atual
    │         ├── evolução da população
    │         ├── persistência JSON
    │         └── memória biológica
    └── NÃO → apenas incrementa _counter
```

### 17.3 Fitness Function

```
fitness = (P × 0.5) + (E × 0.3) + (C × 0.2)

Onde:
  P = BanditPolicy.success / total calls
  E = 1 / latency_média
  C = skills trocadas × IVM_C × 0.01
```

**O ResearchConsolidator é o córtex de memória de longo prazo do organismo. Ele colabora para a evolução dos agentes através de múltiplos ciclos metabólicos:**

🔄 Papel Evolutivo...

1. Memória Imunológica Epigenética:
Cada nota no Obsidian (03_Long_Term/) é um anticorpo arquitetural — um padrão de sucesso/falha que sobrevive a restarts. Quando um agente futuro enfrentar problema similar, sussurrar_intuicao() recupera essas memórias via RAG, evitando repetir erros.

2. Seleção Natural via Fitness Score...
O fitness_score (validated/hypotheses) alimenta diretamente:
- BanditPolicy: recompensa provedores e estratégias que geraram papers com alta validação
- AdaptiveRouter: prioriza agentes que historicamente produziu resultados com fitness > 0.8
- Genetic Algorithm: na fusão de DNAs, genomas com fitness_score alto têm maior probabilidade de sobreviver

3. Gradiente de Informação (Hebb's Rule)
Papers com fitness_score alto são recuperados mais frequentemente → conexões neurais (AgentsPool → BestProviders) se fortalecem. O sistema evolui para buscar mais cedo padrões que funcionam.

4. Autopoiese Fechada
Input (Paper) → ExperimentRunner → Validadores 
                                          ↓
                        ResearchConsolidator → Obsidian Vault
                                          ↓
                        Novos agentes herdam via sussurrar_intuicao()

O organismo se reconstrói a cada ciclo usando seu próprio conhecimento acumulado.

5. Sinalização Celular para Mutação
- fitness_score < 0.5 → sinal para apoptose de provedores/estratégias ruins
- fitness_score > 0.8 → mitose de agentes especializados naquele domínio
- Meta-evolução ajusta thresholds de confiança baseado na distribução de fitness histórica

🧬 Impacto Concreto...

Ciclo Biológico
   ↓
Glutationa
   ↓
Memória Imunológica
   ↓
Gradiente
   ↓
Epigenética

Sem este estágio, o sistema é estéril: cada execução é um organismo novo sem herança. Com ele, o iaglobal acumula aptidão cumulativa — exatamente como evolução biológica.

### 17.4 Genoma (4 Pesos)

| Gene | Limites | Padrão | Descrição |
|------|---------|--------|-----------|
| P (Produtividade) | [0.0, 1.0] | ~0.35 | Peso da taxa de conclusão |
| E (Eficiência) | [0.0, 1.0] | ~0.30 | Peso da latência |
| C (Cooperação) | [0.0, 1.0] | ~0.20 | Peso da troca de skills |
| I (Imunidade) | [0.0, 1.0] | ~0.15 | Peso da validação MHC |

A população tem 50 indivíduos, elite de 2, crossover BLX-α (α=0.5), mutação gaussiana (σ=0.05, 20%).

### 17.5 Integration with Biological Memory

Cada geração persiste o melhor genoma nos **6 sistemas de memória** do iaglobal:

| Sistema | Função | Gatilho |
|---------|--------|---------|
| **SubconsciousAPI (STM)** | Nota em `02_Short_Term/ga_gen_{N}.md` | Toda geração |
| **SubconsciousAPI (LTM)** | Nota em `03_Long_Term/ga_gen_{N}.md` | Fitness ≥ 0.7 |
| **DBManager (insight)** | Registro no banco `insights` | Toda geração |
| **memory_vector** | Embedding para busca semântica | Toda geração |
| **AncestryTree** | Linhagem + mutações no Obsidian | Toda geração |
| **EpigeneticRegistry** | Marca de sucesso (`record_success`) | Toda geração |
| **Vacinas** | `05_Vaccines/linhagem_{gen}.md` | Queda de fitness > 15% |

### 17.6 Persistence Files

| Arquivo | Conteúdo |
|---------|----------|
| `iaglobal/memory/data/json/best_genome.json` | Melhor genoma (weights, fitness, generation) |
| `iaglobal/memory/data/json/ga_telemetry.json` | Histórico de fitness por geração |
| `iaglobal/obsidian/epigenetic/*.cbor` | Marcas epigenéticas (EpigeneticRegistry) |

### 17.7 Componentes

| Módulo | Arquivo | Função |
|--------|---------|--------|
| Population | `evolution/ga/population.py` | Indivíduo, população, inicialização, best, avg |
| Selector | `evolution/ga/selector.py` | Torneio, crossover BLX-α, mutação gaussiana |
| GARunner | `evolution/ga/ga_runner.py` | Ciclo completo + persistência + memória biológica |
| Epigenetic flags | `evolution/epigenetic.py` | `ga_weight_p`, `ga_weight_e`, `ga_weight_c`, `ga_weight_i` |
| Pipeline hook | `pipeline/engine.py` | `_async_metabolism_stage()` → `runner.task_hook()` |

### 17.8 Testes

| Suite | Testes | Escopo |
|-------|--------|--------|
| `tests/test_ga_tuning.py` | 40 | Population, Individual, Selector, GARunner, memória biológica |
| `tests/test_integration_pipeline_genetic_algorithm_tuning.py` | 26 | Pipeline completo, persistência, epigenética |

### 17.9 Evolutionary Vector (Next Mutations)

- **Crossover adaptativo**: α da BLX-α ajustado dinamicamente com base na diversidade da população
- **Migração entre geracoes**: troca de indivíduos entre populações paralelas (modelo de ilhas)
- **Fitness multi-objetivo**: Pareto front para P, E, C, I em vez de soma ponderada
- **Observabilidade**: GA Dashboard integrado ao `iaglobal status`
- **Bootstrapping**: seed inicial baseado em histórico de execuções anteriores, não aleatório puro

---

## 19. Local Prompt Engineering — Self-Correction, Few-Shot and Chain of Thought

### 18.1 DependencyEnforcer — Prohibition of Non-Installed Libraries

**Arquivo:** `iaglobal/core/dependency_enforcer.py`

Mecanismo que impede a invenção de bibliotecas inexistentes pelo LLM. Opera em 2 pontos:

1. **Prompt-level (`INSTRUCAO_DEPENDENCIAS`)**: constante de 243 chars injetada no `PEC_SYSTEM_PROMPT` (item 9) em `agent_base.py` — instrui o modelo a usar apenas stdlib.

2. **Pós-geração (`DependencyEnforcer.enforce()`)**: extrai imports via AST, verifica cada um contra `sys.stdlib_module_names` (Python 3.10+, 290 módulos) + `pip list --format=json` (cache 120s). Imports não-stdlib não-instalados são wrapped em `try/except ImportError` com `logging.warning` + `module = None` (máx 10 wraps por chamada).

**Integração:**
- `CoderAgent.generate()` — Layer 6, após AutoCorrectionLoop
- `TesterAgent.gerar_testes()` — após auto-correção
- `PromptImprover` — no PEC_SYSTEM_PROMPT item 9

### 18.2 FewShotProvider — Real Examples with Semantic Ranking

**Arquivo:** `iaglobal/core/few_shot_provider.py`

Fornece exemplos reais de execuções anteriores para guiar o LLM.

**Fontes:**
| Fonte | Quantidade | Uso |
|-------|-----------|-----|
| ToolLibrary | 2 tools | Exemplos positivos de código executável |
| SkillRegistry | 77 skills | Exemplos positivos de lógica completa |
| MTAPool | N variável | Exemplos negativos (padrões a evitar) |

**Ranking:** embeddings via `sentence-transformers/all-MiniLM-L6-v2` → fallback TF-IDF → keyword overlap. Diversidade: máximo 2 exemplos por fonte.

**Formato:** Seção `[EXEMPLOS DE REFERÊNCIA]` com tags `✅ padrão de sucesso` / `❌ a evitar`.

**Integração:**
- `CriticAgent._montar_prompt_avaliacao()` — injeta até 2 exemplos para `domain="code_evaluation critic"`
- `PromptImprover.improve_with_report()` — exemplos positivos incluem código fonte real via `inspect.getsource(skill.run_fn)` (truncado para 400 chars)

**Custo:** Primeira chamada ~15s (embedding model load + 79 embeddings); subsequentes ~740ms.

### 18.3 Chain of Thought — Breakdown into 4 Steps

**Constante:** `INSTRUCAO_COT` em `agent_base.py:19-25`

```
INSTRUCAO_COT = """ATENÇÃO — Siga ESTRITAMENTE o Chain of Thought:

1. ANÁLISE: Entenda o problema, identifique entradas, saídas e edge cases.
2. PLANO DE ESTRUTURA: Projete a estrutura da solução antes de escrever código.
3. IMPLEMENTAÇÃO: Execute o plano, etapa por etapa.
4. REVISÃO: Verifique a solução contra o plano e corrija discrepâncias."""
```

Injetado como item 10 no `PEC_SYSTEM_PROMPT`.

**Integração:**
| Agente | Local |
|--------|-------|
| `PEC_SYSTEM_PROMPT` | `agent_base.py`, item 10 |
| `CriticAgent` | `_montar_prompt_avaliacao()` |
| `DebuggerAgent` | `build_fix_prompt()` — instrução "Siga as 4 etapas" antes do código |
| `PromptImprover` | Seção `[CHAIN OF THOUGHT — ...]` antes de instruções PSC/EETL |

### 18.4 Integration Profile per Agent

| Agente | DependencyEnforcer | FewShotProvider | Chain of Thought |
|--------|-------------------|-----------------|------------------|
| **CoderAgent** | Layer 6 (pós-auto-correção) | ❌ | ✅ (via PEC_SYSTEM_PROMPT) |
| **CriticAgent** | ❌ | ✅ 2 exemplos | ✅ direto no prompt |
| **DebuggerAgent** | ❌ | ❌ | ✅ direto no prompt |
| **TesterAgent** | Pós-auto-correção | ❌ | ✅ (via PEC_SYSTEM_PROMPT) |
| **PromptImprover** | ✅ (via PEC) | ✅ skill source code | ✅ seção dedicada |

### 18.5 Impacto em Testes

```
773 passed, 2 skipped — zero regressão após inserção das camadas de entropia + prompt engineering.
```

### 18.6 EntropySentinel — Law of Order with Observable Action

**Arquivo:** `iaglobal/immunity/entropy_sentinel.py`

Detecta e penaliza entropia (caos) em execuções de agentes: redundância, loops de tokens, dependências circulares, caos estrutural.

**Mutações Recentes:**

| Mudança | Antes | Depois |
|---------|-------|--------|
| Persistência | Volátil (sessão) | CBOR em `memory/data/json/entropy_profiles.cbor` |
| Mínimo para apoptose | Imediato | ≥30 execuções (evita falso-positivo) |
| Histórico | 20 execuções | 100 execuções |
| Ação | `logger.error()` silencioso | Evento no `AcetylcholineBus` via `EntropyInterceptor` |

**Fluxo de Apoptose:**

```
ImmuneOrchestrator.scan_execution()
     ↓
EntropySentinel.record_execution()
     ↓ (se apoptosis_recommended=True)
EntropyInterceptor.intercept_execution()
     ↓
AcetylcholineBus.emit(apoptosis_candidate)
     ↓
no_apoptosis_kill (nó consumidor) → avalia e executa apoptose
```

**Interceptor (`iaglobal/observability/entropy_interceptor.py`):**

| Função | Propósito |
|--------|-----------|
| `intercept_execution()` | Traduz detecção em ação, retorna `action_taken` |
| `_publish_apoptosis_event()` | Publica evento para `no_apoptosis_kill` |
| `_publish_degradation_alert()` | Alerta para `epigenetic_registry` se trend='degrading' |
| `get_immune_state()` | Estado consolidado para `HealthAggregator` (/health) |

**Estado Imune Exposto:**

```python
{
    "total_profiles": 5,
    "agents_at_apoptosis_risk": 1,
    "agents_degrading": 2,
    "apoptosis_threshold": 0.8,
    "min_executions": 30,
}
```

**Integração:** `no_immune_check.py` chama `intercept_execution()` e retorna `entropy_report` enriquecido com `action_taken`.

### 18.6.1 Exposure in Health Gateway (`/health`)

O endpoint `GET /health` do ASGI Gateway (porta 8000) agora inclui o estado imunológico consolidado:

```json
{
  "organism": "iaglobal",
  "overall_status": "healthy",
  "vital_signs": {...},
  "metabolic_state": {...},
  "cpu_state": {...},
  "immune_state": {
    "entropia": {
      "total_profiles": 2,
      "agents_at_apoptosis_risk": 1,
      "agents_degrading": 0,
      "apoptosis_threshold": 0.8,
      "min_executions": 30
    },
    "barreira": {
      "degraded": false,
      "events": {"cache_poison": 0, "stale_cache": 0, ...}
    },
    "quarantine": {
      "skills": 0,
      "active_detectors": 8
    },
    "glutathione": {
      "guardrails_ativos": 0
    }
  }
}
```

**Fontes de dados:**
| Dado | Fonte |
|------|-------|
| Entropia | `EntropySentinel` via `get_immune_state()` |
| Barreira | `MetabolicImmuneBarrier.counts()` + `is_degraded()` |
| Quarentena | `ImmuneOrchestrator.health_check()` |
| Glutationa | `GlutathionePool.count()` |

**Consumidores:**
- Dashboard CLI (`iaglobal status`) — pode injetar via `health_aggregator`
- UI ReactPy (`/@/`) — pode consumir via fetch `/health`
- MCP tool `get_status` — pode enriquecer com `immune_state`
- Prometheus metrics — pode exportar gauges `iaglobal_immune_*`

### 18.6.2 Apoptosis Node (`no_apoptosis_kill.py`)

**Arquivo:** `iaglobal/graphs/nodes/no_apoptosis_kill.py`

Consumidor de eventos do `AcetylcholineBus` que executa apoptose real de agentes/skills com entropia crítica.

**Fluxo:**
```
AcetylcholineBus (evento: apoptosis_candidate)
     ↓
no_apoptosis_kill.on_apoptosis_event()
     ↓
run_apoptosis_kill(agent_name)
     ├── 1. Avalia critérios (apoptosis_risk, min_executions)
     ├── 2. Drain de execuções em andamento
     ├── 3. Serializa estado para sucessor
     ├── 4. Desregistra agente de pools/registries
     ├── 5. Registra no ancestry tree via OmniMind
     └── 6. Reseta perfil entrópico
```

**Critérios de Apoptose:**
| Critério | Threshold | Justificativa |
|------|--------|-----------|
| `apoptosis_risk` | `chaos_rate > 0.8` | >80% das execuções são caóticas |
| `min_executions_met` | `total >= 30` | Evita falso-positivo em agente novo |

**Integrações:**
- `EntropySentinel` — fornece relatório entrópico
- `OmniMind` — registra apoptose no ancestry tree
- `AcetylcholineBus` — consome eventos `apoptosis_candidate`, publica `apoptosis_completed`
- **Topologia do DAG** — registrado em `graphs/builder.py` e `graphs/topology.py`
  - Arestas: `immune_monitor → apoptosis_kill → adaptive_router`
  - Operação: **event-driven** (não sequencial) — ativado por eventos do bus, não por fluxo do pipeline

**Modo de Operação:**
| Modo | Gatilho | Uso |
|------|---------|-----|
| **Reativo (padrão)** | Evento `apoptosis_candidate` no bus | Detecção automática de entropia crítica |
| **Manual** | Chamada direta a `run_apoptosis_kill()` | CLI, MCP tool, decisão humana |

**Testes:** `tests/test_apoptosis_kill.py` (9 testes)

---

### 18.6.3 Vector Store Minimalista (FewShot Embedding Cache)

**Arquivo:** `iaglobal/core/few_shot_provider.py`

O cache de embeddings do `FewShotProvider` funciona como um **Vector Store minimalista** — armazena embeddings pré-computados para busca semântica rápida de exemplos.

**Arquitetura:**
```
Boot do Sistema
     ↓
FewShotProvider.__init__(preload=False)
     ├── _embedding_cache: OrderedDict (LRU, 100 items)
     └── _load_embedding_cache() ← EAGER LOAD (~50ms)
          └─ memory/data/json/fewshot_embeddings.cbor (CBOR)
               ↓
Primeira Chamada de get_few_shot()
     ↓
_get_or_compute_embedding(query)
     ├── Hash SHA3-256 (16 chars)
     ├── Cache hit? → retorna embedding (~0ms)
     └── Cache miss? → computa + cacheia (~15s na 1ª vez sem persistência)
```

**Trade-off de Design (Princípio da Não-Resistência):**

| Estratégia | Boot | 1ª Chamada | Memória |
|------------|------|------------|---------|
| **Eager load (atual)** | ~50ms | ~0ms (cache hit) | ~100 embeddings |
| Lazy load (sob demanda) | ~0ms | ~15s (computa) | Variável |

**Justificativa:** Gastamos 50ms no boot para evitar 15s de latência na primeira chamada — o sistema não resiste ao fluxo inicial para evitar atrito posterior.

**Health Signal (`/health` → `cognitive`):**

| Métrica | Descrição | Interpretação |
|---------|-----------|---------------|
| `embedding_cache_size` | Items atuais no cache | 0-100 |
| `embedding_cache_limit` | Limite LRU | 100 (fixo) |
| `embedding_cache_usage_pct` | Porcentagem de uso | 0-100% |
| `cache_health` | Status qualitativo | `"high"` (>80%), `"normal"` (30-80%), `"low"` (<30%) |

**Diagnóstico Operacional:**

| Cenário | Interpretação | Ação Recomendada |
|---------|---------------|------------------|
| `cache_health="high"` (90-100%) | Cache saturado, LRU evictando constantemente | Aumentar `LRU_CACHE_SIZE` ou investigar sobrecarga do FewShotProvider |
| `cache_health="normal"` (30-80%) | Uso saudável, margem disponível | Nenhuma ação necessária |
| `cache_health="low"` (<30%) | Cache subutilizado | Reduzir `LRU_CACHE_SIZE` para economizar memória ou aumentar uso do FewShotProvider |

**Persistência:**
- Formato: **CBOR** (binário, eficiente para arrays numéricos)
- Path: `memory/data/json/fewshot_embeddings.cbor`
- Estrutura: `{"embeddings": {hash: [float32 array]}, "count": N}`
- Atualização: Salvo após `_preload_embeddings()` ou periodicamente

**Testes:** `tests/test_fewshot_embedding_cache.py` (7 testes)

### 18.6.4 DLQ Cycle → FewShotProvider (Adaptive Immunological Memory)

**Arquivos:** `iaglobal/core/few_shot_provider.py`, `iaglobal/obsidian/consolidation.py`

O ciclo **DLQ (Dead Letter Queue) → FewShotProvider** é a conexão entre o **sistema imunológico** (apoptose de cache tóxico) e o **sistema cognitivo** (aprendizado por exemplos negativos). Cada entrada em `00_Quarentena/cache_poison_*.json` torna-se uma "vacina" — um exemplo negativo que o sistema aprende a evitar.

**REMSleepEngine como Orquestrador de Imunidade (Integração #1 ✅ IMPLEMENTADA):**

O `REMSleepEngine` agora possui autonomia para varrer a DLQ, agregar padrões recorrentes e injetar vacinas no `FewShotProvider` — transformando "lixo tóxico" em "memória imunológica adaptativa".

**Fluxo Metabólico (Atualizado):**
```
Cache Tóxico Detectado (barreira imunológica)
     ↓
Apoptose + DLQ Write (00_Quarentena/cache_poison_{reason}_{timestamp}.json)
     ↓
REMSleepEngine.iniciar_fase_rem()
     ├── 1. await _process_quarantine_dlq() ← NOVO: orquestração de imunidade
     │    ├── _scan_quarantine() → asyncio.to_thread (I/O isolado)
     │    ├── Agregação por (reason, domain)
     │    ├── Threshold filter (DLQ_THRESHOLD=3)
     │    └── await few_shot_provider.ingest_dlq_examples()
     │
     └── 2. Consolidação de memórias (Short → Long Term)
     
     ↓
_process_quarantine_dlq() detalhado:
     ├── glob("cache_poison_*.json") em thread pool
     ├── _extract_domain(prompt_snippet) → heurística de domínio
     ├── Agregação: patterns[(reason, domain)] += count
     ├── Threshold: filter count >= 3
     └── Ingestão: _negative_examples.append()
     
     ↓
get_few_shot(task) → _from_dlq_pool(query)
     ↓
_rank() → _select_diverse() → _format_section()
     ↓
Prompt final: "Exemplo N (❌ a evitar — dlq:refusal_or_hallucination): ..."
```

**Arquitetura Assíncrona (async-first):**

| Componente | Padrão | Justificativa |
|------------|--------|---------------|
| `_process_quarantine_dlq()` | `async def` + `asyncio.to_thread()` | I/O de disco (`glob`, `read_text`) isolado em thread pool |
| `_scan_quarantine()` | Função síncrona aninhada | Executada em thread pool, I/O síncrono sem bloquear |
| `_extract_domain()` | `@staticmethod` | Heurística pura, sem I/O, tolerante a `None`/`""` |
| `ingest_dlq_examples()` | `async def` + `asyncio.to_thread()` | I/O de disco isolado (chamado por `_process_quarantine_dlq`) |
| `REMSleepEngine.iniciar_fase_rem()` | `await` em contexto async | Consistência com todo I/O do REMSleep |

**Implementação (_process_quarantine_dlq):**
```python
# consolidation.py
async def _process_quarantine_dlq(self) -> Dict[str, Any]:
    """Varre a DLQ, consolida padrões e prepara vacinas."""
    
    def _scan_quarantine() -> Dict[str, Any]:
        """I/O síncrono isolado em thread pool."""
        if not self.quarantine_dir.exists():
            return {"total_files": 0, "patterns": []}
        
        patterns: Dict[str, Dict] = {}
        total_files = 0
        for fpath in self.quarantine_dir.glob("cache_poison_*.json"):
            total_files += 1
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                reason = data.get("reason", "unknown")
                domain = REMSleepEngine._extract_domain(data.get("prompt_snippet", ""))
                
                key = f"{reason}:{domain}"
                if key not in patterns:
                    patterns[key] = {
                        "reason": reason,
                        "domain": domain,
                        "count": 0,
                        "snippets": [],
                        "first_seen": data.get("timestamp"),
                        "last_seen": data.get("timestamp"),
                    }
                patterns[key]["count"] += 1
                patterns[key]["snippets"].append(data.get("prompt_snippet", "")[:100])
            except Exception:
                continue
        
        return {"total_files": total_files, "patterns": list(patterns.values())}
    
    # Executa I/O em thread pool (non-blocking)
    scan_result = await asyncio.to_thread(_scan_quarantine)
    patterns = scan_result["patterns"]
    total_files = scan_result["total_files"]
    
    # Filtra por threshold (padrões recorrentes)
    significant = [p for p in patterns if p["count"] >= self.DLQ_THRESHOLD]
    
    # Injeta no FewShotProvider como vacinas
    ingested = await few_shot_provider.ingest_dlq_examples(self.quarantine_dir)
    
    return {
        "total_files_scanned": total_files,
        "significant_patterns": len(significant),
        "vaccines_injected": ingested,
    }
```

**Heurística de Domínio (_extract_domain):**
```python
@staticmethod
def _extract_domain(prompt_snippet: str) -> str:
    """Extrai domínio aproximado do prompt para agrupamento.
    
    Tolerante a null/empty strings — retorna 'general' como fallback.
    """
    if not prompt_snippet or not isinstance(prompt_snippet, str):
        return "general"
    
    snippet = prompt_snippet.lower()
    
    domains = {
        "api": ["api", "endpoint", "http", "rest", "graphql", "request"],
        "database": ["sql", "query", "database", "table", "insert", "select"],
        "frontend": ["react", "component", "jsx", "html", "css", "dom"],
        "security": ["auth", "token", "permission", "xss", "injection", "csrf"],
        "testing": ["test", "assert", "mock", "fixture", "pytest"],
        "async": ["async", "await", "event loop", "coroutine"],
    }
    
    for domain, keywords in domains.items():
        if any(kw in snippet for kw in keywords):
            return domain
    
    return "general"
```

**Idempotência:**
- **Chave determinística**: `dlq:{reason}:{md5(prompt_snippet)[:12]}` previne duplicação
- **Hash MD5** (não SHA3): usado por eficiência (apenas para deduplicação, não segurança)
- **Segunda ingestão retorna 0**: arquivos já processados são skipados via checagem de chave em `_example_cache`

**Ranking e Formatação:**
- **Score fixo**: `DLQ_SCORE = 0.15` (abaixo do threshold de corte `MIN_SCORE = 0.25`, mas ainda visível para aprendizado)
- **Marcação visual**: `_format_section()` prefixa com `❌ a evitar` para exemplos `dlq:*` e `mta_pool`
- **Fonte identificada**: `source="dlq:refusal_or_hallucination"` permite debugging e auditoria

**Integração no Ciclo REM (iniciar_fase_rem):**
```python
# consolidation.py
async def iniciar_fase_rem(self) -> Dict[str, Any]:
    resultado: Dict[str, Any] = {
        "iniciado_em": datetime.now(UTC).isoformat(),
        "memorias_processadas": 0,
        "memorias_consolidadas": 0,
        "contaminacoes_bloqueadas": 0,
        "dlq_processed": None,  # NOVO: processamento da DLQ
        "erros": [],
    }

    # === NOVO: Processamento da DLQ (antes da consolidação) ===
    try:
        dlq_result = await self._process_quarantine_dlq()
        resultado["dlq_processed"] = dlq_result
        if dlq_result["vaccines_injected"]:
            logger.info(
                "[REMSleep] DLQ vaccinated: %d padrões significativos, %d vacinas injetadas",
                dlq_result["significant_patterns"],
                dlq_result["vaccines_injected"],
            )
    except Exception as e:
        logger.exception("[REMSleep] Falha ao processar DLQ: %s", e)
        resultado["erros"].append(f"dlq_processing: {e}")
    # =========================================================

    # ... restante do ciclo de consolidação ...
```

**Métricas de Eficácia:**

| Métrica | Valor | Justificativa |
|---------|-------|---------------|
| `DLQ_THRESHOLD` | 3 | Mínimo de ocorrências para considerar "padrão recorrente" |
| Tempo de scan | ~5ms por arquivo JSON | Dominado por I/O de disco (thread pool) |
| Throughput | 100 arquivos em <2s | Thread pool permite paralelismo |
| Memória | ~200 bytes por exemplo negativo | Texto + metadata + embedding |
| Idempotência | ✅ Chave determinística | `dlq:{reason}:{md5_hash[:12]}` previne duplicação |

**Heurísticas de Domínio:**

| Domínio | Keywords Exemplo |
|---------|------------------|
| `api` | "api", "endpoint", "http", "rest", "graphql", "request" |
| `database` | "sql", "query", "database", "table", "insert", "select" |
| `frontend` | "react", "component", "jsx", "html", "css", "dom" |
| `security` | "auth", "token", "permission", "xss", "injection", "csrf" |
| `testing` | "test", "assert", "mock", "fixture", "pytest" |
| `async` | "async", "await", "event loop", "coroutine" |
| `general` | Fallback (nenhuma keyword encontrada) |

**Trade-off de Design (Threshold Fixo vs. Adaptativo):**

| Estratégia | Vantagem | Desvantagem |
|------------|----------|-------------|
| **Threshold fixo (atual)** | Simples, previsível, fácil de debugar | Não escala automaticamente com volume de DLQ |
| Threshold adaptativo | Ajusta-se ao volume (lei de potência) | Complexidade adicional, possível oscilação |

**Justificativa:** Threshold fixo (`DLQ_THRESHOLD = 3`) é suficiente para sistemas em crescimento. Futuro: implementar threshold adaptativo baseado em volume total de arquivos na DLQ.

**Health Signal (`/health` → futuro):**
```json
{
  "immune_state": {
    "dlq": {
      "total_ingested": 42,
      "last_ingestion": "2026-07-11T10:30:00Z",
      "negative_examples_active": 38,
      "quarantine_dir_size": 156
    }
  }
}
```

**Consumidores:**
- **PromptImprover**: usa `few_shot_provider.get_few_shot()` para injetar negativos em prompts de melhoria
- **CriticAgent**: pode usar DLQ para identificar padrões de falha recorrentes
- **ReflexionAgent**: analisa DLQ para gerar hipóteses de root cause

**Testes:**
- `tests/test_fewshot_embedding_cache.py` (5 testes DLQ):
  - `test_ingest_dlq_returns_count` — valida contagem de ingestão
  - `test_ingest_dlq_populates_negative_examples` — valida população do pool
  - `test_ingest_dlq_idempotent` — valida não-duplicação
  - `test_ingest_dlq_missing_dir_returns_zero` — valida graceful fallback
  - `test_ingest_dlq_appears_in_format` — valida formatação com ❌

- `tests/test_remsleep_dlq_scan.py` (6 testes REMSleep DLQ):
  - `test_dlq_scan_aggregates_patterns` — valida agregação por (reason, domain)
  - `test_dlq_scan_respects_threshold` — valida filtro por threshold=3
  - `test_dlq_scan_async_io_non_blocking` — valida I/O non-blocking (<2s para 100 arquivos)
  - `test_dlq_scan_missing_dir_returns_zero` — valida graceful fallback
  - `test_dlq_scan_idempotent` — valida não-duplicação de vacinas
  - `test_extract_domain_heuristics` — valida heurística de domínio (9 casos)

**Vetor Evolutivo (Próximas Mutações):**
- ~~**Varredura DLQ no REMSleep**~~ ✅ **IMPLEMENTADO**: `_process_quarantine_dlq()` agrega padrões, aplica threshold, injeta vacinas
- ~~**Expiry de Vacinas + Monitoramento**~~ ✅ **IMPLEMENTADO**: `_expire_old_vaccines()` remove vacinas >30 dias ou >100 items, métricas no `/health`
- **REMScan idle**: varrer `00_Quarentena/` periodicamente (cron) mesmo sem ciclo REM, gerando vacinas contínuas
- **DLQ prioritização**: exemplos com `reason="security_violation"` ou `reason="injection_attempt"` ganham score mais alto (0.25+) para maior visibilidade
- **Threshold adaptativo**: `DLQ_THRESHOLD` dinâmico baseado em volume total de arquivos (lei de potência)
- **EpigeneticRegistry integration**: padrões consolidados registrados para introspecção do Critic/Reflexion

### 18.7 Next Mutations

- ~~**Embedding preload**~~ ✅ **IMPLEMENTADO**: `FewShotProvider` agora tem:
  - Cache LRU em memória (100 embeddings)
  - Persistência CBOR em `memory/data/json/fewshot_embeddings.cbor`
  - `_get_or_compute_embedding()` com cache hit/miss
  - `preload=True` no `__init__` para carregar no boot
  - Redução de cold start: 15s → ~740ms (cache hit)
  - Testes: `tests/test_fewshot_embedding_cache.py` (7 testes)
  
  **Arquitetura do Cache:**
  - **Eager load** no boot (~50ms) → todo arquivo CBOR é carregado em memória
  - **LRU eviction** quando atinge 100 items
  - **Health signal** em `/health` → `cognitive.embedding_cache_size`, `embedding_cache_usage_pct`, `cache_health`
  - **Interpretação**: cache >80% = "high" (sinal de uso intenso), 30-80% = "normal", <30% = "low"

**Implementação completa do cache de embeddings**

- ~~**Ciclo DLQ → FewShotProvider**~~ ✅ **IMPLEMENTADO**:
  - `FewShotProvider.ingest_dlq_examples()` como `async def` + `asyncio.to_thread()`
  - `REMSleepEngine._process_quarantine_dlq()` agrega padrões por (reason, domain)
  - `REMSleepEngine.iniciar_fase_rem()` chama `_process_quarantine_dlq()` **antes** da consolidação
  - I/O de disco (`glob`, `read_text`) isolado em thread pool (non-blocking)
  - Heurística `_extract_domain()` classifica prompts por domínio (api, database, security, etc.)
  - Threshold `DLQ_THRESHOLD = 3` filtra padrões recorrentes
  - Idempotência: chave determinística `dlq:{reason}:{md5_hash[:12]}` previne duplicação
  - Formatação: exemplos DLQ marcados com ❌ "a evitar" no prompt
  - Testes: `tests/test_fewshot_embedding_cache.py` (5 testes DLQ) + `tests/test_remsleep_dlq_scan.py` (6 testes)
  
  **Arquitetura Assíncrona:**
  ```
  REMSleepEngine.iniciar_fase_rem()
       ↓
  await _process_quarantine_dlq()
       ├── _scan_quarantine() → asyncio.to_thread
       ├── Agregação por (reason, domain)
       ├── Threshold filter (count >= 3)
       └── await few_shot_provider.ingest_dlq_examples()
       ↓
  _negative_examples.append() → _from_dlq_pool() → rank → format
  ```
  
  **Métricas:**
  - Tempo de scan: ~5ms por arquivo JSON
  - Throughput: 100 arquivos em <2s (thread pool)
  - Memória: ~200 bytes por exemplo negativo
  - Idempotência: ✅ chave determinística
  
  **Vetores Futuros:**
  - REMScan idle: varrer `00_Quarentena/` periodicamente (cron) mesmo sem ciclo REM
  - DLQ prioritização: `reason="security_violation"` ganha score mais alto (0.25+)
  - Expiry de vacinas: exemplos >30 dias podem ser expirados se obsoletos
  - Threshold adaptativo: `DLQ_THRESHOLD` dinâmico baseado em volume total
  - EpigeneticRegistry integration: padrões consolidados registrados para introspecção

- ~~**Expiry de Vacinas + Monitoramento (Mutação 1C)**~~ ✅ **IMPLEMENTADO**:
  - `_expire_old_vaccines()` remove vacinas com idade >30 dias ou excedentes do cap (100 máx)
  - `ingest_dlq_examples()` chama expiry antes de injetar novas vacinas (defesa em profundidade)
  - Métricas no `/health` → `cognitive.few_shot.negative_examples_count`, `estimated_token_overhead`, `oldest_vaccine_age_days`
  - Alertas no REMSleep → warning se `token_overhead > 5000` tokens
  - Sincronização automática entre `_example_cache` e `_negative_examples`
  - Constantes: `MAX_VACCINE_AGE_DAYS = 30`, `MAX_VACCINES = 100`, `ESTIMATED_TOKENS_PER_EXAMPLE = 300`
  - Testes: `tests/test_fewshot_vaccine_expiry.py` (5 testes)
  
  **Arquitetura de Expiry:**
  ```
  ingest_dlq_examples()
       ↓
  _expire_old_vaccines() ← NOVO: chama antes de injetar
       ├── Expiry por idade (>30 dias)
       ├── Expiry por cap (>100 items, remove mais antigas)
       └── Sincroniza _example_cache ↔ _negative_examples
       ↓
  _scan_and_load() ← Injeta novas vacinas
  ```
  
  **Métricas no /health:**
  ```json
  {
    "cognitive": {
      "few_shot": {
        "negative_examples_count": 42,
        "oldest_vaccine_age_days": 12.5,
        "estimated_token_overhead": 12600,
        "max_vaccine_age_days": 30,
        "expiry_status": "ok"
      }
    }
  }
  ```
  
  **Benefícios:**
  - Previne prompt bloat (limite de 100 vacinas × 300 tokens = 30k tokens máx)
  - Visibilidade completa do estado de vacinas
  - Alertas precoces antes de estourar context window
  - Homeostase cognitiva garantida

📦 Resumo Final

* Arquitetura do Cache:
```
┌─────────────────────────────────────────┐
│  FewShotProvider.__init__(preload=False)│
│  ├── _embedding_cache: OrderedDict      │
│  ├── _example_cache: OrderedDict        │
│  └── _load_embedding_cache()            │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│  _get_or_compute_embedding(text)        │
│  ├── Hash SHA3-256 (16 chars)           │
│  ├── Check cache em memória             │
│  │   ├── Hit → retorna embedding        │
│  │   └── Miss → computa + cacheia       │
│  └── LRU eviction (100 items max)       │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────┐
│  _save_embedding_cache()                    │
│  └─ memory/data/json/fewshot_embeddings.cbor│
└─────────────────────────────────────────────┘
```
* API:

**Com preload no boot (recomendado)**
provider = FewShotProvider(preload=True)

**Sem preload (lazy, default)**
provider = FewShotProvider(preload=False)

**Singleton já usa preload=False**
from iaglobal.core.few_shot_provider import few_shot_provider

- ~~**DependencyEnforcer com install automático**~~ ✅ **IMPLEMENTADO**:

* API:

**Auto-install ativado por padrão**
enforcer = DependencyEnforcer(auto_install=True)

**Desativar auto-install (fallback para wrap)**
enforcer = DependencyEnforcer(auto_install=False)

* Fluxo de Decisão
```
Import não-stdlib não-instalado detectado
     ↓
Está no requirements.txt?
     ├── SIM → pip install -q (timeout 60s)
     │         ├── Sucesso → usa pacote instalado
     │         └── Falha → wrap em try/except
     └── NÃO → wrap em try/except ImportError
```
* Parsing de requirements.txt
- Remove comentários (# ...)
- Remove version specifiers (==, >=, <)
- Remove extras ([extra])
- Normaliza hifen → underscore (package-name → package_name)

  - Se import não-stdlib não-instalado for detectado
  - Verifica se está no `requirements.txt`
  - Se estiver: executa `pip install -q` automaticamente (timeout 60s)
  - Se não estiver: fallback para wrap em try/except ImportError
  - Cache de requirements.txt com parsing de version specifiers
  - Testes: `tests/test_dependency_enforcer_autoinstall.py` (8 testes)
 
- **CoT adaptativo**: variação do número de etapas baseado na complexidade da tarefa (detectada pelo ClassifierMemory).

- ~~**Dashboard de Entropia**~~ ✅ **IMPLEMENTADO**:
  - UI ReactPy: `iaglobal/ui/reactpy_components.py` → `/ui/entropy/`
  - CLI: `iaglobal/cli/status.py` → `iaglobal status` (seção `── Immune System ──`)
  - Dados: perfis, agentes em risco, degradando, thresholds, eventos da barreira, quarentena

---

## 20. MetabolicDataAdapter — CBOR2↔JSON Bridge for LLM Consumption

> **Objetivo:** Converter armazenamento interno (CBOR2 binário, SQLite BLOBs, JSON pools) em contexto JSON limpo que o LLM pode consumir nativamente — eliminando templates genéricos e substituindo por dados metabólicos vivos.

### 20.1 Anatomia do Adapter

**Arquivo:** `iaglobal/storage/metabolic_adapter.py`

```
LLM / CriticAgent / agente
     ↓
MemoryFirstRouter.route()
     ↓
Nível 2.5: MetabolicDataAdapter
     ↓
build_context(task)
     ↓
asyncio.gather (8 fontes em paralelo)
     ├── Epigenetic markers    ─── obsidian/epigenetic/*.cbor (CBOR2)
     ├── SAMe pool             ─── json/same_pool.json
     ├── Homocysteine pool     ─── json/homocysteine_pool.json
     ├── Glutathione pool      ─── json/glutathione_pool.json
     ├── Methylation engine    ─── json/methylation_engine.json
     ├── OmniMind collective   ─── memory/data/omnimind_state.json
     ├── Knowledge base        ─── json/knowledge.json
     └── SQLite STM/LTM        ─── CORE_DB → cbor2.loads(blob)
     ↓
JSON limpo (5.5KB típico) → LLM
```

### 20.2 Integração na Hierarquia de Memória

O `MemoryFirstRouter` passou de 5 para **6 níveis** de orquestração:

| Nível | Fonte | Confidence | Descrição |
|-------|-------|-----------|-----------|
| 0 | Cache exato (db.get_cached_search) | 0.95 | Hash SHA3-256 da task |
| 1 | STM + LTM + Vector + knowledge.json | 0.80 | Memória local consolidada |
| 2 | Obsidian Subconsciente (sussurrar_intuicao) | 0.75 | Intuição do vault markdown |
| **2.5** | **MetabolicDataAdapter (NOVO)** | **0.85** | **Dados metabólicos reais em JSON** |
| 3 | LLM local (Ollama qwen2.5:0.5b) | — | Síntese local |
| 4 | LLM externo (Groq/NVIDIA/Gemini) | — | Via CriticAgent + BanditPolicy |

**Por que confidence 0.85?** Dados metabólicos reais (pools, marcadores epigenéticos, memória coletiva) têm maior confiabilidade que intuição do Obsidian (0.75) — são fatos do sistema, não heurísticas.

### 20.3 Storage Type Config (Novo)

Dois novos seletores de ambiente controlam o comportamento do adapter:

| Variável | Valores | Default | Efeito |
|----------|---------|---------|--------|
| `METABOLIC_STORAGE_TYPE` | `auto`, `cbor2`, `json`, `sqlite` | `auto` | Filtra fontes consultadas pelo adapter |
| `MEMORY_STORAGE_TYPE` | `sqlite`, `json`, `cbor2` | `sqlite` | Backend de persistência STM/LTM |

**Definição em `iaglobal/_paths.py`:**
```python
MEMORY_STORAGE_TYPE = os.environ.get("MEMORY_STORAGE_TYPE", "sqlite")
METABOLIC_STORAGE_TYPE = os.environ.get("METABOLIC_STORAGE_TYPE", "auto")
```

**Exemplo de uso no MetabolicAdapter (`build_context`):**
```python
fetch_cbor = storage_type in ("auto", "cbor2")
fetch_json = storage_type in ("auto", "json")
fetch_sql  = storage_type in ("auto", "sqlite")
```

### 20.4 Perfil Antioxidante

| ROS | GSH |
|-----|-----|
| CBOR2 corrompido | `cbor2.load()` envolvido em try/except |
| Pool JSON ausente | `_read_json_file()` retorna `None` silenciosamente |
| SQLite BLOBs inválidos | `cbor2.loads()` com fallback individual |
| Fonte demorando | `asyncio.gather()` com `return_exceptions=True` — falha parcial não bloqueia |
| Contexto vazio | Retorna `""` em vez de JSON inválido |

### 20.5 Diferenciação (Escalabilidade)

O adapter respeita o `METABOLIC_STORAGE_TYPE` para se especializar conforme o ambiente:

- **Ambiente dev (auto)**: todas as 8 fontes — máximo contexto
- **Ambiente serverless (json)**: apenas JSON — sem dependência de CBOR2 ou SQLite
- **Ambiente mínimo (cbor2)**: apenas epigenéticos — menor footprint
- **Ambiente analítico (sqlite)**: apenas STM/LTM — foco em histórico recente

### 20.6 Protocolo de Evolução Epigenética

A integração no `MemoryFirstRouter` é **epigenética** — muda comportamento sem alterar o código base:

- Flag implícita: existência do módulo `metabolic_adapter` decide se Nível 2.5 é tentado
- Config `METABOLIC_STORAGE_TYPE` decide quais genes (fontes) são expressos
- Se o adapter falha, o sistema recai silenciosamente para o comportamento anterior (LLM local)

### 20.7 Vetor Evolutivo

- **Cache de contexto metabólico**: evitar re-leitura das 8 fontes em chamadas consecutivas no mesmo ciclo
- **Pool de homocisteína como gate**: se homocysteine_pool > 70%, diminuir confidence do adapter
- **Observabilidade**: expor métricas do adapter no `/health` (fontes lidas, tamanho, latência)
- **Adapters especializados por storage type**: classes separadas para `Cbor2Adapter`, `JsonAdapter`, `SqliteAdapter` herdando de `BaseMetabolicAdapter`

---

## 20.8 Metabolismo ↔ Obsidian Interface — Sistema Nervoso Metabólico

### Visão Geral

A pasta `iaglobal/metabolism/` contém **dois tipos de módulos** com responsabilidades distintas:

```
iaglobal/metabolism/
├── 🧬 Metabolismo Puro (sem dependências externas)
│   ├── homocysteine_pool.py         # Detecta toxicidade (acúmulo de erros)
│   ├── methylation_cycle.py         # Ciclo de transformação de dados
│   ├── transsulfuration_cycle.py    # Caminho alternativo de reciclagem
│   └── metabolic_metrics.py         # Calcula IVM (P, E, C)
│
└── 🔗 Interface Metabolismo→Obsidian (módulos de ação)
    ├── clarity_directive.py         # Avalia IVM → decide apoptose via OmniMind
    ├── metabolic_invariants.py      # Monitora saúde → age no Obsidian
    ├── metabolic_autocorrect.py     # Corrige invariantes → DeltaSleep + OmniMind
    └── methylation_engine.py        # Gerencia ciclo → registra skills no Epigenetic
```

### Por Que Esta Separação?

**Metabolismo Puro** (lado esquerdo):
- ✅ **Função**: Processar dados brutos → métricas (IVM, homocisteína, SAMe)
- ✅ **Dependências**: Apenas dados (SQLite, JSON, CBOR2)
- ✅ **Responsabilidade**: Calcular estado metabólico do sistema
- ✅ **Testabilidade**: Alta — funções puras, sem efeitos colaterais

**Interface Metabolismo→Obsidian** (lado direito):
- ✅ **Função**: Traduzir métricas → ações no organismo (Obsidian)
- ✅ **Dependências**: `obsidian.omnimind`, `obsidian.epigenetic_registry`, `obsidian.subconscious`
- ✅ **Responsabilidade**: Agir com base no estado metabólico
- ✅ **Testabilidade**: Média — requer mocks do Obsidian

### Analogia Biológica

| Computacional | Biológico | Exemplo |
|--------------|-----------|---------|
| `MetabolicMetrics` | Mitocôndria | Produz ATP (IVM) |
| `HomocysteinePool` | Fígado | Detecta toxinas (erros) |
| `ClarityDirective` | Sistema Nervoso | Decide apoptose celular |
| `MetabolicAutocorrect` | Sistema Endócrino | Libera hormônios (correções) |
| `MethylationEngine` | Medula Óssea | Produz novas células (skills) |

### Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────┐
│                    METABOLISMO PURO                         │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────┐  │
│  │ Homocysteine │────▶│ Methylation  │────▶│  Metrics    │  │
│  │    Pool      │     │    Cycle     │     │  (IVM=P+E+C)│  │
│  └──────────────┘     └──────────────┘     └─────────────┘  │
│         │                    │                      │       │
│         │ (dados)            │ (dados)              │ (IVM) │
│         ▼                    ▼                      ▼       │
└─────────────────────────────────────────────────────────────┘
          │                    │                      │
          │ (ação)             │ (ação)               │ (ação)
          ▼                    ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│              INTERFACE METABOLISMO→OBSIDIAN                 │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────┐  │
│  │   Clarity    │     │   Autocorrect│     │  Methylation│  │
│  │  Directive   │     │              │     │   Engine    │  │
│  └──────┬───────┘     └──────┬───────┘     └──────┬──────┘  │
│         │                    │                    │         │
│         ▼                    ▼                    ▼         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              OBSIDIAN (Ações no Organismo)          │    │
│  │  - OmniMind (apoptose de agentes)                   │    │
│  │  - EpigeneticRegistry (registro de skills)          │    │
│  │  - SubconsciousAPI (leitura de memória)             │    │
│  │  - DeltaSleepSync (correções em background)         │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Módulos de Interface — Detalhamento

#### 1. ClarityDirective (`clarity_directive.py`)

**Propósito**: Decidir se uma tarefa/agente deve sofrer "clareamento" (apoptose) baseado no IVM.

```python
class ClarityDirective:
    THRESHOLD_VAZIO = 0.1  # IVM mínimo para evitar apoptose
    
    async def avaliar_tarefa(self, agent_id: str, ivm: float) -> bool:
        if ivm < self.THRESHOLD_VAZIO:
            # IVM muito baixo → agente não está contribuindo
            # Aciona apoptose via OmniMind
            await self.omni_mind.trigger_apoptosis(agent_id)
            return True  # Clareou (removeu)
        return False  # Manteve
```

**Por que está em metabolism/**: A decisão é **metabólica** (baseada em IVM), mas a ação é no Obsidian.

---

#### 2. MetabolicInvariants (`metabolic_invariants.py`)

**Propósito**: Monitorar invariantes de saúde metabólica do sistema.

```python
class MetabolicInvariants:
    async def check_all(self) -> Dict[str, Dict]:
        return {
            "vault": await self._check_vault_capacity(),      # Obsidian
            "latency": await self._check_fugue_latency(),     # FugueCompartment
            "toxins": await self._check_toxin_removal(),      # DeltaSleep
            "ivm": await self._check_system_ivm(),            # MetabolicMetrics
        }
```

**Invariantes Monitoradas**:
- `vault_capacity`: Obsidian não está cheio (>90% = alerta)
- `fugue_latency`: Latência do FugueCompartment está aceitável
- `toxin_removal`: DeltaSleep está removendo erros
- `system_ivm`: IVM global do sistema está saudável

**Por que está em metabolism/**: As métricas são metabólicas, mas as verificações usam APIs do Obsidian.

---

#### 3. MetabolicAutocorrect (`metabolic_autocorrect.py`)

**Propósito**: Aplicar correções automáticas quando invariantes são violadas.

```python
class MetabolicAutocorrect:
    async def verificar_e_corrigir(self) -> Dict:
        result = {"invariantes": {}, "correcoes": {}}
        
        # Verifica invariantes
        checks = await self.invariants.check_all()
        
        # Aplica correções se necessário
        for invariant, status in checks.items():
            if status["status"] == "violated":
                correcao = await self._corrigir(invariant)
                result["correcoes"][invariant] = correcao
        
        return result
```

**Correções Automáticas**:
- Se `vault_capacity` > 90% → Aciona limpeza via DeltaSleep
- Se `toxin_removal` falhando → Força remoção de erros antigos
- Se `system_ivm` < 0.5 → Reduz carga de agentes

**Por que está em metabolism/**: As correções são baseadas em métricas metabólicas, mas agem no Obsidian.

---

#### 4. MethylationEngine (`methylation_engine.py`)

**Propósito**: Gerenciar o ciclo completo de metilação (transformação de dados → skills).

```python
class MethylationEngine:
    async def processar_ciclo(self, candidate: CandidateSkill) -> bool:
        # 1. Avalia skill (metabolismo puro)
        score = await self._avaliar(candidate)
        
        # 2. Se score alto → registra no EpigeneticRegistry (Obsidian)
        if score > self.threshold:
            await self.epigenetic_registry.register(candidate)
            return True
        
        # 3. Se score médio → guarda como guardrail (metabolismo)
        elif score > self.guardrail_threshold:
            await self.homocysteine_pool.route_to_guardrail(candidate)
            return False
        
        # 4. Se score baixo → descarta (apoptose)
        return False
```

**Por que está em metabolism/**: O ciclo de metilação é um processo metabólico, mas o registro final é no Obsidian.

---

### Princípio de Design: Separação de Responsabilidades

**Regra**: Módulos em `metabolism/` que importam do Obsidian **NÃO devem**:
- ❌ Criar instâncias diretas de classes do Obsidian
- ❌ Modificar estado do Obsidian diretamente
- ❌ Depender de detalhes de implementação do Obsidian

**Devem**:
- ✅ Usar interfaces estáveis (`omni_mind`, `epigenetic_registry`, `subconscious`)
- ✅ Manter lógica metabólica separada da ação no Obsidian
- ✅ Ser testáveis com mocks do Obsidian

### Exemplo de Teste com Mock

```python
# tests/test_clarity_directive.py
async def test_clarear_com_ivm_baixo(mocker):
    # Mock do Obsidian
    mock_omni_mind = mocker.Mock()
    mock_omni_mind.trigger_apoptosis = mocker.AsyncMock()
    
    # Cria directive com mock
    directive = ClarityDirective()
    directive.omni_mind = mock_omni_mind
    
    # Testa com IVM baixo
    result = await directive.avaliar_tarefa("agent_123", ivm=0.05)
    
    # Verifica se apoptose foi acionada
    assert result == True
    mock_omni_mind.trigger_apoptosis.assert_called_once_with("agent_123")
```

### Roadmap de Refatoração (Opcional)

Se o acoplamento aumentar demais, considerar:

**Opção A**: Mover módulos de interface para `iaglobal/obsidian/metabolic_monitor/`
- ✅ Separação clara de responsabilidades
- ❌ Quebra imports em todo o código
- ❌ Risco de regressão

**Opção B**: Criar subpasta `iaglobal/metabolism/monitoring/`
- ✅ Organização interna sem quebrar imports
- ⚠️ Ainda mantém acoplamento

**Opção C (Atual)**: Manter em `metabolism/` com documentação clara
- ✅ Zero quebra de código
- ✅ Documentação explica o "porquê"
- ⚠️ Acoplamento permanece visível

**Decisão Atual**: Opção C — documentação é suficiente por enquanto.

**Atualização v1.1 (jul 2026)**: Subconsciente unificado em `obsidian/`
- ✅ `fugue_compartment.py` e `delta_sleep.py` movidos para `iaglobal/obsidian/`
- ✅ `subconscious/subconscious_api.py` (wrapper) removido
- ✅ Pasta `iaglobal/subconscious/` eliminada
- ✅ Todos imports atualizados: `iaglobal.subconscious.*` → `iaglobal.obsidian.*`
- ✅ `obsidian/__init__.py` exporta: `SubconsciousAPI`, `FugueCompartment`, `DeltaSleepSync`

---

## 20.9 Subconsciente Unificado — Arquitetura Consolidada

### Visão Geral

O sistema de processamento subconsciente agora está **totalmente integrado** ao módulo `obsidian/`:

```
iaglobal/obsidian/
├── 🧠 Subconsciente (processamento em background)
│   ├── subconsciousapi.py          # API unificada de acesso ao vault
│   ├── fugue_compartment.py        # Processamento de tarefas críticas
│   └── delta_sleep.py              # Limpeza e compactação (sono delta)
│
├── 🛡️ Sistema Imunológico
│   ├── omnimind.py                 # Apoptose e decisões contratuais
│   └── epigenetic_registry.py      # Registro de skills e configurações
│
├── 💾 Armazenamento de Memória
│   ├── 01_Instincts/               # Regras inatas
│   ├── 02_Short_Term/              # STM (tarefas recentes)
│   ├── 03_Long_Term/               # LTM (conhecimento consolidado)
│   ├── 04_Synapses/                # Conexões entre memórias
│   └── 05_Vaccines/                # Padrões de defesa
│
└── 🔄 Ciclo de Consolidação
    └── consolidation.py             # REMSleepEngine (curto → longo prazo)
```

### Por Que Esta Consolidação?

**Antes** (pasta `subconscious/` separada):
- ❌ Wrapper redundante (`subconscious_api.py` delegava para `obsidian/subconsciousapi.py`)
- ❌ Imports confusos: `from iaglobal.subconscious.fugue_compartment`
- ❌ Duplicação de responsabilidade
- ❌ Acoplamento oculto entre módulos

**Depois** (tudo em `obsidian/`):
- ✅ **Unicidade**: API real e processadores no mesmo módulo
- ✅ **Clareza**: `from iaglobal.obsidian import FugueCompartment`
- ✅ **Coerência**: Todo processamento de memória em um lugar
- ✅ **Manutenibilidade**: Zero wrappers, imports diretos

### Fluxo de Processamento Subconsciente

```
┌─────────────────────────────────────────────────────────────┐
│                    TAREFA CRÍTICA                           │
│  (ex: "Processar 1000 embeddings em background")            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              FugueCompartment (Processamento)               │
│  - Isola tarefa do pipeline consciente                      │
│  - Executa em asyncio.create_task()                         │
│  - Monitora latência e progresso                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              SubconsciousAPI (Registro no Vault)            │
│  - Cria nota em 03_Long_Term/FugueTasks/                    │
│  - Metadados: origem, tipo, agent_id, status                │
│  - Permite busca posterior via SmartQuery                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              DeltaSleepSync (Limpeza Periódica)             │
│  - Compacta notas antigas (>7 dias)                         │
│  - Remove toxinas (dados não referenciados)                 │
│  - Libera espaço no vault                                   │
└─────────────────────────────────────────────────────────────┘
```

### exports do Módulo `obsidian`

O arquivo `iaglobal/obsidian/__init__.py` exporta:

```python
from iaglobal.obsidian import (
    SubconsciousAPI,       # API de acesso ao vault
    FugueCompartment,      # Processamento em background
    DeltaSleepSync,        # Limpeza e compactação
    omni_mind,             # Sistema imunológico
    EpigeneticRegistry,    # Registro de skills
)
```

### Histórico da Refatoração

**v1.0** (jun 2026):
- `iaglobal/subconscious/` criado como pasta separada
- Wrapper `subconscious_api.py` delega para `obsidian/subconsciousapi.py`

**v1.1** (jul 2026):
- `fugue_compartment.py` e `delta_sleep.py` movidos para `obsidian/`
- Wrapper removido
- Pasta `subconscious/` eliminada
- 8 arquivos atualizados com novos imports

**Benefícios**:
- Zero redundância de código
- Imports mais claros e diretos
- Co-localização de responsabilidade
- Menor superfície de manutenção

---

## 21. Skill Templates — Centralized Prompt Management

### Problem Solved

Previously, prompt templates were hardcoded inline within skill definitions in `skill.py`, causing:
- **Cache collisions**: Multiple skills using the same generic prompt (e.g., just `{task}`) resulted in identical cache keys
- **Maintenance difficulty**: Finding and editing prompts required searching through 1500+ lines of skill definitions
- **No separation of concerns**: Prompt engineering mixed with skill contract definitions

### Solution: Template-Driven Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    iaglobal/evolution/skills/                   │
├─────────────────────────────────────────────────────────────────┤
│  templates/                    # Centralized prompt library     │
│  ├── README.md                 # Documentation & conventions    │
│  ├── planner.txt               # SKILL_PLANNER prompt           │
│  ├── coder.txt                 # SKILL_CODER prompt             │
│  ├── critic.txt                # SKILL_CRITIC prompt            │
│  ├── architect.txt             # SKILL_ARCHITECT prompt         │
│  ├── api_design.txt            # SKILL_API_DESIGN prompt        │
│  ├── database_design.txt       # SKILL_DATABASE_DESIGN prompt   │
│  ├── frontend_builder.txt      # SKILL_FRONTEND_BUILDER prompt  │
│  ├── backend_builder.txt       # SKILL_BACKEND_BUILDER prompt   │
│  ├── requirements.txt          # SKILL_REQUIREMENTS prompt      │
│  ├── business_rules.txt        # SKILL_BUSINESS_RULES prompt    │
│  ├── domain_analysis.txt       # SKILL_DOMAIN_ANALYSIS prompt   │
│  ├── technology_selection.txt  # SKILL_TECHNOLOGY_SELECTION     │
│  ├── system_design.txt         # SKILL_SYSTEM_DESIGN prompt     │
│  ├── integrator.txt            # SKILL_INTEGRATOR prompt        │
│  ├── test_generator.txt        # SKILL_TEST_GENERATOR prompt    │
│  ├── documentation.txt         # SKILL_DOCUMENTATION prompt     │
│  ├── security_audit.txt        # SKILL_SECURITY_AUDIT prompt    │
│  └── performance_audit.txt     # SKILL_PERFORMANCE_AUDIT prompt │
│                                                                 │
│  template_loader.py            # Auto-loader with LRU cache     │
│  skill.py                      # Skills reference templates     │
└─────────────────────────────────────────────────────────────────┘
```

### Template Loader Architecture

```python
# iaglobal/evolution/skills/template_loader.py

from functools import lru_cache
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"

@lru_cache(maxsize=128)
def load_skill_template(skill_name: str, default: str = "") -> str:
    """Carrega template automaticamente da pasta templates/.
    
    Normalizes skill name (removes "skill_" prefix and "_agent" suffix).
    Returns template content or default if not found.
    """
    normalized = skill_name.lower().replace("skill_", "").replace("_agent", "")
    template_file = TEMPLATES_DIR / f"{normalized}.txt"
    
    if template_file.exists():
        return template_file.read_text(encoding="utf-8").strip()
    
    return default
```

### Skill Definition Pattern

```python
# iaglobal/evolution/skills/skill.py

from iaglobal.evolution.skills.template_loader import load_skill_template as _get_template

SKILL_CODER = Skill(
    name="coder",
    description="Gera código a partir de especificação",
    inputs=["task", "plan"],
    outputs=["code"],
    constraints=["llm", "python", "syntax_valid"],
    template_type="llm",
    template_prompt=_get_template("coder"),  # ← Loads from templates/coder.txt
)
```

### Cache Key Differentiation

**Before (cache collision):**
```
All skills → template_prompt="" → fallback to ctx.get("task")
Cache key: SHA256("groq:groq/llama-3.3-70b-versatile:create a REST API...")
Result: ALL agents get SAME cached response ❌
```

**After (unique prompts):**
```
coder      → templates/coder.txt      → "Como desenvolvedor sênior...{task}...{plan}"
critic     → templates/critic.txt     → "Como critic de código...{code}...{task}"
architect  → templates/architect.txt  → "Como arquiteto de software...{task}...{requirements}"

Cache keys are now UNIQUE per skill ✅
```

### Template Syntax

Templates use placeholder syntax for context injection:

```txt
# templates/coder.txt

Como desenvolvedor sênior especializado em Python, implemente código para: {task}

Siga o plano de execução: {plan}

REQUISITOS OBRIGATÓRIOS:
1. Código limpo e legível (Clean Code)
2. Tipagem estática (type hints) quando aplicável
3. Docstrings no formato Google ou NumPy
...
```

**Available placeholders:**
- `{task}` → Original user task
- `{refined_task}` → Task refined by interpreter
- `{plan}` → Execution plan from planner
- `{requirements}` → Requirements (RFs + RNFs)
- `{business_rules}` → Business rules
- `{architect}` → System architecture
- `{code}` → Generated code
- `{execution_plan}` → Detailed execution plan
- `{api_design}` → API specification
- `{db_schema}` → Database schema

### Benefits

| Benefit | Description |
|---------|-------------|
| **Maintainability** | Edit prompts in isolated `.txt` files without touching skill contracts |
| **Cache Integrity** | Each skill has unique prompt → unique cache key → no collisions |
| **Prompt Engineering** | Dedicated space for prompt optimization, A/B testing, versioning |
| **Separation of Concerns** | Skill contract (inputs/outputs) separate from prompt content |
| **Automatic Loading** | `@lru_cache` ensures templates loaded once, reused efficiently |
| **Validation** | `validate_template()` function checks placeholder validity |

### Usage Examples

**Add new template:**
1. Create `templates/new_skill.txt`
2. Use appropriate placeholders
3. In skill definition: `template_prompt=_get_template("new_skill")`

**Modify existing template:**
1. Edit the `.txt` file
2. New prompt automatically used on next execution

**Validate template:**
```python
from iaglobal.evolution.skills.template_loader import validate_template

valid, placeholders, msg = validate_template("coder")
# Returns: (True, ["task", "plan"], "Template válido com 2 placeholders")
```

### Evolutionary Impact

This architecture enables:
- **Rapid prompt iteration**: Test new prompts without code changes
- **Skill-specific optimization**: Tailor prompts per skill's domain
- **A/B testing**: Swap templates to compare performance
- **Version control**: Track prompt changes independently from code
- **Community contributions**: Non-developers can improve prompts

---

## 📋 ROADMAP_2.md — Evolution History

### Integration #1: DLQ Scan in REMSleep (✅ COMPLETA)

**Status:** 7/7 fases completas, 807 testes passando

**Implementações:**
- `_process_quarantine_dlq()` — varre DLQ, agrega por (reason, domain), aplica threshold=3
- `_extract_domain()` — heurística de 6 domínios + fallback "general"
- Integração no `iniciar_fase_rem()` — chama DLQ scan **antes** da consolidação
- 6 testes em `test_remsleep_dlq_scan.py`

### Integration #2: Mutation 1C (Expiry + Monitoramento) (✅ COMPLETA)

**Status:** 6/6 fases completas, 812 testes passando

**Implementações:**
- `_expire_old_vaccines()` — remove vacinas >30 dias ou >100 items
- Integração no `ingest_dlq_examples()` — chama expiry antes de injetar
- Métricas no `/health` — `negative_examples_count`, `estimated_token_overhead`, etc.
- Alertas no REMSleep — warning se token_overhead >5000
- 5 testes em `test_fewshot_vaccine_expiry.py`

**Constantes:**
```python
MAX_VACCINE_AGE_DAYS = 30
MAX_VACCINES = 100
ESTIMATED_TOKENS_PER_EXAMPLE = 300
```

**Bug Corrigido:** Sincronização entre `_example_cache` e `_negative_examples` estava falhando por comparação incompleta de chaves MD5.

---

## 22. SearXNG Integration — Web Search Infrastructure

### Visão Geral

**SearXNG** é um **meta-buscador** que agrega resultados de múltiplos provedores (Google, Bing, DuckDuckGo, Wikipedia, etc.) sem rastreamento. No iaglobal, ele opera como **fonte de busca web primária** quando disponível.

### Arquitetura de Integração

```
┌─────────────────────────────────────────────────────────────┐
│                    iaglobal/search/                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           SearchMiddleware (enrich())                │   │
│  │  1. _needs_web_search() — classifica necessidade     │   │
│  │  2. ConfidenceTracker — skip se confiança alta       │   │
│  │  3. Obsidian cache — verifica antes da web           │   │
│  │  4. _expand_query() — expande termos                 │   │
│  │  5. Busca paralela:                                  │   │
│  │     - searxng_search() ← primário                    │   │
│  │     - duckduckgo_search() ← fallback                 │   │
│  │     - youcom_search() ← cloud (se disponível)        │   │
│  │  6. _synthesize_context() — LLM resume (opcional)    │   │
│  │  7. Injeta [CONTEXTO] no prompt                      │   │
│  │  8. Agenda persistência Obsidian (fire-and-forget)   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              iaglobal/graphs/nodes/_search_sources.py       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  searxng_search(query: str) -> str                   │   │
│  │  - Circuit breaker com TTL progressivo               │   │
│  │  - Timeout: 15s (normal) / 3s (fallback)             │   │
│  │  - Agrega 5 resultados de múltiplos engines          │   │
│  │  - Deduplica por título                              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           SearXNG Instance (localhost:4000)                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  /search?q={query}&format=json&language=en           │   │
│  │ → JSON: { results: [ {title, url, content, engine} ]}│   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Circuit Breaker (Proteção Contra Falhas)

O SearXNG tem **proteção automática** contra indisponibilidade:

```python
# Estado global do módulo
_searxng_offline_until: float = 0.0  # Timestamp de retorno
_searxng_fail_count: int = 0         # Falhas consecutivas

# Após 3 falhas, TTL aumenta para 300s (5 minutos)
def _searxng_ttl() -> float:
    if _searxng_fail_count >= 3:
        return 300.0
    return 60.0  # 1 minuto entre tentativas
```

**Fluxo de Falha**:
1. Falha na conexão → `_mark_searxng_offline()`
2. Incrementa `_searxng_fail_count`
3. Calcula TTL progressivo (60s → 300s)
4. Define `_searxng_offline_until = now + TTL`
5. Durante TTL: retorna `""` imediatamente (sem tentar)
6. Após TTL: tenta novamente com timeout reduzido (3s)
7. Sucesso: reseta contadores via `_reset_searxng_state()`

### Formato da Requisição

```python
def searxng_search(query: str) -> str:
    import urllib.parse as _up
    
    base = _searxng_base_url()  # http://localhost:4000
    q = _up.quote(query)
    
    # URL formatada
    url = f"{base}/search?q={q}&format=json&language=en"
    
    # Request com User-Agent
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "IAGlobal/1.0"}
    )
    
    # Timeout adaptativo
    timeout = 3.0 if _searxng_fail_count > 0 else 15.0
    
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
```

### Formato da Resposta

**JSON do SearXNG**:
```json
{
  "results": [
    {
      "title": "Flask REST API Tutorial",
      "url": "https://flask.palletsprojects.com/en/2.3.x/quickstart/",
      "content": "A quickstart guide for building REST APIs with Flask...",
      "engine": "google",
      "score": 0.95
    }
  ]
}
```

**Processamento no iaglobal**:
```python
results = data.get("results", [])
lines = []
seen = set()

for item in results[:5]:  # Top 5 resultados
    title = item.get("title", "")
    url = item.get("url", "")
    content = item.get("content", "")
    engine = item.get("engine", "")
    
    # Deduplica por título
    if title in seen:
        continue
    seen.add(title)
    
    # Formata resultado
    lines.append(
        f"• {title} [{engine}]\n"
        f"  {url}\n"
        f"  {content[:200]}"
    )

return "\n\n".join(lines)
```

### Configuração

**Variável de Ambiente**:
```bash
# .env
SEARXNG_URL=http://localhost:4000
```

**Default**: `http://localhost:4000` (se não especificado)

### Comparação: SearXNG vs Outros Provedores

| Provedor | Tipo | Configuração | Status |
|----------|------|--------------|--------|
| **SearXNG** | Meta-buscador local | `SEARXNG_URL` | ✅ Primário |
| **DuckDuckGo** | Buscador direto | Nenhuma | ✅ Fallback |
| **You.com** | API cloud | `YOUCOM_API_KEY` | ⚠️ Opcional |
| **SerpAPI** | API Google | `SERPAPI_KEY` | ❌ Não implementado |

### Tratamento de Erros

**Erros Comuns**:

| Erro | Causa | Solução |
|------|-------|---------|
| `URLError: Connection refused` | SearXNG fora do ar | Circuit breaker ativa TTL 60s |
| `TimeoutError` | Timeout 15s excedido | Retry com timeout 3s |
| `JSONDecodeError` | Resposta inválida | Log debug, retorna `""` |
| `HTTPError 429` | Rate limit | Aumenta TTL para 300s |

### Métricas de Uso

O SearchMiddleware registra:
- ✅ Buscas realizadas (sucesso/falha)
- ✅ Latência média por provedor
- ✅ Taxa de cache hit (Obsidian)
- ✅ Economia de tokens (contexto pré-buscado)

---

**Próxima Integração (#3):** EpigeneticRegistry Integration — registrar padrões consolidados para introspecção do Critic/Reflexion.
