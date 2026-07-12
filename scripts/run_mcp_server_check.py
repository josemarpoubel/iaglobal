"""
Teste de sanidade do MCP server iaglobal.
Verifica se o servidor está vivo e se o protocolo MCP está respondendo.
"""
import json
import subprocess
import sys
import time
from contextlib import contextmanager

MCP_CMD = [sys.executable, "-m", "iaglobal.api.mcp_server"]


def _check_process_alive() -> bool:
    """
    Verifica se o processo do MCP server está rodando.
    
    Returns:
        True se o processo está ativo no sistema, False caso contrário.
    """
    try:
        result = subprocess.run(["pgrep", "-f", "iaglobal.api.mcp_server"],
                                capture_output=True, text=True, timeout=5)
        alive = result.returncode == 0 and bool(result.stdout.strip())
        print(f"[TEST] Processo MCP ativo: {alive}")
        return alive
    except Exception as e:
        print(f"[TEST] Erro ao verificar processo MCP: {e}")
        return False


@contextmanager
def _mcp_session(timeout: float = 5.0):
    """
    Context manager para uma sessão MCP via stdio.
    
    Args:
        timeout: Tempo máximo de espera por resposta em segundos.
        
    Yields:
        Processo MCP e helper de comunicação.
    """
    import select
    
    try:
        # Inicia o servidor MCP como subprocess
        proc = subprocess.Popen(
            MCP_CMD,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        print(f"[TEST] Falha ao iniciar MCP: {e}")
        raise

    def send_recv(request: dict) -> dict | None:
        """
        Envia requisição JSON-RPC e retorna a resposta parseada.
        
        Args:
            request: Dict no formato JSON-RPC 2.0.
            
        Returns:
            Dict com a resposta ou None em caso de falha.
        """
        try:
            proc.stdin.write(json.dumps(request) + "\n")
            proc.stdin.flush()
        except Exception as e:
            print(f"[TEST] Erro ao enviar requisição: {e}")
            return None

        buffer = ""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                ready, _, _ = select.select([proc.stdout], [], [], deadline - time.time())
                if not ready:
                    break
                line = proc.stdout.readline()
                if not line:
                    break
                buffer += line
                try:
                    return json.loads(buffer.strip())
                except json.JSONDecodeError:
                    continue
            except Exception as e:
                print(f"[TEST] Erro na leitura: {e}")
                return None

        # Tenta parsear o que temos no buffer mesmo após timeout
        if buffer.strip():
            try:
                return json.loads(buffer.strip())
            except json.JSONDecodeError:
                pass
        print("[TEST] Timeout aguardando resposta do MCP")
        return None

    try:
        yield proc, send_recv
    finally:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass


def run_tests() -> dict:
    """
    Executa bateria de testes contra o MCP server.
    
    Returns:
        Dict com resultados agregados dos testes.
    """
    results = {
        "process_alive": False,
        "initialize_ok": False,
        "tools_list_ok": False,
        "tool_count": 0,
        "server_name": None,
        "error": None,
    }

    # Verifica se o processo já está rodando antes de iniciar novo
    if not _check_process_alive():
        results["error"] = "MCP server não está rodando (nem como background nem via teste)"
        return results

    results["process_alive"] = True

    print("\n[TEST] Iniciando teste de protocolo MCP...")
    try:
        with _mcp_session() as (proc, send_recv):
            # 1. Initialize handshake
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "0.1.0"},
                },
            }
            init_resp = send_recv(init_req)

            if init_resp and "result" in init_resp:
                results["initialize_ok"] = True
                info = init_resp["result"].get("serverInfo", {})
                results["server_name"] = info.get("name")
                print(f"[TEST] Initialize OK: {results['server_name']}")
            else:
                print(f"[TEST] Initialize FALHOU: {init_resp}")

            # 2. Tools list
            tools_req = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
            tools_resp = send_recv(tools_req)

            if tools_resp and "result" in tools_resp:
                tools = tools_resp["result"].get("tools", [])
                results["tools_list_ok"] = True
                results["tool_count"] = len(tools)
                print(f"[TEST] Tools list OK: {len(tools)} ferramentas")
                for tool in tools[:8]:
                    desc = (tool.get("description") or "")[:70]
                    print(f"  - {tool.get('name')}: {desc}")
                if len(tools) > 8:
                    print(f"  ... e mais {len(tools) - 8} ferramentas")
            else:
                print(f"[TEST] Tools list FALHOU: {tools_resp}")

    except Exception as e:
        results["error"] = str(e)
        print(f"[TEST] Exceção durante teste: {e}")
        return results

    return results


if __name__ == "__main__":
    print("=" * 70)
    print("TESTE MCP SERVER — iaglobal")
    print("=" * 70)

    result = run_tests()

    print("\n" + "=" * 70)
    print("RESULTADO FINAL")
    print("=" * 70)
    for k, v in result.items():
        print(f"  {k}: {v}")

    if result.get("initialize_ok") and result.get("tools_list_ok"):
        print("\n✅ MCP SERVER ESTÁ FUNCIONAL")
        sys.exit(0)
    else:
        print("\n❌ MCP SERVER COM FALHAS")
        if result.get("error"):
            print(f"   Erro: {result['error']}")
        sys.exit(1)
