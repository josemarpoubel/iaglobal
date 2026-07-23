# SearXNG — Container Local

O iaglobal usa SearXNG como meta-buscador web, rodando em container Docker local.

**URL padrão:** `http://localhost:8005`

## Subir o container

```bash
docker compose -f docker-compose.search.yml up -d
```

## Parar o container

```bash
docker compose -f docker-compose.search.yml down
```

## Logs

```bash
docker compose -f docker-compose.search.yml logs -f
```

## Configurar

Edite `searxng/settings.yml` para adicionar/remover engines de busca.

## Testar conectividade

```bash
curl -s "http://localhost:8005/search?q=flask+rest+api&format=json"
```

## Como funciona

A função `searxng_search()` em `iaglobal/graphs/nodes/_search_sources.py` faz a busca. Ela inclui um circuit breaker: após 3 falhas consecutivas, espera 300s antes de tentar novamente.
