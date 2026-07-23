# iaglobal/cli/main.py

import os
import sys
import logging
import asyncio
import subprocess


from iaglobal.utils.logger import start_session_log, stop_session_log

logger = logging.getLogger("ia-global")


async def run_cli():
    """Ponto de entrada assíncrono para o CLI."""
    start_session_log()
    from iaglobal.utils.logger import logger

    log_path = "Desconhecido"
    try:
        for handler in logger.handlers:
            if hasattr(handler, "baseFilename"):
                log_path = handler.baseFilename
                break

        await _run_cli_impl()

    except Exception as e:
        import traceback

        print(f"\n❌ CRITICAL ERROR: {e}")
        logger.exception("Falha crítica durante a execução do CLI")
        traceback.print_exc()

    finally:
        # Flush de métricas antes do shutdown (garante persistência)
        try:
            from iaglobal.providers.provider_metrics import metrics

            metrics.flush()
        except Exception:
            pass
        # Fecha sessões aiohttp antes do shutdown
        try:
            from iaglobal.providers.async_http import close_all_sessions

            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    await close_all_sessions()
            except RuntimeError:
                asyncio.run(close_all_sessions())
        except Exception:
            pass
        print(f"\n📝 Log detalhado em: {log_path}")
        stop_session_log()


def _ensure_searxng():
    logger.debug("[SEARXNG] Usando instância pública (paulgo.io). Nenhum container local necessário.")


