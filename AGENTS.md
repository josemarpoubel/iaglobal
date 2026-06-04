# IAGlobal — Sistema Multi-Agente Autônomo

Pipeline determinístico em DAG (25 nós, 6 fases), memória persistente multicamadas, evolução genética, orquestração híbrida local/cloud com governança formal.

## Goal

Manter e evoluir o sistema multi-agente IAGlobal. O pipeline V3 está completo e funcional. Alterações devem preservar os 536 testes passando.

## Pipeline V3

### Fluxo completo (25 nós)
```
prompt_intake → enhancement → orchestrator_agent → pm → requirements
→ architect → search → knowledge → dependency → risk_analysis
→ security_design → performance_design → planner → coder → reviewer
→ semantic_validator → security_audit → performance_audit → tester
→ debug_coder → coder ↺ → documentation → release → metrics
→ optimization → result_agent
```

### 6 Fases
| Fase | Nós | Descrição |
|------|-----|-----------|
| Definição | 12 | intake → enhancement → orchestrator → pm → requirements → architect → search → knowledge → dependency → risk → security_design → performance_design |
| Planejamento | 1 | planner |
| Construção | 1 | coder |
| Qualidade | 4 | reviewer → semantic → security_audit → performance_audit |
| Correção | 2 | tester → debug_coder → coder (loop) |
| Entrega | 5 | documentation → release → metrics → optimization → result_agent |

## Constraints

- **Paths**: tudo em `/home/user/projeto-iaglobal/iaglobal/memory/data/`
- **Coder híbrido**: 1 nó recebe `specialization_instructions` do MetaAgentDesigner
- **Timeouts**: todos os providers 30s (Ollama, Groq, OpenRouter, NVIDIA, OpenCode, Gemini)
- **Fallback**: ollama sempre incluso no final da chain
- **Governança**: CognitiveProxy decide; Critic é sensor passivo; contratos formais via GovernanceLayer
- **Abordagem híbrida**: MetaAgentDesigner gera `specialization_instructions`, não cria nós no DAG

## Key Decisions

- **Dependency determinístico**: regex + 200+ tabela import→pacote + `pip list`
- **Knowledge sequencial**: entre search e dependency (não mais transversal)
- **BanditPolicy**: seleciona modelo por eficiência/score (ε-greedy); providers/ executa chamadas
- **aiohttp sessions**: persistidas por event loop (`_sessions: Dict[int, ClientSession]`)
- **Crossover forçado**: quando ≤2 EVO agents, pula random gate (70% skip) — prevenção de extinção
- **Critic é sensor**: apenas avalia e emite score JSON; CognitiveProxy decide retry/continue
- **errors.json centralizado**: aprendizado por `query_relevant_errors()` + `[REINCIDENCIA]`

## Project Structure

245 arquivos em 133 diretórios. Estrutura principal:

```
iaglobal/
├── agents/           — 17 agentes especializados
├── core/             — CognitiveProxy, Governance, RetryHandler, Orchestrator
├── graphs/           — DAG Builder, BanditPolicy, ExecutionEngine, Node
├── evolution/        — EvolutionEngine, Skills, CollapseDetector, Replay
├── memory/           — STM, LTM, Vector, Semantic Cache, FusionEngine, errors
├── providers/        — 6 providers LLM + router + load balancer
├── pipeline/         — PipelineEngine, stages, state
├── cli/              — CLI principal + evolution-lab
├── tests/            — 536 testes, 0 falhas
└── docs/             — ROADMAP.md
```

## Providers

| Provider | Modelo | Timeout |
|----------|--------|---------|
| Ollama | qwen2.5:0.5b | 30s |
| Groq | llama-3.1-8b-instant | 30s |
| OpenRouter | (seleção por score) | 30s |
| NVIDIA | meta/llama-3.3-70b-instruct | 30s |
| OpenCode | nemotron-3-super-free | 30s |
| Gemini | gemini-2.5-flash-lite | 30s |

## Tests

536 testes, 0 falhas. Suites principais em `iaglobal/tests/`.

## Relevant Files

- `iaglobal/_paths.py` — Paths centralizados
- `iaglobal/graphs/builder.py` — PIPELINE_SKILLS V3 + run functions
- `iaglobal/evolution/skills/skill.py` — 25 Skills V3
- `iaglobal/evolution/evolutionengine.py` — CORE_NODE_NAMES, mutação/crossover
- `iaglobal/core/cognitive_proxy.py` — Orquestrador determinístico 6 estágios
- `iaglobal/core/governance.py` — GovernanceLayer com contratos formais
- `iaglobal/core/retry_handler.py` — Retry inteligente + escalonamento
- `iaglobal/providers/provider_router.py` — Roteamento + fallback chain
- `iaglobal/memory/memory_error.py` — errors.json + learning
- `iaglobal/memory/semantic_cache.py` — Cache semântico (embeddings)
- `iaglobal/memory/fusion_engine.py` — Web + Memory Fusion Engine
- `iaglobal/memory/term_short.py` / `term_long.py` — STM / LTM
- `iaglobal/graphs/bandit.py` — BanditPolicy ε-greedy
- `plaintext.txt` — Documentação completa do projeto
- `docs/ROADMAP.md` — Histórico de implementação
