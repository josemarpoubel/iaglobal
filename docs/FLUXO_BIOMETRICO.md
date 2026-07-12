================================================================================
                        🧬 INICIO DO FLUXO BIOMIMÉTICO
================================================================================

# 🧬 Arquitetura da Pipeline iaglobal

```
================================================================================
                    📥 FASE 0 — INPUT DO USUÁRIO
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│  USER PROMPT                                                                │
│  "Criar um componente 'HealthDashboard.jsx' que exibe o status de 3         │
│   agentes (Planner, Coder, Critic) usando Framer Motion para transições."   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
================================================================================
                    🧠 FASE 1 — COGNIÇÃO INICIAL
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│  PROMPT_INTAKE (Captura e Validação Inicial)                                │
│  ├── Valida schema do prompt                                                │
│  ├── Extrai metadados (tipo, complexidade, domínio)                         │
│  └── Gera hash único da tarefa                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PROMPT_IMPROVER (Melhorador de Prompt) ⭐ PRIMEIRO AGENTE INTELIGENTE      │
│  ├── Adiciona contexto técnico (React, Tailwind, Framer Motion)             │
│  ├── Inclui restrições (WCAG 2.1, mobile-first, performance)                │
│  ├── Adiciona exemplos de formato de saída                                  │
│  ├── Aplica Chain-of-Thought (CoT)                                          │
│  └── Enriquece de 136 chars → 2318 chars                                    │
│                                                                             │
│  SAÍDA: "Criar HealthDashboard.jsx com:                                     │
│          - React 18+ com hooks                                              │
│          - Framer Motion para animações de entrada                          │
│          - Tailwind CSS para estilização                                    │
│          - Props: agents (array com status de Planner, Coder, Critic)       │
│          - Responsivo: @media (max-width: 768px)                            │
│          - Acessibilidade: aria-labels, keyboard navigation                 │
│          - Export: default function HealthDashboard..."                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
================================================================================
                    📋 FASE 2 — PLANEJAMENTO ESTRATÉGICO
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│  PLANNER (Planejador de Tarefas) ⭐ USA PROMPT JÁ MELHORADO                 │
│  ├── Analisa prompt enriquecido                                             │
│  ├── Identifica subtarefas necessárias                                      │
│  ├── Estima complexidade (baixa/média/alta)                                 │
│  ├── Define ordem de execução (sequencial vs paralelo)                      │
│  └── Atribui prioridades e deadlines                                        │
│                                                                             │
│  SAÍDA (Plano de Execução):                                                 │
│  {                                                                          │
│    "task": "HealthDashboard.jsx",                                           │
│    "steps": [                                                               │
│      {"id": 1, "action": "search", "target": "Framer Motion examples"},     │
│      {"id": 2, "action": "design", "target": "Component structure"},        │
│      {"id": 3, "action": "code", "target": "Generate JSX"},                 │
│      {"id": 4, "action": "test", "target": "Unit tests"},                   │
│      {"id": 5, "action": "validate", "target": "LSP + a11y check"}          │
│    ],                                                                       │
│    "requires_web_search": true,                                             │
│    "estimated_complexity": "medium"                                         │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  TASK_BREAKDOWN (Quebra em Micro-Tarefas)                                   │
│  ├── Divide cada step em ações atômicas                                     │
│  └── Gera IDs únicos para rastreamento                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXECUTION_PLAN (Plano de Execução Detalhado)                               │
│  ├── Ordena tarefas por dependência                                         │
│  ├── Identifica oportunidades de paralelismo                                │
│  └── Prepara contexto para cada agente                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
================================================================================
                    🔍 FASE 3 — COLETA DE DADOS (RAG)
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│  SEARCH + LOCAL_KNOWLEDGE (Coleta Paralela)                                 │
│  ├── Web Search (DuckDuckGo): Framer Motion dashboard examples              │
│  ├── Local Knowledge (Obsidian): Componentes reutilizáveis                  │
│  └── Memory Vector: Embeddings de tarefas similares                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SOURCE_VALIDATOR (Validação de Credibilidade) ⭐ FILTRO IMUNOLÓGICO        │
│  ├── Score de domínio (arxiv.org=0.95, medium.com=0.60)                     │
│  ├── Score de recência (<30 dias=1.0, >3 anos=0.4)                          │
│  ├── Score de consistência (concorda com outras fontes?)                    │
│  └── Filtra: score < 0.6 → DESCARTA                                         │
│                                                                             │
│  SAÍDA: Apenas fontes confiáveis (score >= 0.6)                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SNIPPET_SYNTHESIZER (Opcional, se habilitado)                              │
│  ├── Resume múltiplos snippets em 1 parágrafo coerente                      │
│  ├── Detecta contradições entre fontes                                      │
│  └── Gera síntese com 50% menos tokens                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
================================================================================
                    🏗️ FASE 4 — CONSTRUÇÃO (BUILDERS)
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND_BUILDER / BACKEND_BUILDER / API_BUILDER                           │
│  ├── Recebe: prompt melhorado + plano + dados validados                     │
│  ├── Usa CoderAgent com contexto enriquecido                                │
│  ├── Gera código JSX/TS/Python                                              │
│  └── Publica no AcetylcholineBus para próximo nó                            │
│                                                                             │
│  ⚠️ NOTA: NÃO chama BanditPolicy diretamente!                               │
│     Usa modelos padrão (qwen2.5:0.5b) como fallback                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LSP_VALIDATOR (Validação Sintática)                                        │
│  ├── Verifica erros de sintaxe                                              │
│  ├── Verifica imports ausentes                                              │
│  └── Se erro → DEBUG_UNIFICADO corrige                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DEBUG_UNIFICADO (Correção de Erros)                                        │
│  ├── Analisa erro do LSP                                                    │
│  ├── Aplica correção direta (se simples)                                    │
│  └── Solicita LLM (se complexo)                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FIX_VALIDATOR (Valida Correção)                                            │
│  └── Confirma que erro foi resolvido                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
================================================================================
                    🧪 FASE 5 — TESTES E REVISÃO
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│  TESTER (Geração de Testes)                                                 │
│  ├── Gera testes unitários (pytest/Jest)                                    │
│  ├── Cobre happy path + edge cases                                          │
│  └── Isola dependências com mocks                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  REVIEWER (Revisão de Código)                                               │
│  ├── Verifica best practices                                                │
│  ├── Aplica linting (ESLint, Pylint)                                        │
│  └── Sugere otimizações                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
================================================================================
                    ⚖️ FASE 6 — APROVAÇÃO CRÍTICA (GATE)
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│  CRITIC ⭐ APPROVAL GATE (Ponto de Decisão Crítico)                         │
│  ├── Avalia código gerado (score 0-100)                                     │
│  ├── Critérios:                                                             │
│  │   ├── Funcionalidade: atende ao prompt?                                  │
│  │   ├── Qualidade: segue best practices?                                   │
│  │   ├── Testes: cobertura >= 80%?                                          │
│  │   ├── Performance: sem bottlenecks?                                      │
│  │   └── Segurança: sem vulnerabilidades?                                   │
│  │                                                                          │
│  ├── DECISÃO:                                                               │
│  │   ├── Score >= 80: ✅ APROVA → vai para BANDIT_POLICY                    │
│  │   └── Score < 80:  ❌ REPROVA → RETRY LOOP                               │
│  │                └─→ Volta para FRONTEND_BUILDER (com feedback)            │
│  │                    (máximo 3 retries antes de falha crítica)             │
│  └── Publica decisão no AcetylcholineBus                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
              (Score >= 80)                   (Score < 80)
                    │                               │
                    ▼                               │
================================================================================              
                    🎯 FASE 7 — SELEÇÃO DE MODELO                                                   
================================================================================              
                                                                                              
┌─────────────────────────────────────────────────────────────────────────────┐ 
│  BANDIT_POLICY ⭐ ÚNICO PONTO DE SELEÇÃO DE MODELO                          │
│  ├── Recebe: prompt + contexto + score do Critic                            │
│  ├── Analisa providers disponíveis (ollama, groq, nvidia, openrouter)       │
│  ├── Calcula IVM (Índice de Viabilidade Metabólica):                        │
│  │   IVM = (P × 0.4) + (E × 0.4) + (C × 0.2)                                │
│  │   P = Produtividade (taxa de sucesso)                                    │
│  │   E = Eficiência (1/latência)                                            │
│  │   C = Cooperação (skills trocadas)                                       │
│  ├── Seleciona modelo ótimo:                                                │
│  │   ├── Tarefas simples: qwen2.5:0.5b (local, grátis)                      │
│  │   ├── Tarefas complexas: groq-llama-3.1-70b (rápido)                     │
│  │   └── Tarefas críticas: o1-preview (raciocínio)                          │
│  └── Retorna: provider + modelo selecionados                                │
└─────────────────────────────────────────────────────────────────────────────┘                 │
                                    │                                                           │
                                    ▼                                                           │
================================================================================                │
                    📦 FASE 8 — PERSISTÊNCIA                                                    │
================================================================================                │
                                                                                                │
┌─────────────────────────────────────────────────────────────────────────────┐                 │
│  ARTIFACT_WRITER (Persiste Resultado)                                       │                 │
│  ├── Detecta tipo de artefato (.jsx, .py, .md)                              │                 │
│  ├── Salva em: iaglobal/memory/data/result/                                 │                 │
│  └── Gera metadata (autor, timestamp, task_hash)                            │                 │
└─────────────────────────────────────────────────────────────────────────────┘                 │
                                    │                                                           │
                                    ▼                                                           │
┌─────────────────────────────────────────────────────────────────────────────┐                 │
│  RESULT_AGENT (Consolida Resultado Final)                                   │                 │
│  ├── Agrega todos os artefatos                                              │                 │
│  ├── Gera summary executivo                                                 │                 │
│  └── Prepara para memória de longo prazo                                    │                 │
└─────────────────────────────────────────────────────────────────────────────┘                 │
                                    │                                                           │
                                    ▼                                                           │
================================================================================                │
                    🧠 FASE 9 — MEMÓRIA E APRENDIZADO            │                              │
================================================================================                │
                                                                                                │
┌─────────────────────────────────────────────────────────────────────────────┐                 │
│  RETROSPECTIVE (Análise Pós-Execução)                                       │                 │
│  ├── O que funcionou bem?                                                   │                 │
│  ├── O que falhou?                                                          │                 │
│  └── Lições aprendidas                                                      │                 │
└─────────────────────────────────────────────────────────────────────────────┘                 │
                                                                                                │
                    ┌──────────────────────────────────────────┐                                │
                    │                                          │                                │
              (Sucesso)                                (Falha após 3 retries)                   │
                    │                                          │                                │
                    ▼                                          ▼                                │
┌────────────────────────────────────────────────────┐   ┌────────────────────────────────────┐ │
│  REFLEXION (Commit de Aprendizado)                 │   │  REFLEXION (Análise de Falha)      │ │
│  ├── Salva no Obsidian:                            │   │  ├── Identifica causa raiz         │ │
│  │   - O que funcionou                             │   │  ├── Atualiza padrões de falha     │ │
│  │   - Padrões de sucesso                          │   │  ├── Ajusta thresholds             │ │
│  │   - Metrics de performance                      │   │  └── Gera insight para futuro      │ │
│  └── Atualiza CreditAssignmentEngine               │   └── Atualiza CreditAssignmentEngine  │ │
└────────────────────────────────────────────────────┘   └────────────────────────────────────┘ │
                    │                                          │                                │
                    └──────────────────┬───────────────────────┘                                │
                                       │                                                        │
                                       ▼                                                        │
┌─────────────────────────────────────────────────────────────────────────────┐                 │
│  MEMORY_WRITER (Persiste em Longo Prazo)                                    │                 │
│  ├── Salva em Obsidian (04_Synapses/)                                       │                 │
│  ├── Atualiza MemoryVector (embeddings)                                     │                 │
│  └── Indexa para busca futura                                               │                 │
└─────────────────────────────────────────────────────────────────────────────┘                 │
                                    │                                                           │
                                    ▼                                                           │
================================================================================                │
                    ✅ FASE 10 — ENTREGA FINAL                                                  │
================================================================================                │
                                                                                                │
┌─────────────────────────────────────────────────────────────────────────────┐                 │
│  MEMORY_CLEANER (Limpeza de Cache)                                          │                 │
│  ├── Remove cache expirado (>5min)                                          │                 │
│  └── Libera memória RAM                                                     │                 │
└─────────────────────────────────────────────────────────────────────────────┘                 │
                                    │                                                           │
                                    ▼                                                           │
┌─────────────────────────────────────────────────────────────────────────────┐                 │
│  METRICS (Coleta de Métricas Finais)                                        │                 │
│  ├── Latência total                                                         │                 │
│  ├── Custo total (tokens × preço)                                           │                 │
│  ├── IVM final do pipeline                                                  │                 │
│  └── Sucesso/Falha                                                          │                 │
└─────────────────────────────────────────────────────────────────────────────┘                 │
                                    │                                                           │
                                    ▼                                                           │
┌─────────────────────────────────────────────────────────────────────────────┐                 │
│  OUTPUT PARA USUÁRIO                                                        │                 │
│  ├── Artefato gerado: HealthDashboard.jsx                                   │                 │
│  ├── Tests: test_HealthDashboard.jsx                                        │                 │
│  ├── Summary: 2318 chars → 150 chars (resumo)                               │                 │
│  └── Caminho: /home/kitohamachi/projeto-iaglobal/iaglobal/memory/data/      │                 │
│                result/Criar_um_componente__HealthDashboard_jsx__*.md        │                 │
└─────────────────────────────────────────────────────────────────────────────┘                 │
                                                                                                │
                                    FIM DO FLUXO                                                │
                                                                                                │
=================================================================================================
```