async def _run_cli_impl():
    import argparse
    import asyncio
    from iaglobal.core.env_loader import load_env
    from iaglobal.cli.bootstrap import bootstrap
    from iaglobal.events.replay import DecisionReplaySystem

    # 1. Carregamento de ambiente
    load_env()

    # 2. Configuração de Argumentos
    parser = argparse.ArgumentParser(description="IAGlobal Runtime CLI")
    parser.add_argument(
        "command",
        type=str,
        nargs="?",
        help="Comando (run, status, replay, dashboard-sleep, etc)",
    )
    parser.add_argument("prompt", type=str, nargs="*", help="Tarefa ou prompt")
    parser.add_argument("--force", action="store_true", help="Forcar execucao")
    parser.add_argument("--batch-what-if", type=str, help="IDs para analise em lote")
    parser.add_argument("--model", type=str, help="Modelo para analise")
    parser.add_argument(
        "--refresh",
        type=int,
        default=10,
        help="Intervalo de atualizacao em segundos (para dashboard-sleep)",
    )
    parser.add_argument(
        "--continuous", action="store_true", help="Modo continuo para auditoria MCP"
    )
    parser.add_argument("--interactive", action="store_true", help="Modo interativo")

    args, unknown = parser.parse_known_args()

    # 3. Inicialização Centralizada
    # bootstrap.initialize() é assíncrono — retorna o Orchestrator diretamente
    orch = await bootstrap.initialize()

    # Usa o bandit e credit_engine do orchestrator (singleton global)
    credit_engine = orch.bandit.credit_engine
    bandit = orch.bandit

    # 4. Execução Assíncrona
    if args.command == "dashboard-sleep":
        from iaglobal.dashboard.metabolic_sleep_dashboard import MetabolicSleepDashboard

        dashboard = MetabolicSleepDashboard()
        dashboard.refresh_interval = args.refresh
        print(f"🌙 Iniciando Dashboard de Sono Metabólico (refresh: {args.refresh}s)")
        await dashboard.iniciar()
    elif args.command == "check-invariants":
        from iaglobal.metabolism.metabolic_invariants import MetabolicInvariants

        invariants = MetabolicInvariants()
        result = await invariants.check_all()
        print("🔍 INVARIANTES DE SAÚDE METABÓLICA")
        print("=" * 50)
        for invariant, status in result.items():
            print(f"{invariant.upper()}: {status['status']}")
            if "alert" in status:
                print(f" 🚨 {status['alert']}")
        print("=" * 50)

    elif args.command == "check-health":
        from iaglobal.metabolism.metabolic_metrics import MetabolicMetrics
        from iaglobal.utils.ansi_colors import ANSI

        metrics = MetabolicMetrics()
        health_data = await metrics.collect_health_data()

        print(
            f"{ANSI.BOLD}{ANSI.CYAN}🌡️ DASHBOARD METABÓLICO (T+{health_data.uptime_min}min){ANSI.RESET}"
        )
        print("=" * 80)
        print(
            f"{ANSI.BOLD}| INVARIANTE{' ' * 14} | STATUS       | VALOR         | ÚLTIMA CORREÇÃO     |{ANSI.RESET}"
        )
        print(f"|{'-' * 21}|{'-' * 12}|{'-' * 14}|{'-' * 21}|")

        status_colors = {"OK": ANSI.GREEN, "AVISO": ANSI.YELLOW, "VIOLADA": ANSI.RED}

        for invariant, data in health_data.invariants.items():
            status_color = status_colors.get(data["status"], ANSI.WHITE)
            status_display = f"{status_color}{data['status'].ljust(12)}{ANSI.RESET}"

            value_display = str(data.get("value", "N/A")).ljust(13)
            last_correction = data.get("last_correction", "Nenhuma")
            if isinstance(last_correction, str):
                correction_display = last_correction.ljust(20)
            else:
                correction_display = (
                    f"{last_correction['acao']} ({last_correction['ago']} atrás)".ljust(
                        20
                    )
                )

            print(
                f"| {invariant.ljust(20)} | {status_display} | {value_display} | {correction_display} |"
            )

            if "alert" in data and data["alert"]:
                alert_len = len(data["alert"])
                padding = " " * (13 - alert_len) if alert_len <= 13 else ""
                print(
                    f"| {' ' * 20} | {' ' * 12} | {ANSI.RED}🚨 {data['alert']}{ANSI.RESET}{padding} | {' ' * 21} |"
                )

        # Additional System Metrics
        print(f"|{'-' * 21}|{'-' * 12}|{'-' * 14}|{'-' * 21}|")
        for metric, value in health_data.system_metrics.items():
            status = "OK" if value["healthy"] else "VIOLADA"
            status_color = status_colors.get(status, ANSI.WHITE)
            status_display = f"{status_color}{status.ljust(12)}{ANSI.RESET}"

            value_display = str(value["value"]).ljust(13)
            print(
                f"| {metric.ljust(20)} | {status_display} | {value_display} | {'N/A'.ljust(20)} |"
            )

        print("=" * 80)

        if health_data.suggestions:
            print(f"\n{ANSI.BOLD}{ANSI.CYAN}📊 SUGESTÕES:{ANSI.RESET}")
            for suggestion in health_data.suggestions:
                print(f"- {suggestion}")

        print()

    elif args.command == "autocorrect":
        from iaglobal.metabolism.metabolic_autocorrect import MetabolicAutocorrect

        autocorrect = MetabolicAutocorrect()
        result = await autocorrect.verificar_e_corrigir()
        print("🛠️ AUTO-CORREÇÃO DE INVARIANTES")
        print("=" * 50)
        for invariant, status in result["invariantes"].items():
            print(f"{invariant.upper()}: {status['status']}")
            if "alert" in status:
                print(f"  🚨 {status['alert']}")
        if result["correcoes"]:
            print("\n🔧 CORREÇÕES APLICADAS:")
            for invariant, correcao in result["correcoes"].items():
                print(f"  {invariant.upper()}: {correcao['acao']}")
        print("=" * 50)
    elif args.command == "run" and args.prompt:
        task = " ".join(args.prompt)
        print(f"🛰️ [IAGLOBAL] Processando tarefa: {task}...")

        await asyncio.to_thread(_ensure_searxng)

        # Aguarda a pipeline async
        result = await orch.pipeline.execute(task, force=args.force)

        from iaglobal.cli.output import OutputRenderer

        # Renderização delegada para thread se for bloqueante
        await asyncio.to_thread(OutputRenderer.render, result)
        return

    elif args.batch_what_if and args.model:
        # Uso do método de lote no DecisionReplaySystem
        ids = args.batch_what_if.split(",")
        print(f"📊 [REPLAY] Analisando lote de {len(ids)} execuções...")

        report = await asyncio.to_thread(
            DecisionReplaySystem.batch_compare_what_if, ids, args.model
        )

        print(f"✅ Relatório de Lote:")
        print(f"   - Modelo Testado: {report.get('model_tested', 'N/A')}")
        print(
            f"   - Consistência (Melhoria): {report.get('consistency_score', 0) * 100:.1f}%"
        )
        print(
            f"   - Média de melhoria de score: {report.get('average_score_improvement', 0)}"
        )
        return

    # ── replay command ──

    logger.info("✅ Sistema cognitivo pronto.")

    if args.command == "replay" or (args.prompt and args.prompt[0] == "replay"):
        from iaglobal.cli.output import ReplayRenderer
        from iaglobal.providers.provider_metrics import metrics

        rest = args.prompt[1:] if args.prompt else []
        exec_id = getattr(args, "what_if", None) or (
            rest[0] if rest and not rest[0].startswith("--") else None
        )

        # 1. Métricas de Modelo
        if getattr(args, "model_metrics", False):
            m_stats, p_stats = metrics.get_model_stats(), metrics.get_provider_stats()
            print("\n" + metrics.format_metrics_report(m_stats, "Model Performance"))
            print("\n" + metrics.format_metrics_report(p_stats, "Provider Performance"))
            return

        # 2. Comandos que exigem ID de execução
        if any(
            [
                getattr(args, "explain", False),
                getattr(args, "train_bandit", False),
                getattr(args, "what_if", False),
                getattr(args, "stats", False),
                exec_id,
            ]
        ):
            if not exec_id:
                print("\n  ❌ Erro: Informe o execution_id para este comando.\n")
                return

            replay = DecisionReplaySystem()
            # IMPORTANTE: Reutilizamos a instância credit_engine já existente
            credit = credit_engine

            # 3. Execução dos Subcomandos
            # Nota: O uso de to_thread é mantido para operações síncronas pesadas (I/O)
            if args.explain:
                result = await asyncio.to_thread(replay.explain, exec_id, credit)
                ReplayRenderer.render_explain(result) if result else print(
                    f"❌ Erro: {exec_id} não encontrado"
                )

            elif args.train_bandit or (rest and "--train-bandit" in rest):
                # Passamos o bandit que recuperamos no início
                result = await asyncio.to_thread(
                    replay.train_bandit, exec_id, credit, bandit
                )
                ReplayRenderer.render_train_result(result)

            elif args.what_if:
                result = await asyncio.to_thread(replay.what_if, exec_id, args.what_if)
                ReplayRenderer.render_what_if(result) if result else print(
                    f"\n  ❌ Execução {exec_id} não encontrada\n"
                )

            elif args.stats or (rest and "--stats" in rest):
                summary = await asyncio.to_thread(replay.summary, exec_id)
                ReplayRenderer.render_summary(summary) if result else print(
                    f"\n  ❌ Execução {exec_id} não encontrada\n"
                )

            elif exec_id:
                summary = await asyncio.to_thread(replay.summary, exec_id)
                ReplayRenderer.render_summary(summary) if result else print(
                    f"\n  ❌ Execução {exec_id} não encontrada\n"
                )
        else:
            await asyncio.to_thread(_show_history_list)

        return

    # ── history command ──
    if args.command == "history" or (args.prompt and args.prompt[0] == "history"):
        from iaglobal.events import store as decision_store
        from iaglobal.cli.output import HistoryRenderer

        # Garante que o banco de dados esteja iniciado de forma não bloqueante
        await asyncio.to_thread(decision_store.start)

        rest = args.prompt[1:] if args.prompt else []

        # 1. Comandos de visualização rápida
        if getattr(args, "stats", False) or (rest and "--stats" in rest):
            await asyncio.to_thread(_show_history_stats)
            return

        if getattr(args, "list", False) or (rest and "--list" in rest):
            await asyncio.to_thread(_show_history_list)
            return

        # 2. Extração de filtros
        step_filter = getattr(args, "step", None)
        if not step_filter and "--step" in rest:
            try:
                step_filter = rest[rest.index("--step") + 1]
            except (ValueError, IndexError):
                pass

        exec_id = next((r for r in rest if not r.startswith("--")), None)

        # 3. Execução da query (Encapsulando operações de I/O bloqueante)
        if step_filter and exec_id:
            rows = await asyncio.to_thread(
                decision_store.query, execution_id=exec_id, step=step_filter
            )
            HistoryRenderer.render_steps(rows, step_filter)
        elif exec_id:
            rows = await asyncio.to_thread(decision_store.replay, exec_id)
            HistoryRenderer.render_execution(rows, exec_id)
        elif step_filter:
            rows = await asyncio.to_thread(decision_store.query, step=step_filter)
            HistoryRenderer.render_steps(rows, step_filter)
        else:
            await asyncio.to_thread(_show_history_list)

        return

    # ── evolution-lab command ──
    if args.command in ("evolution-lab", "evolution_lab") or (
        args.prompt and args.prompt[0] in ("evolution-lab", "evolution_lab")
    ):
        from iaglobal.cli.evolution_lab import run_evolution_lab

        rest = args.prompt[1:] if args.prompt else []
        if args.command and args.command not in ("evolution-lab", "evolution_lab"):
            rest = [args.command] + rest

        sys.argv = ["evolution-lab"] + unknown + rest
        # Executamos o lab em uma thread dedicada para não travar o loop async da CLI
        await asyncio.to_thread(lambda: run_evolution_lab())
        return

    # ── life-signals command ──
    if args.command == "life-signals" or (
        args.prompt and args.prompt[0] == "life-signals"
    ):
        from iaglobal.cli.life_signals import main as life_signals_main

        rest = args.prompt[1:] if args.prompt else []
        sys.argv = ["life-signals"] + unknown + rest
        await asyncio.to_thread(life_signals_main)
        return

    # ── learn/aprender command ──
    if args.command in ("learn", "aprender") or (
        args.prompt and args.prompt[0] in ("learn", "aprender")
    ):
        from iaglobal.cli.learn import run_learn

        await run_learn(args, orch)
        return

    # ── status command ──
    if args.command == "status" or (args.prompt and args.prompt[0] == "status"):
        from iaglobal.cli.status import Dashboard

        # Dashboard costuma ser puramente visual/leitura
        await asyncio.to_thread(Dashboard.show_status, orch)
        return

    # ── mcp-audit command ──
    elif args.command == "mcp-audit":
        from iaglobal.mcp.mcp_agent import MCPAgent

        mcp = MCPAgent()
        audit = await mcp.run_audit()
        mcp._print_audit_report(audit)

        if getattr(args, "continuous", False):
            print("\n⏳ Iniciando auditoria contínua (Ctrl+C para sair)...")
            await mcp.run_continuous(interval=300)
        return

    # ── Execução de tarefa (run) ──
    if args.prompt:
        from iaglobal.cli.output import OutputRenderer

        prompt_text = (
            " ".join(args.prompt[1:])
            if args.prompt[0] == "run"
            else " ".join(args.prompt)
        )

        print(f"🛰️ [IAGLOBAL] Processando tarefa...\n")

        await asyncio.to_thread(_ensure_searxng)

        # Ponto de execução assíncrono principal
        result = await orch.pipeline.execute(
            prompt_text, force=getattr(args, "force", False)
        )

        await asyncio.to_thread(OutputRenderer.render, result)
        # OutputRenderer.render(result)  <-- Removido duplicado

        return

    # ── Modo Interativo ──
    if getattr(args, "interactive", False):
        from iaglobal.cli.output import OutputRenderer

        await asyncio.to_thread(_ensure_searxng)

        print("\nIAGlobal Interactive Mode | Digite 'exit' para sair\n")
        while True:
            try:
                # input() é bloqueante, usamos to_thread para não travar o loop
                prompt = await asyncio.to_thread(input, ">>> ")
                if prompt.lower().strip() in ["exit", "quit"]:
                    break
                print(f"🛰️ [IAGLOBAL] Processando...\n")

                # Execução assíncrona no modo interativo
                result = await orch.pipeline.execute(
                    prompt, force=getattr(args, "force", False)
                )
                await asyncio.to_thread(OutputRenderer.render, result)
                # OutputRenderer.render(result) <-- Removido duplicado
                print()
            except KeyboardInterrupt:
                print("\nEncerrando...")
                break
    else:
        parser.print_help()


