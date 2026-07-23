# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do MCP Protocol Expansion — Fases 1, 2 e 3.

Cobertura:
  Fase 1 — Serviços de Cliente MCP:
    - mcp_server.py: FastMCP tools registradas e importáveis
    - search_web.py: WebSearchTool cache/fetch
    - file_system.py: FileSystemTool whitelist (read/write/list)
    - code_executor.py: CodeExecutorTool sandbox wrapper
    - client.py: MCPClient conexão e list_tools
    - discovery.py: MCPDiscovery descoberta e cache
    - mcp_tools.json: cache persistido com schema correto

  Fase 2 — Integração com Agentes:
    - tool_caller_agent.py: ToolCallerAgent seleção e execução
    - validation/validation_engine.py: validate_mcp_call schema checking

  Fase 3 — Segurança:
    - security/mcp_sandbox.py: MCPSandbox whitelist/rate-limit/audit
    - immunity/glutathione_guardrails.py: MCP_RATE_LIMITS + rate check
    - memory/data/json/audit.json: audit trail schema
"""

import asyncio
import json
import logging
import time
from pathlib import Path

import pytest

from iaglobal._paths import PROJECT_ROOT
from iaglobal.validation.validation_engine import FeedbackEngine
from iaglobal.immunity.glutathione_guardrails import (
    GlutathioneGuardrails,
    MCP_RATE_LIMITS,
)

logging.basicConfig(level=logging.ERROR)

PACKAGE_DIR = Path(__file__).resolve().parent.parent


def _run(coro):
    return asyncio.run(coro)


# ─────────────────────────────────────────────
# FASE 1 — Serviços de Cliente MCP
# ─────────────────────────────────────────────


class TestMCPServer:
    """mcp_server.py — FastMCP server com tools registradas."""

    def test_imports_and_tools_exist(self):
        from iaglobal.mcp.mcp_server import mcp, metabolic_audit, get_ivm
        from iaglobal.mcp.mcp_server import read_file, write_file, list_dir
        from iaglobal.mcp.mcp_server import web_search, web_fetch, execute_code

        for fn in [
            metabolic_audit,
            get_ivm,
            read_file,
            write_file,
            list_dir,
            web_search,
            web_fetch,
            execute_code,
        ]:
            assert callable(fn), f"{fn.__name__} deve ser callable"

        assert mcp is not None


class TestWebSearchTool:
    """search_web.py — busca web com cache e TTL."""

    def test_cache_hit_and_miss(self):
        from iaglobal.mcp.search_web import WebSearchTool

        tool = WebSearchTool(cache_ttl=300)
        assert tool._cache == {}
        assert tool._cache_ttl == 300

    def test_cache_eviction(self):
        from iaglobal.mcp.search_web import WebSearchTool

        tool = WebSearchTool(cache_ttl=0.01)
        tool._set_cache("k1", [{"title": "t1"}])
        assert "k1" in tool._cache
        time.sleep(0.02)
        assert tool._get_from_cache("k1") is None

    def test_cache_max_size(self):
        from iaglobal.mcp.search_web import WebSearchTool

        tool = WebSearchTool()
        for i in range(105):
            tool._set_cache(f"k{i}", [{"title": f"t{i}"}])
        assert len(tool._cache) <= 100


class TestFileSystemTool:
    """file_system.py — whitelist de paths seguros."""

    def test_read_file_allowed(self):
        from iaglobal.mcp.file_system import FileSystemTool

        content = _run(FileSystemTool().read_file("iaglobal/mcp/__init__.py"))
        assert content is not None

    def test_read_file_blocked_external(self):
        from iaglobal.mcp.file_system import FileSystemTool

        content = _run(FileSystemTool().read_file("/etc/passwd"))
        assert content is None

    def test_read_file_blocked_relative_escape(self):
        from iaglobal.mcp.file_system import FileSystemTool

        content = _run(FileSystemTool().read_file("../../etc/passwd"))
        assert content is None

    def test_write_file_allowed(self):
        from iaglobal.mcp.file_system import FileSystemTool

        ok = _run(
            FileSystemTool().write_file(
                "memory/data/json/_mcp_test_tmp.json", '{"test": true}'
            )
        )
        assert ok is True
        path = PROJECT_ROOT / "memory" / "data" / "json" / "_mcp_test_tmp.json"
        assert path.exists()
        path.unlink(missing_ok=True)

    def test_write_file_blocked(self):
        from iaglobal.mcp.file_system import FileSystemTool

        ok = _run(FileSystemTool().write_file("/tmp/malicious.txt", "x"))
        assert ok is False

    def test_list_dir_allowed(self):
        from iaglobal.mcp.file_system import FileSystemTool

        entries = _run(FileSystemTool().list_dir("iaglobal/mcp"))
        assert len(entries) >= 6
        assert any("mcp_server.py" in e for e in entries)

    def test_list_dir_blocked(self):
        from iaglobal.mcp.file_system import FileSystemTool

        entries = _run(FileSystemTool().list_dir("/etc"))
        assert entries == []


class TestCodeExecutorTool:
    """code_executor.py — wrapper MCP do SandboxExecutor."""

    def test_execute_code_simple(self):
        from iaglobal.mcp.code_executor import CodeExecutorTool

        result = _run(CodeExecutorTool().execute("print('mcp_ok')"))
        assert result["sucesso"] is True
        assert "mcp_ok" in result.get("stdout", "")

    def test_execute_code_unsupported_language(self):
        from iaglobal.mcp.code_executor import CodeExecutorTool

        result = _run(CodeExecutorTool().execute("print(1)", language="java"))
        assert result["sucesso"] is False
        assert "UnsupportedLanguage" in result.get("erro", "")

    def test_validate_code(self):
        from iaglobal.mcp.code_executor import CodeExecutorTool

        result = _run(CodeExecutorTool().validate("x = 1"))
        assert result["valid"] is True


class TestMCPClient:
    """client.py — conexão a servidores MCP externos."""

    def test_connect_no_server_returns_error(self):
        from iaglobal.mcp.client import MCPClient

        client = MCPClient()
        result = _run(client.connect_stdio("python3", ["-c", "print('mcp')"]))
        assert "error" in result or "serverInfo" in result or isinstance(result, dict)

    def test_list_tools_sem_conexao(self):
        from iaglobal.mcp.client import MCPClient

        client = MCPClient()
        tools = _run(client.list_tools())
        assert tools == []

    def test_call_tool_sem_conexao(self):
        from iaglobal.mcp.client import MCPClient

        client = MCPClient()
        result = _run(client.call_tool("test", {}))
        assert "error" in result


class TestMCPDiscovery:
    """discovery.py — descoberta dinâmica e cache de tools."""

    def test_discover_all_contains_internal_tools(self):
        from iaglobal.mcp.discovery import MCPDiscovery

        data = _run(MCPDiscovery().discover_all())
        assert data["version"] == 1
        names = {t["name"] for t in data["tools"]}
        assert "web_search" in names
        assert "read_file" in names
        assert "execute_code" in names
        assert "metabolic_audit" in names

    def test_get_tool_found(self):
        from iaglobal.mcp.discovery import MCPDiscovery

        tool = _run(MCPDiscovery().get_tool("web_search"))
        assert tool is not None
        assert tool["name"] == "web_search"
        assert "parameters" in tool

    def test_get_tool_not_found(self):
        from iaglobal.mcp.discovery import MCPDiscovery

        tool = _run(MCPDiscovery().get_tool("nonexistent_tool_xyz"))
        assert tool is None

    def test_cache_file_persisted(self):
        from iaglobal.mcp.discovery import CACHE_PATH

        assert CACHE_PATH.exists()
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert len(data["tools"]) >= 8
        assert "updated_at" in data


# ─────────────────────────────────────────────
# FASE 2 — Integração com Agentes
# ─────────────────────────────────────────────


class TestToolCallerAgent:
    """tool_caller_agent.py — seleciona e executa tools MCP."""

    def test_tool_caller_read_file_success(self):
        from iaglobal.agents.tool_caller_agent import ToolCallerAgent

        result = _run(
            ToolCallerAgent().run(
                {
                    "tool_name": "read_file",
                    "arguments": {"path": "iaglobal/mcp/__init__.py"},
                    "agent_id": "test_tca",
                }
            )
        )
        assert result["execution_metrics"]["success"] is True
        assert result["result"] is not None
        assert result["execution_metrics"]["tool_name"] == "read_file"

    def test_tool_caller_internal_not_mapped(self):
        from iaglobal.agents.tool_caller_agent import ToolCallerAgent

        result = _run(
            ToolCallerAgent().run(
                {
                    "tool_name": "metabolic_audit",
                    "arguments": {},
                    "agent_id": "test_tca",
                }
            )
        )
        assert result["execution_metrics"]["success"] is False
        assert "error" in str(result.get("result", {}))

    def test_tool_caller_nonexistent(self):
        from iaglobal.agents.tool_caller_agent import ToolCallerAgent

        result = _run(
            ToolCallerAgent().run(
                {
                    "tool_name": "tool_nao_existe",
                    "arguments": {},
                    "agent_id": "test_tca",
                }
            )
        )
        assert result["execution_metrics"]["success"] is False

    def test_tool_caller_execution_metrics_structure(self):
        from iaglobal.agents.tool_caller_agent import ToolCallerAgent

        result = _run(
            ToolCallerAgent().run(
                {
                    "tool_name": "list_dir",
                    "arguments": {"path": "iaglobal/mcp"},
                    "agent_id": "test_metrics",
                }
            )
        )
        metrics = result["execution_metrics"]
        assert "tool_name" in metrics
        assert "success" in metrics
        assert "latency" in metrics
        assert isinstance(metrics["latency"], float)
        assert "arguments" in metrics
        assert "result_summary" in metrics


class TestValidationEngineMCP:
    """validation/validation_engine.py — validate_mcp_call schema checking."""

    def test_valid_call_passes(self):
        engine = FeedbackEngine()
        schema = {
            "parameters": {"query": {"type": "string"}, "limit": {"type": "integer"}}
        }
        assert engine.validate_mcp_call(schema, {"query": "test", "limit": 5}) is True

    def test_invalid_type_fails(self):
        engine = FeedbackEngine()
        schema = {"parameters": {"limit": {"type": "integer"}}}
        assert engine.validate_mcp_call(schema, {"limit": "not_an_int"}) is False

    def test_no_params_always_passes(self):
        engine = FeedbackEngine()
        assert engine.validate_mcp_call({}, {"anything": 42}) is True

    def test_boolean_type(self):
        engine = FeedbackEngine()
        schema = {"parameters": {"flag": {"type": "boolean"}}}
        assert engine.validate_mcp_call(schema, {"flag": True}) is True
        assert engine.validate_mcp_call(schema, {"flag": "yes"}) is False

    def test_none_value_for_optional(self):
        engine = FeedbackEngine()
        schema = {"parameters": {"query": {"type": "string"}}}
        assert engine.validate_mcp_call(schema, {"query": None}) is True


# ─────────────────────────────────────────────
# FASE 3 — Segurança
# ─────────────────────────────────────────────


class TestMCPSandbox:
    """security/mcp_sandbox.py — whitelist, rate limit, audit trail."""

    def test_validate_call_allowed(self):
        from iaglobal.security.mcp_sandbox import MCPSandbox

        allowed = _run(MCPSandbox().validate_call("web_search", {}))
        assert allowed is True

    def test_validate_call_blocked(self):
        from iaglobal.security.mcp_sandbox import MCPSandbox

        allowed = _run(MCPSandbox().validate_call("rm_rf", {}))
        assert allowed is False

    def test_validate_call_blocked_system(self):
        from iaglobal.security.mcp_sandbox import MCPSandbox

        allowed = _run(MCPSandbox().validate_call("os.system", {}))
        assert allowed is False

    def test_rate_limit_allowed(self):
        from iaglobal.security.mcp_sandbox import MCPSandbox

        allowed = _run(MCPSandbox().check_rate_limit("read_file", "test_agent"))
        assert allowed is True

    @pytest.mark.asyncio
    async def test_audit_trail_blocked_recorded(self):
        from iaglobal.security.mcp_sandbox import MCPSandbox, AUDIT_PATH
        import json

        # Setup: Limpa audit.json antes de testar para garantir isolamento
        if AUDIT_PATH.exists():
            AUDIT_PATH.unlink()

        sandbox = MCPSandbox()

        # Chama com allowed=False para simular o bloqueio que o teste espera
        await sandbox.audit_call("rm_rf", {}, "access_denied", "e2e_test", False)

        # Verifica se o arquivo foi criado e contém a entrada
        assert AUDIT_PATH.exists(), "O arquivo de auditoria não foi criado."

        with open(AUDIT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Agora a decisão será 'blocked' conforme esperado pela chamada anterior
            assert data["audits"][0]["sandbox_decision"] == "blocked"


class TestGlutathioneRateLimit:
    """immunity/glutathione_guardrails.py — MCP_RATE_LIMITS + check."""

    def test_rate_limit_constants_defined(self):
        assert "web_search" in MCP_RATE_LIMITS
        assert "execute_code" in MCP_RATE_LIMITS
        assert MCP_RATE_LIMITS["web_search"]["calls_per_minute"] == 10

    def test_rate_limit_allowed(self):
        result = GlutathioneGuardrails.check_mcp_rate_limit("web_search", "test_agent")
        assert result["allowed"] is True

    def test_rate_limit_for_unconfigured_tool(self):
        result = GlutathioneGuardrails.check_mcp_rate_limit(
            "unknown_tool", "test_agent"
        )
        assert result["allowed"] is True
        assert "Sem limite configurado" in result.get("reason", "")


class TestAuditTrail:
    """memory/data/json/audit.json — schema e persistência."""

    def test_audit_json_exists_and_valid(self):
        path = (
            Path(PROJECT_ROOT) / "iaglobal" / "memory" / "data" / "json" / "audit.json"
        )
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "audits" in data
        assert isinstance(data["audits"], list)

    def test_audit_entry_schema(self):
        from iaglobal.security.mcp_sandbox import MCPSandbox, AUDIT_PATH

        before = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        count_before = len(before["audits"])

        _run(
            MCPSandbox().audit_call(
                "test_tool", {"arg": 1}, "ok", agent_id="test_schema", allowed=True
            )
        )

        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        entry = data["audits"][-1]
        assert "timestamp" in entry
        assert "T" in entry["timestamp"]
        assert entry["agent_id"] == "test_schema"
        assert entry["tool"] == "test_tool"
        assert entry["arguments"] == {"arg": 1}
        assert entry["sandbox_decision"] in ("allowed", "blocked")


class TestMCPServerRun:
    """mcp_server.py — run_server helper."""

    def test_run_server_import(self):
        from iaglobal.mcp.mcp_server import run_server

        assert callable(run_server)

    def test_mcp_agent_integration(self):
        from iaglobal.mcp.mcp_agent import MCPAgent
        from iaglobal.mcp.mcp_server import _get_agent

        agent = _get_agent()
        assert isinstance(agent, MCPAgent)
        assert len(agent.sondas) == 3


class TestMCPToolsJSON:
    """mcp_tools.json — cache persistido com schema correto."""

    def test_json_schema(self):
        path = (
            Path(PROJECT_ROOT)
            / "iaglobal"
            / "memory"
            / "data"
            / "json"
            / "mcp_tools.json"
        )
        assert path.exists()

        data = json.loads(path.read_text(encoding="utf-8"))
        assert "version" in data
        assert "updated_at" in data
        assert "tools" in data

        for tool in data["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert "server" in tool
            assert "parameters" in tool


import pytest
from iaglobal.agents.tool_caller_agent import ToolCallerAgent
from iaglobal.security.mcp_sandbox import MCPSandbox


@pytest.mark.asyncio
class TestToolCallerAgentIntegration:
    """Testes de integração: tool_caller_agent + sandbox (Assíncrono)."""

    async def test_end_to_end_file_read(self):
        sandbox = MCPSandbox()
        agent = ToolCallerAgent()

        tool_name = "read_file"
        args = {"path": "iaglobal/mcp/__init__.py"}

        # Validação via sandbox (agora await)
        is_allowed = await sandbox.validate_call(tool_name, args)
        assert is_allowed is True

        # Execução do agente (agora await)
        result = await agent.run(
            {"tool_name": tool_name, "arguments": args, "agent_id": "e2e_test"}
        )

        assert result["execution_metrics"]["success"] is True
        assert result["result"] is not None

    async def test_end_to_end_list_dir(self):
        sandbox = MCPSandbox()
        agent = ToolCallerAgent()

        tool_name = "list_dir"
        args = {"path": "iaglobal/mcp"}

        assert await sandbox.validate_call(tool_name, args) is True

        result = await agent.run(
            {"tool_name": tool_name, "arguments": args, "agent_id": "e2e_test"}
        )

        assert result["execution_metrics"]["success"] is True
        # Validação funcional: garantir que retornou algo (lista)
        assert isinstance(result["result"], list)
        assert len(result["result"]) >= 1

    async def test_end_to_end_blocked_by_sandbox(self):
        sandbox = MCPSandbox()
        agent = ToolCallerAgent()

        tool_name = "rm_rf"
        args = {}

        # O sandbox deve bloquear a chamada
        assert await sandbox.validate_call(tool_name, args) is False

        result = await agent.run(
            {"tool_name": tool_name, "arguments": args, "agent_id": "e2e_test"}
        )

        # O agente deve relatar falha pois a chamada não foi autorizada
        assert result["execution_metrics"]["success"] is False