## 🔄 LOOP DE RETRY (metodo de reprovação do Critic)

```
┌─────────────────────────────────────────────────────────────┐
│  CRITIC: Score = 65 (< 80) → REPROVADO                      │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  FEEDBACK PARA FRONTEND_BUILDER:                            │
│  - "Adicionar aria-labels para acessibilidade"              │
│  - "Incluir tratamento de erro no useEffect"                │
│  - "Otimizar re-renders com React.memo"                     │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND_BUILDER: Re-gera código com feedback              │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  TESTER + REVIEWER + CRITIC: Re-avalia                      │
│  - Score = 85 → ✅ APROVADO                                 │
│  - Score = 70 → ❌ REPROVADO (retry 2/3)                    │
│  - Score = 50 → ❌ REPROVADO (retry 3/3) → FALHA CRÍTICA    │
└─────────────────────────────────────────────────────────────┘
```

## 📊 MÉTRICAS DO FLUXO

```
| Fase | Agente Principal | Latência Esperada | ATP (Custo)      |
|------|------------------|-------------------|------------------|
| 0    | User             | -                 | 0                |
| 1    | Prompt Improver  | 1-2s              | 50 tokens        |
| 2    | Planner          | 2-3s              | 100 tokens       |
| 3    | Search           | 3-5s              | 0 (duckduckgo)   |
| 4    | Frontend Builder | 5-10s             | 500 tokens       |
| 5    | Tester           | 3-5s              | 300 tokens       |
| 6    | Critic           | 2-3s              | 200 tokens       |
| 7    | Bandit Policy    | <1s               | 0 (local)        |
| 8    | Artifact Writer  | <1s               | 0                |
| 9    | Reflexion        | 2-3s              | 100 tokens       |
| 10   | Metrics          | <1s               | 0                |
| **TOTAL** |             | **19-33s**        | **~1250 tokens** |
```

## 🧬 PRINCÍPIOS BIOMIMÉTICOS APLICADOS

```
| Processo Biológico      |         Equivalente Computacional       |
|-------------------------|-----------------------------------------|
| **Metilação**           | Prompt Improver (enriquece input bruto) |
| **Tradução**            | Planner → Execution Plan                |
| **Homeostase**          | Source Validator (filtra toxinas)       |
| **Sistema Imunológico** | Critic (detecta anomalias)              |
| **Apoptose**            | Retry Loop (elimina código ruim)        |
| **Memória Imunológica** | Obsidian + MemoryVector                 |
| **Metabolismo**         | IVM (otimiza ATP/token)                 |
| **Evolução**            | Reflexion (aprendizado contínuo)        |
```
================================================================================
                        🧬 FIM DO FLUXO BIOMIMÉTICO
================================================================================
