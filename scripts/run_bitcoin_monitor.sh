#!/bin/bash
# Bitcoin Monitor 24h - Launcher
# Executa o monitor em background com log dedicado

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/iaglobal/memory/data/logs/bitcoin_monitor.log"

echo "🚀 Iniciando Bitcoin Monitor de 24 horas..."
echo "📊 Logs em: $LOG_FILE"
echo "📄 Output em: $PROJECT_DIR/docs/temp.md"
echo ""
echo "⏰ Data de início: $(date)"
echo "⏰ Data de término prevista: $(date -d '+24 hours' 2>/dev/null || date -v+24H 2>/dev/null || echo 'calcular manualmente')"
echo ""
echo "🔍 Para acompanhar em tempo real:"
echo "   tail -f $LOG_FILE"
echo ""
echo "📊 Para ver o documento atualizado:"
echo "   cat $PROJECT_DIR/docs/temp.md"
echo ""
echo "🛑 Para interromper:"
echo "   kill \$(pgrep -f bitcoin_monitor_24h.py)"
echo ""
echo "Iniciando agora..."
echo ""

cd "$PROJECT_DIR"
source venv/bin/activate 2>/dev/null || true

# Executa em background
nohup python3 "$SCRIPT_DIR/bitcoin_monitor_24h.py" > "$LOG_FILE" 2>&1 &

PID=$!
echo "✅ Processo iniciado com PID: $PID"
echo ""
echo "📈 Aguardando primeira coleta (~1-2 minutos)..."
sleep 5

if ps -p $PID > /dev/null; then
    echo "✅ Monitor rodando com sucesso!"
    echo ""
    echo "🔍 Acompanhar logs:"
    echo "   tail -f $LOG_FILE"
else
    echo "❌ Falha ao iniciar. Verifique os logs:"
    echo "   cat $LOG_FILE"
    exit 1
fi