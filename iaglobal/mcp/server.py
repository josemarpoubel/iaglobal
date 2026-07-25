# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
MCP Server Unificado — Consolidação dos 3 servidores MCP do iaglobal.

Este servidor unificado integra:
1. FastMCP tools (metabolic_audit, get_ivm, web_search, file_system, code_exec)
2. IAGlobalAPI pipeline (run_task, get_status, get_history)
3. FastAPI gateway (/health, /audit, /fix, /metrics, /jsonrpc)
4. AcetylcholineBus integration (métricas, comandos, violações)

Arquitetura modular:
- Core MCP: tools nativas do protocolo MCP
- API Tools: integração com pipeline iaglobal
- HTTP Gateway: endpoints REST para compatibilidade
- Bus Integration: comunicação assíncrona com organismo

Uso:
    python -m iaglobal.mcp.server
"""

import asyncio
import time
import os
from typing import Any, Dict, Optional
from datetime import datetime, timezone

# FastMCP core
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None

# FastAPI gateway
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse

# iaglobal core
from iaglobal.mcp.mcp_agent import MCPAgent
from iaglobal.mcp.search_web import WebSearchTool
from iaglobal.mcp.file_system import FileSystemTool
from iaglobal.mcp.code_executor import CodeExecutorTool
from iaglobal.mcp.placeholder import MCPPlaceholder
from iaglobal.api import IAGlobalAPI
from iaglobal.metabolism.metabolic_invariants import MetabolicInvariants
from iaglobal.metabolism.metabolic_autocorrect import MetabolicAutocorrect
from iaglobal.obsidian.omnimind import omni_mind
from iaglobal.core.env_loader import load_env
from iaglobal.utils.logger import get_logger

# Optional: AcetylcholineBus
try:
    from iaglobal.graphs.comms.acetylcholine_bus import AcetylcholineBus, AgentMessage

    BUS_AVAILABLE = True
except ImportError:
    BUS_AVAILABLE = False
    AcetylcholineBus = None
    AgentMessage = None

logger = get_logger("iaglobal.mcp.unified")

# ==============================================================================
# SINGLETONS GLOBAIS
# ==============================================================================

_agent: Optional[MCPAgent] = None
_web_search: Optional[WebSearchTool] = None
_file_system: Optional[FileSystemTool] = None
_code_exec: Optional[CodeExecutorTool] = None
_api: Optional[IAGlobalAPI] = None
_invariants: Optional[MetabolicInvariants] = None
_autocorrect: Optional[MetabolicAutocorrect] = None
_bus: Optional[AcetylcholineBus] = None
_fastapi_app: Optional[FastAPI] = None
_mcp_instance = None  # Instância FastMCP


def _get_agent() -> MCPAgent:
    global _agent
    if _agent is None:
        _agent = MCPAgent()
    return _agent


def _get_web_search() -> WebSearchTool:
    global _web_search
    if _web_search is None:
        _web_search = WebSearchTool()
    return _web_search


def _get_file_system() -> FileSystemTool:
    global _file_system
    if _file_system is None:
        _file_system = FileSystemTool()
    return _file_system


def _get_code_exec() -> CodeExecutorTool:
    global _code_exec
    if _code_exec is None:
        _code_exec = CodeExecutorTool()
    return _code_exec


def _get_api() -> IAGlobalAPI:
    global _api
    if _api is None:
        _api = IAGlobalAPI(lazy_init=True)
    return _api


async def _ensure_phase1() -> None:
    """Idempotente. Aguarda Phase1 (~50ms) e agenda Phase2 em background."""
    from iaglobal.cli.bootstrap import bootstrap as _bootstrap

    await _bootstrap.ensure_phase1()


async def _ensure_full() -> "Orchestrator":
    """Idempotente. Aguarda Phase2 completo e sincroniza IAGlobalAPI."""
    from iaglobal.cli.bootstrap import bootstrap as _bootstrap

    orch = await _bootstrap.initialize()
    api = _get_api()
    if not api._initialized and orch is not None:
        api._orchestrator = orch
        api._initialized = True
    return orch


def _boot_snapshot() -> dict:
    from iaglobal.cli.bootstrap import bootstrap as _bootstrap

    return _bootstrap.snapshot()


def _ready() -> bool:
    from iaglobal.cli.bootstrap import bootstrap as _bootstrap

    return _bootstrap._phase2_done


def _get_invariants() -> MetabolicInvariants:
    global _invariants
    if _invariants is None:
        _invariants = MetabolicInvariants()
    return _invariants


def _get_autocorrect() -> MetabolicAutocorrect:
    global _autocorrect
    if _autocorrect is None:
        _autocorrect = MetabolicAutocorrect()
    return _autocorrect


def _get_bus() -> Optional[AcetylcholineBus]:
    global _bus
    if _bus is None and BUS_AVAILABLE:
        try:
            _bus = AcetylcholineBus()
        except Exception as e:
            logger.warning(f"AcetylcholineBus não disponível: {e}")
    return _bus


# ==============================================================================
# FASTMCP CORE SERVER
# ==============================================================================

if FastMCP is not None:
    mcp = FastMCP(
        "iaglobal-unified",
        instructions="""Sistema imunológico evolutivo iaglobal com ferramentas MCP integradas.

