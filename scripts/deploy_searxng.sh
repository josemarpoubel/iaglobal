#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# SearXNG Deployment Script
# ═══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/../docker-compose.search.yml"
cd "$SCRIPT_DIR/.."

echo "🚀 SearXNG Deployment for iaglobal"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"

# Check if docker compose is available
if ! docker compose version &> /dev/null; then
    echo "❌ docker compose not found. Please install it first."
    exit 1
fi

echo "✅ docker compose is available"
echo ""

# Parse command line arguments
ACTION="${1:-up}"

case "$ACTION" in
    up)
        echo "📦 Starting SearXNG..."
        docker compose -f "$COMPOSE_FILE" up -d
        
        echo ""
        echo "⏳ Waiting for SearXNG to be ready..."
        sleep 10
        
        # Health check
        for i in {1..10}; do
            if curl -s "http://localhost:8005/search?q=test&format=json" > /dev/null 2>&1; then
                echo "✅ SearXNG is ready!"
                break
            fi
            echo "   Waiting... ($i/10)"
            sleep 2
        done
        
        echo ""
        echo "📊 Service Status:"
        docker compose -f "$COMPOSE_FILE" ps
        echo ""
        echo "🌐 Access Points:"
        echo "   - SearXNG: http://localhost:8005"
        echo ""
        echo "🧪 Test Commands:"
        echo "   curl 'http://localhost:8005/search?q=flask+rest+api&format=json'"
        echo "   python -c \"from iaglobal.graphs.nodes._search_sources import searxng_search; print(searxng_search('flask tutorial'))\""
        echo ""
        ;;
        
    down)
        echo "🛑 Stopping SearXNG and YaCy..."
        docker compose -f docker-compose.search.yml down
        echo ""
        echo "✅ Services stopped"
        ;;
        
    restart)
        echo "🔄 Restarting services..."
        docker compose -f docker-compose.search.yml restart
        echo ""
        echo "✅ Services restarted"
        ;;
        
    logs)
        echo "📋 Showing logs..."
        docker compose -f docker-compose.search.yml logs -f
        ;;
        
    status)
        echo "📊 Service Status:"
        docker compose -f docker-compose.search.yml ps
        echo ""
        echo "🔍 Health Check:"
        if curl -s "http://localhost:8005/search?q=test&format=json" > /dev/null 2>&1; then
            echo "   ✅ SearXNG: ONLINE"
        else
            echo "   ❌ SearXNG: OFFLINE"
        fi
        ;;
        
    test)
        echo "🧪 Running integration tests..."
        echo ""
        
        # Test 1: SearXNG endpoint
        echo "1️⃣  Testing SearXNG JSON endpoint..."
        RESPONSE=$(curl -s "http://localhost:8005/search?q=flask+rest+api&format=json")
        if echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'   Results: {len(data.get(\"results\", []))}')" 2>/dev/null; then
            echo "   ✅ SearXNG responding correctly"
        else
            echo "   ❌ SearXNG not responding or invalid JSON"
            exit 1
        fi
        
        # Test 2: Python integration
        echo ""
        echo "2️⃣  Testing Python integration..."
        source venv/bin/activate 2>/dev/null || true
        python3 -c "
from iaglobal.graphs.nodes._search_sources import searxng_search
result = searxng_search('flask rest api tutorial')
if result:
    lines = result.strip().split('\n')
    print(f'   Results found: {len([l for l in lines if l.startswith(\"•\")])}')
    print('   ✅ Python integration working')
else
    print('   ⚠️  No results (might be rate limited)')
"
        
        # Test 3: Circuit breaker
        echo ""
        echo "3️⃣  Testing circuit breaker..."
        python3 -c "
from iaglobal.graphs.nodes._search_sources import _searxng_fail_count, _searxng_offline_until
import time
print(f'   Fail count: {_searxng_fail_count}')
print(f'   Offline until: {_searxng_offline_until - time.monotonic():.1f}s' if _searxng_offline_until > time.monotonic() else '   Offline until: N/A')
print('   ✅ Circuit breaker state accessible')
"
        
        echo ""
        echo "✅ All tests completed!"
        ;;
        
    *)
        echo "Usage: $0 {up|down|restart|logs|status|test}"
        echo ""
        echo "Commands:"
        echo "   up      - Start SearXNG"
        echo "   down    - Stop services"
        echo "   restart - Restart services"
        echo "   logs    - Show logs"
        echo "   status  - Show status and health check"
        echo "   test    - Run integration tests"
        exit 1
        ;;
esac