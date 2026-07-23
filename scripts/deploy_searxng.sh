#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# SearXNG — Teste de conectividade com instância pública
# ═══════════════════════════════════════════════════════════════

BASE_URL="${SEARXNG_URL:-https://paulgo.io}"
echo "🔍 Testando SearXNG em $BASE_URL ..."

if curl -s "$BASE_URL/search?q=test&format=json" > /dev/null 2>&1; then
    echo "✅ SearXNG respondendo em $BASE_URL"
else
    echo "⚠️  $BASE_URL não respondeu. Verifique SEARXNG_URL no .env"
    echo "   curl -s \"\$SEARXNG_URL/search?q=test&format=json\""
fi