== TOOLS METABÓLICAS ==
- metabolic_audit: Auditoria metabólica completa do sistema
- get_ivm: Índice de Viabilidade Metabólica (0-1)
- run_task: Executa pipeline completo de engenharia de software
- get_status: Status do DAG, evolução e memória

== TOOLS WEB ==
- web_search: Busca web com cache e deduplicação
- web_fetch: Fetch de conteúdo de URL com timeout

== TOOLS FILE SYSTEM ==
- read_file: Leitura segura (whitelist enforced)
- write_file: Escrita segura (whitelist enforced)
- list_dir: Listagem de diretórios (whitelist enforced)

== TOOLS CODE EXECUTION ==
- execute_code: Execução em sandbox isolada com timeout

== PROTOCOLO ==
DNA: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
""",
    )

    # --------------------------------------------------------------------------
    # TOOLS METABÓLICAS
    # --------------------------------------------------------------------------

    @mcp.tool()
    async def metabolic_audit() -> dict:
        """Executa auditoria metabólica completa do sistema."""
        agent = _get_agent()
        audit = await agent.run_audit()
        return {
            "score": audit.score,
            "findings": {k: v["status"] for k, v in audit.findings.items()},
            "corrections": len(audit.corrections),
            "timestamp": audit.timestamp,
        }

    @mcp.tool()
    async def get_ivm() -> float:
        """Retorna o Índice de Viabilidade Metabólica atual."""
        return _get_agent()._get_ivm()

    # --------------------------------------------------------------------------
    # TOOLS IAGLOBAL API
    # --------------------------------------------------------------------------

    @mcp.tool()
    async def run_task(prompt: str) -> str:
        """Executa tarefa de engenharia de software no pipeline iaglobal.

        Pipeline: planner → web_classifier → search → multi_coder → critic →
        validator → ast_validator → tester → debugger → rank_final →
        final_gatekeeper → artifact_writer → reflexion

        Args:
            prompt: Descrição da tarefa

        Returns:
            Relatório formatado da execução
        """
        api = _get_api()
        await _ensure_full()
        result = api.run_task(prompt)

        lines = []
        if result["success"]:
            lines.append(f"✅ Tarefa concluída em {result['execution_time']}s")
            if result["script_path"]:
                lines.append(f"📁 Script salvo em: {result['script_path']}")
            if result["response"]:
                lines.append(f"📄 Código gerado ({len(result['response'])} caracteres)")
                lines.append("```python")
                lines.append(result["response"][:2000])
                if len(result["response"]) > 2000:
                    lines.append("# ... (código truncado)")
                lines.append("```")
            if result["score"]:
                lines.append(f"🏆 Score: {result['score']:.2f}")
        else:
            lines.append(f"❌ Erro: {result['error']}")
        return "\n".join(lines)

    @mcp.tool()
    async def get_status() -> str:
        """Retorna status do sistema iaglobal (DAG, evolução, memória).

        Lazy: responde imediatamente em BOOTING se Phase2 ainda corre.
        """
        await _ensure_phase1()

        snap = _boot_snapshot()
        if not snap["phase2_done"]:
            steps = (
                ", ".join(
                    f"{k}={v}"
                    for k, v in snap["phase2_steps"].items()
                    if v == "running"
                )
                or "—"
            )
            return (
                f"⚡ IAGlobal {snap['current_phase'] or 'phase1'}\n"
                f"  phase1_done: {snap['phase1_done']}\n"
                f"  phase2_running: {snap['phase2_running']}\n"
                f"  steps running: {steps}\n"
                f"  phase2_elapsed: {snap['phase2_elapsed_seconds']}s"
            )

        await _ensure_full()
        status = _get_api().get_status()
        if not status:
            return "⚠️ Status vazio (orchestrator initialized mas sem snapshot)"

        def get_val(path: list, default="N/A"):
            curr = status
            for key in path:
                if isinstance(curr, dict):
                    curr = curr.get(key, {})
                else:
                    return default
            return curr if curr != {} else default

        lines = [
            "📊 IAGlobal Status",
            "=" * 40,
            "",
            f"  Graph gen: {get_val(['version', 'graph_gen'])}",
            f"  Python:    {get_val(['version', 'python'])}",
            "",
            "── DAG ──",
            f"  Total nodes: {get_val(['dag', 'nodes_total'])}",
            f"  Core: {get_val(['dag', 'nodes_core'])} | EVO: {get_val(['dag', 'nodes_evo'])}",
            "",
            "── Evolution ──",
            f"  Running: {'yes' if get_val(['evolution', 'running']) else 'no'}",
            f"  Cycles: {get_val(['evolution', 'cycles'])}",
            "",
            "── Memory ──",
            f"  Insights: {get_val(['memory', 'insights'])}",
            f"  Errors: {get_val(['memory', 'errors'])}",
        ]
        return "\n".join(lines)

    @mcp.tool()
    async def get_history(limit: int = 10) -> list[dict]:
        """Retorna histórico de execuções recentes. Lazy: [] durante BOOTING."""
        await _ensure_phase1()
        if not _ready():
            return []
        try:
            from iaglobal.events import store as decision_store

            events = decision_store.query(limit=limit) or []
        except Exception:
            events = []
        if not events:
            try:
                from iaglobal.memory.db_manager import db

                events = db.get_insights(limit=limit) or []
            except Exception:
                events = []
        return events

    # --------------------------------------------------------------------------
    # TOOLS OBSERVABILIDADE (lazy: snapshot/dados de I/O leve durante BOOTING)
    # --------------------------------------------------------------------------

    @mcp.tool()
    async def get_insights(
        agent: str = "", limit: int = 10, min_score: float = 0.0
    ) -> str:
        """Recupera aprendizados armazenados pelos agentes."""
        await _ensure_phase1()
        if not _ready():
            return "BOOTING: insights indisponíveis até Phase2."
        records = _get_api().get_insights(
            agent=agent if agent else None,
            limit=limit,
            min_score=min_score if min_score > 0 else None,
        )
        if not records:
            return "Nenhum insight encontrado."

        lines = [f"📚 {len(records)} insights", "=" * 40, ""]
        for r in records:
            score_bar = "█" * max(1, int(r["score"] / 5)) + "░" * max(
                0, 20 - int(r["score"] / 5)
            )
            lines.append(f"  [{r['agent']}] score={r['score']:.0f} {score_bar}")
            lines.append(f"  {r['content'][:120]}")
            lines.append(f"  task_id={r['task_id']} | {r['timestamp']}")
            lines.append("")
        return "\n".join(lines)

    @mcp.tool()
    async def list_scripts() -> str:
        """Lista scripts Python gerados e persistidos pelo sistema."""
        await _ensure_phase1()
        if not _ready():
            return "BOOTING: listagem de scripts indisponível até Phase2."
        scripts = _get_api().list_scripts()
        if not scripts:
            return "Nenhum script gerado ainda."

        from datetime import datetime

        lines = [f"📁 {len(scripts)} scripts gerados", "=" * 40, ""]
        for s in scripts:
            modified = datetime.fromtimestamp(s["modified"]).strftime("%H:%M:%S")
            size_kb = s["size"] / 1024
            lines.append(f"  {s['name']:<60} {size_kb:>6.1f}KB  {modified}")
        return "\n".join(lines)

    @mcp.tool()
    async def get_provider_metrics() -> str:
        """Métricas por provedor (read-only, não precisa de Phase2)."""
        from iaglobal.providers.provider_metrics import metrics

        stats = metrics.get_provider_stats()
        if not stats:
            return "Nenhuma metrica de provedor registrada ainda."

        lines = ["📊 Metricas por Provedor", "=" * 50, ""]
        lines.append(
            f"  {'Provedor':<20} {'Chamadas':>9} {'Sucesso':>8} {'Lat.Media':>9} {'Custo':>8} {'Tokens':>8}"
        )
        lines.append(f"  {'─' * 20} {'─' * 9} {'─' * 8} {'─' * 9} {'─' * 8} {'─' * 8}")
        for prov, data in sorted(
            stats.items(), key=lambda x: x[1].get("calls", 0), reverse=True
        ):
            calls = data.get("calls", 0)
            sr = data.get("success_rate", 0)
            lat = data.get("avg_latency", 0)
            cost = data.get("total_cost", 0)
            tokens = data.get("avg_tokens", 0)
            lines.append(
                f"  {prov:<20} {calls:>9} {sr:>7.1%} {lat:>8.0f}ms ${cost:<6.4f} {tokens:>8}"
            )
        return "\n".join(lines)

    @mcp.tool()
    async def get_model_metrics(min_calls: int = 1) -> str:
        """Métricas por modelo (read-only)."""
        from iaglobal.providers.provider_metrics import metrics

        stats = metrics.get_model_stats()
        if not stats:
            return "Nenhuma metrica de modelo registrada ainda."
        filtered = {k: v for k, v in stats.items() if v.get("calls", 0) >= min_calls}
        if not filtered:
            return f"Nenhum modelo com {min_calls}+ chamadas."

        lines = ["📊 Metricas por Modelo", "=" * 55, ""]
        lines.append(
            f"  {'Modelo':<35} {'Chamadas':>9} {'Sucesso':>8} {'Lat.Media':>9} {'Tokens':>8}"
        )
        lines.append(f"  {'─' * 35} {'─' * 9} {'─' * 8} {'─' * 9} {'─' * 8}")
        for model, data in sorted(
            filtered.items(), key=lambda x: x[1].get("calls", 0), reverse=True
        ):
            calls = data.get("calls", 0)
            sr = data.get("success_rate", 0)
            lat = data.get("avg_latency", 0)
            tokens = data.get("avg_tokens", 0)
            lines.append(
                f"  {model:<35} {calls:>9} {sr:>7.1%} {lat:>8.0f}ms {tokens:>8}"
            )
        return "\n".join(lines)

    @mcp.tool()
    async def get_bandit_scores() -> str:
        """Exibe scores do BanditPolicy. Lazy: espera Phase2."""
        await _ensure_phase1()
        if not _ready():
            return "BOOTING: BanditPolicy ainda não carregado (Phase2 em andamento)."
        await _ensure_full()
        try:
            orch = _get_api().orchestrator
            bandit = orch.bandit
            credit = bandit.credit_engine
        except Exception:
            return "BanditPolicy nao disponivel (orchestrator nao inicializado)."

        if not credit.stats:
            return "Nenhum score de bandit registrado ainda."

        lines = ["🎲 BanditPolicy — Scores por Modelo", "=" * 50, ""]
        lines.append(
            f"  {'Modelo':<35} {'Sucesso':>8} {'Falhas':>8} {'Score':>7} {'Latencia':>9}"
        )
        lines.append(f"  {'─' * 35} {'─' * 8} {'─' * 8} {'─' * 7} {'─' * 9}")
        for key, data in sorted(
            credit.stats.items(), key=lambda x: x[1].get("success", 0), reverse=True
        ):
            node, model, strategy = key
            suc = data.get("success", 0)
            fail = data.get("fail", 0)
            total = suc + fail
            score = suc / total if total > 0 else 0
            lat = data.get("latency", 0)
            avg_lat = lat / total if total > 0 else 0
            lines.append(
                f"  {model:<35} {suc:>8} {fail:>8} {score:>6.2f} {avg_lat:>8.0f}ms"
            )
        return "\n".join(lines)

    @mcp.tool()
    async def get_execution_history(limit: int = 10) -> str:
        """Histórico das últimas execuções do pipeline."""
        await _ensure_phase1()
        if not _ready():
            return "BOOTING: DecisionEventStore ainda não carregado."
        try:
            from iaglobal.events import store as decision_store

            events = decision_store.query(limit=limit)
        except Exception:
            return "DecisionEventStore nao disponivel."
        if not events:
            return "Nenhum evento de execucao registrado."

        lines = ["📜 Historico de Execucoes", "=" * 50, ""]
        for ev in events:
            step = ev.get("step", "?")
            action = ev.get("action", "")
            selected = ev.get("selected", "")
            result = ev.get("result", "")
            ts = ev.get("timestamp", "")[11:19] if ev.get("timestamp") else ""
            line = f"  [{ts}] {step:<18}"
            if action:
                line += f" {action:<20}"
            if selected:
                line += f" → {selected}"
            if result:
                line += f" = {result}"
            lines.append(line)
        return "\n".join(lines)

    @mcp.tool()
    async def get_system_health(max_age_seconds: int = 3600) -> str:
        """Saúde do sistema via LifeSignals. Lazy: BOOTING se nenhum sinal."""
        await _ensure_phase1()
        try:
            from iaglobal.utils.life_signal_collector import collector
        except Exception:
            return "LifeSignalCollector nao disponivel."

        report = collector.get_report()
        if report["total_functions"] == 0:
            snap = _boot_snapshot()
            return (
                "🚧 IAGlobal em bootstrap\n"
                f"  phase1_done: {snap['phase1_done']}\n"
                f"  phase2_running: {snap['phase2_running']}\n"
                f"  phase2_elapsed: {snap['phase2_elapsed_seconds']}s\n"
                "  Life signals ainda não emitidos (instrumentação será visível após primeira execução)."
            )

        lines = ["🩺 Saúde do Sistema — Life Signals", "=" * 50, ""]
        lines.append(f"Funções monitoradas: {report['total_functions']}")
        lines.append(f"Total de sinais: {report['total_signals']}")
        lines.append("")
        alive = hibernating = dead = 0
        for func, data in sorted(report["functions"].items()):
            status = data["status"]
            if "ALIVE" in status:
                icon, alive = "✅", alive + 1
            elif "HIBERNATING" in status:
                icon, hibernating = hibernating + 1
            else:
                icon, dead = dead + 1
            lines.append(f"  {icon} {func}")
            lines.append(f"      {status}")
            if data.get("last_seen_iso"):
                lines.append(f"      Último sinal: {data['last_seen_iso']}")
        lines.append("")
        lines.append("── Resumo ──")
        lines.append(f"  ALIVE: {alive} | HIBERNATING: {hibernating} | DEAD: {dead}")
        return "\n".join(lines)

    # --------------------------------------------------------------------------
    # TOOLS WEB
    # --------------------------------------------------------------------------

    @mcp.tool()
    async def web_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Busca na web com cache e deduplicação."""
        return await _get_web_search().search(query, max_results=max_results)

    @mcp.tool()
    async def web_fetch(url: str, timeout: int = 15) -> str | None:
        """Fetch de conteúdo de URL."""
        return await _get_web_search().fetch_page(url, timeout=timeout)

    # --------------------------------------------------------------------------
    # TOOLS FILE SYSTEM
    # --------------------------------------------------------------------------

    @mcp.tool()
    async def read_file(path: str) -> str | None:
        """Leitura segura de arquivos (whitelist enforced)."""
        return await _get_file_system().read_file(path)

    @mcp.tool()
    async def write_file(path: str, content: str) -> bool:
        """Escrita segura de arquivos (whitelist enforced)."""
        return await _get_file_system().write_file(path, content)

    @mcp.tool()
    async def list_dir(path: str) -> list[str]:
        """Listagem de diretórios (whitelist enforced)."""
        return await _get_file_system().list_dir(path)

    # --------------------------------------------------------------------------
    # TOOLS CODE EXECUTION
    # --------------------------------------------------------------------------

    @mcp.tool()
    async def execute_code(code: str, language: str = "python") -> dict[str, Any]:
        """Executa código em sandbox isolada com timeout."""
        return await _get_code_exec().execute(code, language=language)

    # --------------------------------------------------------------------------
    # TOOLS EVOLUTION
    # --------------------------------------------------------------------------

    @mcp.tool()
    async def evolution_status() -> dict:
        """Retorna status do motor evolutivo (ciclos, falhas, estratégia)."""
        from iaglobal.evolution.evolutionruntime import get_runtime

        runtime = get_runtime()
        status = runtime.status()

        return {
            "running": status.get("running", False),
            "cycles": status.get("cycles", 0),
            "failures": status.get("failures", 0),
            "strategy": status.get("strategy", "unknown"),
            "interval": status.get("interval", 30),
        }

    @mcp.tool()
    async def evolve_strategy(strategy: str = "fast") -> dict:
        """Alterna estratégia de evolução em tempo de execução.

        Args:
            strategy: 'fast' (30s intervalo) ou 'deep' (300s intervalo)

        Returns:
            Status da mudança de estratégia
        """
        from iaglobal.evolution.evolutionruntime import get_runtime
        from iaglobal.evolution.evolutionruntime import (
            FastEvolutionStrategy,
            DeepEvolutionStrategy,
        )

        runtime = get_runtime()

        if strategy.lower() == "deep":
            runtime.set_strategy(DeepEvolutionStrategy())
        elif strategy.lower() == "fast":
            runtime.set_strategy(FastEvolutionStrategy())
        else:
            return {
                "status": "error",
                "message": "Estratégia inválida. Use 'fast' ou 'deep'.",
            }

        return {
            "status": "success",
            "nova_estrategia": strategy.lower(),
            "intervalo": runtime.interval,
        }

    @mcp.tool()
    async def evolution_dashboard(format: str = "json") -> dict | str:
        """Dashboard em tempo real da evolução.

        Args:
            format: 'json' para dados estruturados, 'ascii' para dashboard textual

        Returns:
            Dashboard em formato JSON ou ASCII
        """
        from iaglobal.evolution.evolutionruntime import get_runtime
        from iaglobal.evolution.evolution_replay import EvolutionReplay

        runtime = get_runtime()
        evo_status = runtime.status()

        if format.lower() == "ascii":
            replay = EvolutionReplay(engine=runtime.evolver)
            return replay.render_ascii_dashboard(max_gen=5)
        else:
            return {
                "evolution": evo_status,
                "timestamp": time.time(),
            }

    # --------------------------------------------------------------------------
    # TOOLS GLUTATIONA (AUTO-CURA / REFLEXION)
    # --------------------------------------------------------------------------

    @mcp.tool()
    async def reflexion_fix(code: str, error: str, language: str = "python") -> dict:
        """Corrige código com base em erro detectado usando ReflexionEngine.

        Args:
            code: Código original que falhou
            error: Mensagem de erro ou traceback
            language: Linguagem do código (default: python)

        Returns:
            Dicionário com código corrigido e explicação
        """
        from iaglobal.reflection.reflexion_engine import ReflexionEngine
        from iaglobal.graphs.bandit import BanditPolicy

        # Criar prompt de reflexão
        prompt = f"""Corrija o seguinte código {language} que apresentou erro:

CÓDIGO ORIGINAL:
```{language}
{code}
```

ERRO DETECTADO:
{error}

Forneça APENAS o código corrigido, sem explicações."""

        # Usar BanditPolicy para obter função de modelo async
        async def model_fn(prompt_text: str) -> str:
            policy = BanditPolicy()
            response = await policy.generate(prompt_text)
            return (
                response.get("content", "")
                if isinstance(response, dict)
                else str(response)
            )

        engine = ReflexionEngine(
            model_fn=lambda p: asyncio.run(model_fn(p)), max_iterations=3
        )

        try:
            # Executar reflexão
            result = engine.reflect(prompt)

            return {
                "status": result.get("status", "unknown"),
                "original_code": code,
                "corrected_code": result.get("code", ""),
                "error_resolved": result.get("status") == "success",
                "iterations": result.get("iterations", 0),
                "elapsed_seconds": result.get("elapsed_seconds", 0),
            }
        except Exception as e:
            logger.exception(f"❌ reflexion_fix falhou: {e}")
            return {
                "status": "error",
                "message": str(e),
                "original_code": code,
            }

    @mcp.tool()
    async def reflexion_loop(prompt: str, max_iterations: int = 5) -> dict:
        """Executa loop completo de reflexão para gerar código auto-corrigido.

        Args:
            prompt: Descrição da tarefa para geração de código
            max_iterations: Número máximo de tentativas (default: 5)

        Returns:
            Resultado com código gerado, status e métricas
        """
        from iaglobal.reflection.reflexion_engine import ReflexionEngine
        from iaglobal.graphs.bandit import BanditPolicy

        async def model_fn(prompt_text: str) -> str:
            policy = BanditPolicy()
            response = await policy.generate(prompt_text)
            return (
                response.get("content", "")
                if isinstance(response, dict)
                else str(response)
            )

        engine = ReflexionEngine(
            model_fn=lambda p: asyncio.run(model_fn(p)), max_iterations=max_iterations
        )

        try:
            result = engine.reflect(prompt)

            return {
                "status": result.get("status", "unknown"),
                "code": result.get("code", ""),
                "prompt": prompt,
                "success": result.get("status") == "success",
                "iterations_used": result.get("iterations", 0),
                "elapsed_seconds": result.get("elapsed_seconds", 0),
                "output": result.get("output", ""),
            }
        except Exception as e:
            logger.exception(f"❌ reflexion_loop falhou: {e}")
            return {
                "status": "error",
                "message": str(e),
                "prompt": prompt,
            }

    @mcp.tool()
    async def get_error_history(limit: int = 10) -> list:
        """Retorna histórico de erros armazenados na memória para prevenção.

        Args:
            limit: Número máximo de erros para retornar (default: 10)

        Returns:
            Lista de erros com contexto e correções aplicadas
        """
        from iaglobal.memory.memory_error import query_relevant_errors

        try:
            errors = await asyncio.to_thread(query_relevant_errors, "", limit=limit)

            return [
                {
                    "error_id": err.get("id", ""),
                    "error_type": err.get("error_type", ""),
                    "task_context": err.get("task_context", ""),
                    "correction_applied": err.get("correction_applied", ""),
                    "timestamp": err.get("timestamp", ""),
                }
                for err in errors
            ]
        except Exception as e:
            logger.exception(f"❌ get_error_history falhou: {e}")
            return []

