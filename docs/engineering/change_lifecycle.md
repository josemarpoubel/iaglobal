# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# Change Lifecycle — Workflow de Engenharia

> **Status:** Política operacional vigente.
> **Origem:** Extraída de `AGENTS.md` (seção 6) em 2026-07-29.
> **ADR relacionada:** [`docs/adr/0005-change-lifecycle.md`](../adr/0005-change-lifecycle.md).

Durante análise de bugs — principalmente em componentes críticos (pipeline, concorrência, memória, providers, AST, etc.) — **nunca misture alterações de naturezas diferentes na mesma rodada de trabalho ou PR**.

---

## 0. Linguagem Normativa (RFC 2119)

| Termo | Significado |
|-------|-------------|
| **MUST** / **MUST NOT** | Regra obrigatória. Violação = blocker na revisão. |
| **SHOULD** / **SHOULD NOT** | Recomendação forte. Justificar desvios explicitamente. |
| **MAY** | Opcional. Preferência ou contexto. |

---

## 1. Correção (Fix)

**Objetivo:** eliminar a causa conhecida de um defeito.

**MUST:**
- alterar comportamento da aplicação de forma intencional;
- possuir teste que reproduza o defeito antes da correção e valide o conserto (ver [🧬 Testing Standards](../../AGENTS.md#-testing-standards));
- ser mínima e localizada (alterar apenas o necessário);
- atacar a causa raiz comprovada por evidências.

**Exemplos:**
- corrigir perda do `ArtifactKind` no transporte entre nós;
- impedir que o parser AST receba artefatos não-Python;
- corrigir um leak de `Semaphore` comprovado por contadores.

---

## 2. Instrumentação (Observability)

**Objetivo:** aumentar a capacidade de diagnóstico **sem alterar comportamento**.

**MUST:**
- não mudar decisões da aplicação;
- não alterar contratos públicos;
- ter custo praticamente zero em produção.

**SHOULD:**
- ser protegida por nível de log (`DEBUG`) ou flag de feature;
- ser removida (ou reduzida) após a correção ser validada, salvo se agregar observabilidade de longo prazo.

**MAY permanecer quando todas as condições forem satisfeitas:**
- produz métricas operacionais;
- auxilia diagnóstico recorrente;
- possui custo desprezível em produção;
- não altera comportamento.

**Exemplos:**
- logs estruturados com caller info;
- métricas (contadores, gauges, histograms);
- tracing de tempo por nó;
- `ProgressEvent` (start/finish/duration);
- captura de stack no timeout;
- contadores `acquire`/`release` em `Semaphore`.

---

## 3. Investigação (Investigation)

**Objetivo:** produzir **evidências** antes de modificar o sistema.

**MUST:**
- coletar dados antes de propor correção;
- reproduzir o problema (ou provar que é intermitente);
- documentar a hipótese testada e o resultado.

### Critérios de saída

Uma investigação só pode ser encerrada quando existir pelo menos um dos seguintes:

- causa raiz identificada com evidência objetiva;
- hipótese descartada por dados observados;
- teste que reproduz o problema de forma determinística;
- limitação externa documentada (ex.: dependência de provedor externo).

### Ferramentas recomendadas

- watchdog (coroutine periódica de liveness);
- `asyncio.wait_for()` com timeout agressivo;
- `asyncio.all_tasks()` + `task.get_stack()` no momento do hang;
- monitor de progresso com falha por estagnação;
- snapshots de estado (semáforos, filas, últimas transições);
- APIs públicas de `asyncio.Task` (`done()`, `cancelled()`, `get_coro()`).

---

### 3.1 Evidência Mínima

**MUST:** uma hipótese **NÃO** é evidência.

Toda correção MUST ser sustentada por pelo menos uma das seguintes formas de evidência objetiva:

- teste que reproduz o defeito de forma determinística;
- stack trace capturado no momento da falha;
- logs instrumentados com timestamps e caller info;
- métricas quantitativas (contadores, gauges, histograms);
- profiler (cProfile, py-spy, `time.monotonic()`);
- inspeção direta e comprovável do código-fonte relevante.

Hipóteses que não foram convertidas em evidência por nenhum dos meios acima MUST ser descartadas ou convertidas em nova investigação antes de qualquer correção.

---

### 3.2 Respeito ao Trabalho em Curso

Toda investigação MUST respeitar a **Regra 0** ([MCS — MCP Coordenation & Anti-Revert](../../AGENTS.md#-mcs--mcp-coordenation--anti-revert)): a instrumentação necessária para diagnosticar um problema NÃO deve remover, sobrescrever ou modificar alterações em andamento de outro agente. Antes de qualquer operação destrutiva (`git restore`, `git checkout --`, `git reset`), verificar `git status -s` e `git log -1`.

---

## 4. Refatoração (Refactoring)

**Objetivo:** melhorar arquitetura ou reduzir dívida técnica **sem alterar comportamento observável**.

**MUST:**
- preservar todos os testes existentes (ver [🧬 Testing Standards](../../AGENTS.md#-testing-standards));
- manter contratos públicos;
- não introduzir novas dependências externas sem justificativa.

**Exemplos:**
- extrair lógica duplicada em helper compartilhado;
- renomear símbolo público após consolidação de terminologia;
- reorganizar camadas internas (ex.: mover detector de `_is_python_code` para um único helper reutilizado por múltiplos callers).

**Atenção:** Refatoração é frequentemente confundida com Correção. A diferença é que **refatoração não muda comportamento** — se o comportamento muda, é Correção, não Refatoração.

---

## 5. Regra Obrigatória

**MUST NOT:** implementar uma correção baseada apenas em hipótese.

Sequência obrigatória:

```
Investigação
    ↓
Evidências
    ↓
Correção mínima
    ↓
Validação
    ↓
Remoção (ou redução) da instrumentação temporária
```

Instrumentação permanente somente quando agregar observabilidade de longo prazo.

---

### 5.1 Classificação de Alterações

**MUST:** toda alteração MUST ser classificada em exatamente uma categoria principal:

1. **Investigação** — produz evidência antes de qualquer mudança comportamental
2. **Instrumentação** — adiciona observabilidade sem alterar comportamento
3. **Correção** — altera comportamento para eliminar defeito comprovado
4. **Refatoração** — reorganiza estrutura sem alterar comportamento observável

**SHOULD:** se uma alteração envolver múltiplas categorias, elas SHOULD ser divididas em commits distintos para facilitar revisão e `git bisect`.

Exemplo de sequência ideal:

```
Commit 1: Instrumentação (watchdog + timeline START/END)
Commit 2: Investigação (relatório do hang com stack traces)
Commit 3: Correção (fix do leak de Semaphore)
Commit 4: Remoção da instrumentação temporária
```

---

## 6. Proibição de "Band-aids"

Não são aceitas alterações que apenas escondem sintomas.

**MUST NOT:**
- retornar `valid=True` para evitar um erro;
- adicionar `sleep()` para "resolver" concorrência;
- aumentar timeout sem identificar o motivo;
- adicionar retries para mascarar deadlocks;
- capturar `Exception` sem registrar a causa raiz;
- silenciar `logger.error` em `logger.debug` para "limpar o log";
- cancelar `Task`s silenciosamente sem diagnóstico (especialmente em sistemas assíncronos);
- envolver chamadas assíncronas em `try/except Exception` apenas para permitir a continuação da pipeline.

**Toda alteração deve atacar a causa raiz comprovada por evidências.**

---

## 7. Checklist de Revisão

Use esta tabela durante code review para validar a classificação da PR:

| Categoria       | Pergunta de revisão                                                     |
| --------------- | ----------------------------------------------------------------------- |
| Investigação    | Produziu evidência objetiva documentada no PR ou issue?                  |
| Instrumentação  | Altera comportamento ou contrato público?                               |
| Instrumentação  | Está protegida por nível de log (`DEBUG`) ou flag de feature?           |
| Correção        | Há teste de regressão que reproduz o defeito ANTES da correção?         |
| Correção        | Foi baseada em hipótese ou em evidência?                                |
| Refatoração     | Todos os testes existentes continuam passando?                           |
| Refatoração     | Algum teste falhou como efeito colateral da mudança?                    |
| Qualquer        | A alteração está classificada em exatamente uma categoria principal?   |
| Qualquer        | Respeita a **Regra 0** (não reverte trabalho alheio em curso)?          |

Se qualquer resposta for **"não"** ou **"incerto"**, a PR MUST voltar para revisão antes de merge.
