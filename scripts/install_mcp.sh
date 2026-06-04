#!/bin/bash
# Instala o MCP Server do iaglobal no opencode.json

set -e

IAGLOBAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ "$1" == "--global" ]; then
    CONFIG_DIR="$HOME/.config/opencode"
else
    CONFIG_DIR="$IAGLOBAL_DIR"
fi

CONFIG_FILE="$CONFIG_DIR/opencode.json"
mkdir -p "$CONFIG_DIR"

if [ -f "$CONFIG_FILE" ]; then
    if grep -q '"iaglobal"' "$CONFIG_FILE" 2>/dev/null; then
        echo "ℹ️  MCP server 'iaglobal' ja registrado em $CONFIG_FILE"
        exit 0
    fi
    python3 << 'PYEOF'
import json
cfg_file = "$HOME/.config/opencode/opencode.json"
with open(cfg_file) as f:
    cfg = json.load(f)
if 'mcp' not in cfg:
    cfg['mcp'] = {}
cfg['mcp']['iaglobal'] = {
    "type": "local",
    "command": ["python", "-m", "iaglobal.api.mcp_server"],
    "enabled": True,
    "timeout": 300000
}
with open(cfg_file, 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
print("✅ iaglobal adicionado ao MCP em " + cfg_file)
PYEOF
else
    cat > "$CONFIG_FILE" << 'EOF'
{
  "mcp": {
    "iaglobal": {
      "type": "local",
      "command": ["python", "-m", "iaglobal.api.mcp_server"],
      "enabled": true,
      "timeout": 300000
    }
  }
}
EOF
    echo "✅ opencode.json criado em $CONFIG_FILE"
fi

echo ""
echo "🔧 Agora adicione ao seu AGENTS.md:"
echo ""
echo "   When the user asks to generate code, create a blockchain,"
echo "   or run software engineering tasks, use the iaglobal MCP server."
echo "   Available tools: run_task, get_status, get_insights, list_scripts"
echo ""
