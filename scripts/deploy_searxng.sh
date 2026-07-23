#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# SearXNG — Deploy e teste do container local
# ═══════════════════════════════════════════════════════════════

BASE_URL="http://localhost:8005"
COMPOSE_FILE="docker-compose.search.yml"

echo "🔍 Verificando SearXNG em $BASE_URL ..."

if curl -s "$BASE_URL/search?q=test&format=json" > /dev/null 2>&1; then
    echo "✅ SearXNG já está rodando em $BASE_URL"
    exit 0
fi

echo "🚀 Iniciando container SearXNG..."
docker compose -f "$COMPOSE_FILE" up -d

echo "⏳ Aguardando 15s para o SearXNG iniciar..."
sleep 15

if curl -s "$BASE_URL/search?q=test&format=json" > /dev/null 2>&1; then
    echo "✅ SearXNG iniciado com sucesso em $BASE_URL"
else
    echo "⚠️  SearXNG não respondeu. Verifique os logs:"
    echo "   docker compose -f $COMPOSE_FILE logs"
fi
