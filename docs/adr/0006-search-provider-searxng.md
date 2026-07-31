# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# ADR 0006 — Search Provider: SearXNG integrado ao pipeline de busca

- **Status**: Aceita
- **Data**: 2026-07-31

## Contexto

O SearXNG estava **configurado** (`ProviderConfig.SEARXNG_URL`, default
`http://localhost:8005`) e **inicializado** pelo CLI (`cli/main.py:60
_ensure_searxng`, que levanta o container Docker), mas **não participava do
pipeline de busca**. O nó `no_search.py` usava DuckDuckGo, Playwright, Bing,
YaCy e o router especializado; `searxng_search()` (`_search_sources.py:485`)
só era referenciado num bloco morto `if False:` do `_search_router.py`
(`L411-423`).

Resultado: infraestrutura paga (meta-buscador local agregando Google+Bing+DDG)
ociosa, e o rótulo `source="searxng"` em `evo_agent.py` enganoso — a busca era
feita via `SearchMiddleware` (DDG), não SearXNG.

## Decisão

Integrar o SearXNG como **fonte de busca de primeira classe**, em dois pontos:

1. **`no_search.py` — fonte ativa em `SOURCES`**: `("searxng",
   _search_sources_mod.searxng_search, 15)` após `ddg_text`. Referência via
   atributo do módulo (`_search_sources_mod.searxng_search`) para permitir
   interceptação determinística em testes (`mock.patch.object(_search_sources,
   "searxng_search")`).

2. **`_search_router.py` — fallback de conhecimento geral**: queries sem
   categoria especializada (`classify_task` retorna `[]`) caem em
   `_general_knowledge_search(task)` → `searxng_search()` via
   `asyncio.to_thread`. Removidos os dois blocos mortos `if False:`.

### Salvaguardas mantidas

- **Circuit breaker próprio** do `searxng_search` (TTL progressivo 60s→300s):
  quando offline, retorna `""` sem tocar rede — sem thundering herd nem
  latência no pipeline. Falha de conexão (refused) é instantânea; timeout
  interno de 15s limita o caso de instância pendurada.
- **Paralelismo**: `no_search` continua rodando DDG/Playwright/Bing em
  paralelo; o SearXNG é uma fonte a mais, não um gargalo.
- **Formato de saída normalizado**: `"• title [engine]\n  url\n  content[:200]"`
  com header canônico `=== SEARXNG ===` no agregado do router — idêntico ao
  padrão das demais fontes (`=== {name.upper()} ===`). Consumidores usam
  `SOURCE_RE` (`search_code_extractor.py:34`), que já reconhece qualquer
  seção nesse formato; nenhum consumidor espera a string crua do fallback.

### Observabilidade

A origem do resultado é identificável em três níveis:

1. **Agregado** — seção `=== SEARXNG ===` no payload consolidado.
2. **Logs** — `[SEARXNG] Busca OK: N resultados para '...'` (sucesso) e
   `[SEARXNG] Offline (falha #N): ... Pulando por Xs` (circuit breaker).
3. **Nó** — `[SEARCH] Fonte 'searxng' OK: N caracteres extraídos.`

### O que NÃO mudou (fora de escopo)

- `SearchMiddleware` (DDG) segue como está; o rótulo `source="searxng"` em
  `evo_agent.py` permanece uma dívida de observabilidade (correção futura).
- A abstração `SearchProvider(Protocol)` foi **descartada nesta rodada**: a
  integração mínima (fonte em `SOURCES` + fallback no router) atinge o objetivo
  sem introduzir camada nova sobre o formato string já consolidado. Pode ser
  revisitada quando mais provedores entrarem.

## Consequências

### Positivas

- Infraestrutura SearXNG finalmente alimenta o pipeline com evidência web.
- Busca de conhecimento geral ganha um meta-buscador local (privacidade +
  agregação Google/Bing/DDG) com custo zero por chamada.
- Dois xfail comportamentais viraram testes positivos em `test_searxng_state.py`
  (10 + 3 = 13 testes passando).
- Código morto removido (`if False:` em `_search_router.py`) — menos ruído
  para o auditor arquitetural.

### Negativas / Custos

- Uma chamada adicional de rede por busca quando o SearXNG está no ar (15s de
  timeout interno, 3s após falha).
- `searxng_search` continua **síncrono** (urllib) — depende de
  `asyncio.to_thread` para não bloquear o loop. Refatoração para async é uma
  evolução futura.

## Referências

- `iaglobal/graphs/nodes/_search_sources.py` — `searxng_search` (L485),
  circuit breaker (`_searxng_offline_until`/`_searxng_fail_count`).
- `iaglobal/graphs/nodes/no_search.py` — `SOURCES`, `run_search`.
- `iaglobal/graphs/nodes/_search_router.py` — `run_search_router`,
  `_general_knowledge_search`.
- `iaglobal/tests/test_searxng_state.py` — cobertura de integração.
- ADR 0005 — Change Lifecycle (categoria: **Correção** — altera comportamento
  para eliminar o defeito comprovado de SearXNG ocioso).