# ====================================================================================


def _show_history_stats():
    """
    Exibe estatísticas agregadas do histórico de decisões.
    Executada em uma thread separada para não bloquear o loop async.
    """
    from iaglobal.events import store as decision_store
    from iaglobal.cli.output import HistoryRenderer
    from iaglobal.events.event_types import PipelineStep

    # Inicia o store se necessário
    decision_store.start()

    # Operações de banco de dados bloqueantes
    total = decision_store.count()

    by_step = {}
    for step in PipelineStep.ALL:
        count = decision_store.count(step=step)
        if count:
            by_step[step] = count

    # Renderização (assumindo que seja uma operação rápida de CPU/Terminal)
    HistoryRenderer.render_stats({"total": total, "by_step": by_step})


# ====================================================================================


def _show_history_list():
    """
    Exibe as 20 execuções mais recentes, garantindo o fechamento da conexão.
    """
    from iaglobal.memory.db_manager import db
    from iaglobal.cli.output import HistoryRenderer

    # Usamos o gerenciador de contexto para garantir que a conexão feche sozinha
    try:
        # A boa prática é tratar db._get_conn() como um recurso temporário
        with db._get_conn() as conn:
            cursor = conn.execute(
                "SELECT execution_id, COUNT(*), MAX(created_at) "
                "FROM decision_events "
                "GROUP BY execution_id "
                "ORDER BY MAX(created_at) DESC "
                "LIMIT 20"
            )
            rows = cursor.fetchall()

            entries = [(r[0], r[1], r[2]) for r in rows]

            if not entries:
                print("\n  ℹ️ Nenhuma execução encontrada no histórico.\n")
                return

            HistoryRenderer.render_list(entries)

    except Exception as e:
        print(f"\n  ❌ Erro ao acessar histórico: {e}\n")


# ====================================================================================

# ... no lugar da chamada atual run_cli() ...


def main():
    """Entry point síncrono para console_scripts."""
    try:
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
