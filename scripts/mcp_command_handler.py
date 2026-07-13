# scripts/mcp_command_handler.py
"""
Handler para o comando `opencode mcp` (integração iaglobal).
"""

import argparse
import requests
import json

MCP_URL = "http://localhost:8000/mcp"


def main():
    parser = argparse.ArgumentParser(description="Control iaglobal's MCP Server")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Comando: audit
    audit_parser = subparsers.add_parser("audit", help="Run metabolic audit")
    audit_parser.add_argument("--continuous", action="store_true", help="Run continuous audit")
    
    # Comando: status
    subparsers.add_parser("status", help="Check MCP Server status")
    
    # Comando: fix
    fix_parser = subparsers.add_parser("fix", help="Trigger autocorrection")
    fix_parser.add_argument("target", choices=["vault", "latency", "toxins", "ivm"], help="Target to fix")
    
    # Comando: tools
    subparsers.add_parser("tools", help="List available MCP tools")
    
    args = parser.parse_args()
    
    if args.command == "audit":
        run_audit(args.continuous)
    elif args.command == "status":
        check_status()
    elif args.command == "fix":
        run_fix(args.target)
    elif args.command == "tools":
        list_tools()


def run_audit(continuous: bool):
    """Executa auditoria via MCP Server."""
    if continuous:
        print("⏳ Modo contínuo: Pressione Ctrl+C para sair")
        try:
            while True:
                response = requests.get(f"{MCP_URL}/audit", auth=("iaglobal", "homeostasis"))
                if response.status_code == 200:
                    data = response.json()
                    print(f"🔍 Auditoria: Score={data.get('score', 0):.2f}")
                    print("-" * 50)
                else:
                    print(f"❌ Erro: {response.status_code}")
                
                import time
                time.sleep(10)
        except KeyboardInterrupt:
            print("✅ Modo contínuo encerrado")
    else:
        response = requests.get(f"{MCP_URL}/audit", auth=("iaglobal", "homeostasis"))
        if response.status_code == 200:
            data = response.json()
            print(f"🔍 Auditoria MCP (Score: {data.get('score', 0):.2f})")
            print("=" * 50)
            for target, finding in data.get("findings", {}).items():
                status = finding.get("status", "UNKNOWN")
                color = {
                    "OK": "\033[32m",
                    "AVISO": "\033[33m",
                    "VIOLADA": "\033[31m",
                }.get(status, "")
                reset = "\033[0m"
                print(f"{color}{target.upper()}: {status}{reset}")
                if "alert" in finding:
                    print(f"   🚨 {finding['alert']}")
            print("=" * 50)
        else:
            print(f"❌ Falha ao executar auditoria: {response.status_code}")


def check_status():
    """Verifica status do MCP Server."""
    response = requests.get(f"{MCP_URL}/health")
    if response.status_code == 200:
        status = response.json().get("status")
        metabolic = response.json().get("metabolic_health", {}).get("status", "N/A")
        print(f"✅ MCP Server: {status}")
        print(f"🌡️ Saúde metabólica: {metabolic}")
    else:
        print(f"❌ Falha ao verificar status: {response.status_code}")


def run_fix(target: str):
    """Aciona correção automática."""
    response = requests.post(
        f"{MCP_URL}/fix",
        json={"target": target},
        auth=("iaglobal", "homeostasis")
    )
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Correção aplicada: {target}")
        print(f"   {result.get('corrections', 0)} correções realizadas")
    else:
        print(f"❌ Falha ao acionar correção: {response.status_code}")


def list_tools():
    """Lista ferramentas disponíveis via MCP."""
    response = requests.post(
        f"{MCP_URL}/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1
        }
    )
    if response.status_code == 200:
        tools = response.json().get("result", {}).get("tools", [])
        print(f"🛠️ Ferramentas MCP ({len(tools)} disponíveis):")
        for tool in tools:
            print(f"- {tool.get('name')}:")
            print(f"    {tool.get('description')}")
            if "params" in tool:
                print(f"    Parâmetros: {json.dumps(tool['params'], indent=2)}")
    else:
        print(f"❌ Falha ao listar ferramentas: {response.status_code}")


if __name__ == "__main__":
    main()