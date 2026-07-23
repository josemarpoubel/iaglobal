# SearXNG — Instância Pública

O iaglobal usa uma instância pública do SearXNG como meta-buscador web.

**Default:** `https://paulgo.io`

Configure via `SEARXNG_URL` no `.env`:

```bash
export SEARXNG_URL=https://paulgo.io
```

### Testar conectividade

```bash
curl -s "$SEARXNG_URL/search?q=flask+rest+api&format=json"
```

### Como funciona

A função `searxng_search()` em `iaglobal/graphs/nodes/_search_sources.py` faz a busca. Ela inclui um circuit breaker: após 3 falhas consecutivas, espera 300s antes de tentar novamente.

Não é necessário gerenciar containers localmente.