else:
    from iaglobal.mcp.placeholder import MCPPlaceholder

    mcp = MCPPlaceholder()

# ==============================================================================
# FASTAPI GATEWAY
# ==============================================================================


def _create_fastapi_app() -> FastAPI:
    """Cria aplicação FastAPI para gateway HTTP."""
    load_env()

    app = FastAPI(
        title="IAGlobal MCP Unified Server",
        version="1.0.0",
        description="Servidor MCP unificado com gateway HTTP",
    )

    # Security
    security = HTTPBasic()
    valid_user = os.getenv("MCP_USER")
    valid_pass = os.getenv("MCP_PASSWORD")

    async def check_credentials(credentials: HTTPBasicCredentials = Depends(security)):
        if credentials.username != valid_user or credentials.password != valid_pass:
            logger.warning(f"Falha de autenticação: {credentials.username}")
            raise HTTPException(status_code=401, detail="Unauthorized")
        return credentials

    # Middleware CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Routes públicas
    @app.get("/health", response_model=Dict[str, str])
    async def health_check():
        """Health check do servidor."""
        invariants = _get_invariants()
        status = await invariants.check_all()
        return {
            "status": "✅ OK",
            "service": "mcp_unified",
            "metabolic_health": status["vault"]["status"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/metrics")
    async def get_metrics():
        """Métricas Prometheus."""
        metrics = []
        metrics.append("# HELP iaglobal_mcp_audit_score Score da última auditoria")
        metrics.append("# TYPE iaglobal_mcp_audit_score gauge")

        try:
            audit = await _get_agent().run_audit()
            metrics.append(f"iaglobal_mcp_audit_score {audit.score}")
        except:
            metrics.append("iaglobal_mcp_audit_score 0")

        invariants = await _get_invariants().check_all()
        for inv_name, data in invariants.items():
            safe_name = inv_name.replace(" ", "_").lower()
            metrics.append(f"# HELP iaglobal_invariant_{safe_name}_status Status")
            metrics.append(f"# TYPE iaglobal_invariant_{safe_name}_status gauge")
            value = 1 if data["status"] == "OK" else 0
            metrics.append(f"iaglobal_invariant_{safe_name}_status {value}")

        return PlainTextResponse("\n".join(metrics))

    @app.post("/jsonrpc", response_model=Dict[str, Any])
    async def json_rpc_handler(request: Request):
        """Handler JSON-RPC para compatibilidade."""
        try:
            payload = await request.json()
            method = payload.get("method")
            rpc_id = payload.get("id")

            if method == "initialize":
                result = await _get_agent().initialize()
            elif method == "tools/list":
                result = {"tools": _get_agent().get_tools()}
            elif method == "metabolic_audit":
                result = await _get_agent().run_audit()
            else:
                raise HTTPException(
                    status_code=400, detail=f"Method not found: {method}"
                )

            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": result,
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": payload.get("id") if payload else None,
                "error": {"code": -32603, "message": str(e)},
            }

    # Rotas protegidas
    @app.get("/audit", dependencies=[Depends(check_credentials)])
    async def run_audit():
        """Auditoria metabólica em tempo real (protegida)."""
        try:
            audit = await _get_agent().run_audit()

            await omni_mind.registrar_violação_lei(
                agente_id="mcp_unified",
                lei="Lei da Ordem",
                mensagem=f"Auditoria /audit - Score: {audit.score:.2f}",
            )

            return {
                "score": audit.score,
                "findings": audit.findings,
                "corrections": audit.corrections,
                "timestamp": audit.timestamp,
            }
        except Exception as e:
            logger.exception("Falha na auditoria")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/fix", dependencies=[Depends(check_credentials)])
    async def trigger_autocorrect():
        """Aciona correção automática (protegida)."""
        try:
            result = await _get_autocorrect().verificar_e_corrigir()

            await omni_mind.registrar_violação_lei(
                agente_id="mcp_unified",
                lei="Lei da Ordem",
                mensagem=f"Correção /fix - Correções: {len(result['correcoes'])}",
            )

            return {
                "status": "✅ Correção aplicada",
                "correcoes": result["correcoes"],
                "invariantes": result["invariantes"],
            }
        except Exception as e:
            logger.exception("Falha na autocorreção")
            raise HTTPException(status_code=500, detail=str(e))

    return app


# ==============================================================================
# ACETYCHOLINEBUS INTEGRATION
# ==============================================================================


async def _publish_metrics_loop():
    """Publica métricas no barramento a cada 30s."""
    bus = _get_bus()
    if not bus:
        return

    while True:
        try:
            invariants = await _get_invariants().check_all()
            ivm = _get_agent()._get_ivm()

            metrics = {
                "invariants": invariants,
                "ivm": ivm,
                "timestamp": time.time(),
            }

            msg = AgentMessage(
                sender="mcp_unified", recipient="mcp/metrics", payload=metrics
            )
            await bus.publish(msg)
            logger.debug(f"📊 Métricas publicadas: IVM={ivm:.2f}")
        except Exception as e:
            logger.error(f"❌ Falha ao publicar métricas: {e}")

        await asyncio.sleep(30)


async def _handle_autocorrect_command(payload: Dict[str, Any]):
    """Lida com comandos de correção do barramento."""
    bus = _get_bus()
    if not bus:
        return

    try:
        logger.info(f"⚡ Comando de correção recebido: {payload.get('target')}")
        result = await _get_autocorrect().verificar_e_corrigir()

        response = {
            "status": "success",
            "corrections": len(result["correcoes"]),
            "details": result["correcoes"],
        }

        response_msg = AgentMessage(
            sender="mcp_unified",
            recipient=f"mcp/autocorrect/response/{payload['command_id']}",
            payload=response,
        )
        await bus.publish(response_msg)
    except Exception as e:
        error_msg = AgentMessage(
            sender="mcp_unified",
            recipient=f"mcp/autocorrect/response/{payload['command_id']}",
            payload={"status": "error", "error": str(e)},
        )
        await bus.publish(error_msg)


async def _handle_invariant_violation(payload: Dict[str, Any]):
    """Lida com violações de invariantes reportadas."""
    bus = _get_bus()
    if not bus:
        return

    logger.warning(
        f"🚨 Violação detectada em {payload['invariant']}: {payload['alert']}"
    )

    await omni_mind.registrar_violação_lei(
        agente_id="mcp_unified",
        lei="Lei da Ordem",
        mensagem=f"Violação em {payload['invariant']}: {payload['alert']}",
    )

    if payload["status"] == "VIOLADA":
        await _get_autocorrect().verificar_e_corrigir()


async def _setup_bus_integration():
    """Configura integração com AcetylcholineBus."""
    bus = _get_bus()
    if not bus:
        logger.warning("AcetylcholineBus não disponível - skip integração")
        return

    try:
        # Publicar métricas
        asyncio.create_task(_publish_metrics_loop())

        # Escutar comandos
        bus.subscribe("mcp/autocorrect", _handle_autocorrect_command)
        bus.subscribe("invariants/violation", _handle_invariant_violation)

        logger.info("✅ MCP Unified integrado ao AcetylcholineBus")
    except Exception as e:
        logger.error(f"❌ Falha ao integrar com AcetylcholineBus: {e}")


# ==============================================================================
# SERVER LIFECYCLE
# ==============================================================================


async def run_server(host: str = "127.0.0.1", port: int = 8100, sse: bool = True):
    """Inicia servidor MCP via SSE ou stdio."""
    if FastMCP is None:
        logger.error("FastMCP não instalado. Execute: pip install mcp")
        return

    logger.info(f"🔮 Iniciando MCP Unified Server em {host}:{port}")

    await _ensure_phase1()
    snap = _boot_snapshot()
    logger.info(
        "⚡ MCP pronto para handshake (phase1=%s, phase2_running=%s)",
        snap["phase1_done"],
        snap["phase2_running"],
    )

    # Setup integração bus
    await _setup_bus_integration()

    if sse:
        await mcp.run_sse(host=host, port=port)
    else:
        await mcp.run_stdio_async()


def run_http_server(host: str = "127.0.0.1", port: int = 8101):
    """Inicia servidor HTTP gateway."""
    import uvicorn

    app = _create_fastapi_app()
    logger.info(f"🌐 HTTP Gateway em http://{host}:{port}")

    uvicorn.run(app, host=host, port=port, log_level="info")


# ==============================================================================
# SINGLETON GLOBAL PARA IMPORTAÇÃO
# ==============================================================================


def get_app() -> FastAPI:
    """Retorna FastAPI app para uso em ASGI."""
    global _fastapi_app
    if _fastapi_app is None:
        _fastapi_app = _create_fastapi_app()
    return _fastapi_app


# ==============================================================================
# CLI ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="MCP Server Unificado iaglobal")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host do servidor (padrão: 127.0.0.1)"
    )
    parser.add_argument("--port", type=int, default=8100, help="Porta do servidor")
    parser.add_argument(
        "--http-port", type=int, default=8101, help="Porta HTTP gateway"
    )
    parser.add_argument(
        "--mode", choices=["sse", "stdio", "http", "both"], default="both"
    )
    args = parser.parse_args()

    load_env()
    logger.info(
        f"🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136"
    )
    logger.info("🔮 MCP Unified Server inicializando...")

    if args.mode in ("sse", "both"):
        # Rodar ambos servidores em paralelo
        async def run_both():
            tasks = []
            if args.mode == "both":
                # HTTP gateway em thread separada
                import threading

                http_thread = threading.Thread(
                    target=run_http_server,
                    kwargs={"host": args.host, "port": args.http_port},
                    daemon=True,
                )
                http_thread.start()
                logger.info(f"✅ HTTP Gateway iniciado em {args.http_port}")

            tasks.append(run_server(host=args.host, port=args.port, sse=True))
            await asyncio.gather(*tasks)

        try:
            asyncio.run(run_both())
        except KeyboardInterrupt:
            logger.info("🛑 Servidor encerrado pelo usuário")
    elif args.mode == "stdio":
        asyncio.run(run_server(sse=False))
    elif args.mode == "http":
        run_http_server(host=args.host, port=args.http_port)
