# iaglobal/cli/main.py

import argparse
import sys

from iaglobal.cli.bootstrap import bootstrap
from iaglobal.core.env_loader import load_env
from iaglobal.cli.output import OutputRenderer, HistoryRenderer, ReplayRenderer
from iaglobal.cli.status import Dashboard
from iaglobal.events import store as decision_store
from iaglobal.providers.provider_metrics import metrics
from iaglobal.graphs.credit import CreditAssignmentEngine


def run_cli():
    parser = argparse.ArgumentParser(
        description="IAGlobal Runtime CLI"
    )

    parser.add_argument(
        "prompt",
        type=str,
        nargs="*",
        help="Tarefa ou prompt para execução"
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Modo interativo (REPL)"
    )

    parser.add_argument(
        "command",
        type=str,
        nargs="?",
        help="Comando especial (status, history, replay, evolution-lab)"
    )

    parser.add_argument(
        "--step",
        type=str,
        default=None,
        help="Filtrar por etapa (com history)"
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="Listar execuções recentes (com history)"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Estatísticas agregadas (com history, replay)"
    )
    parser.add_argument(
        "--model-metrics",
        action="store_true",
        help="Exibir métricas de performance de modelos (override history/replay)"
    )

    parser.add_argument(
        "--what-if",
        type=str,
        default=None,
        help="Modelo alternativo para simulação (com replay)"
    )

    parser.add_argument(
        "--train-bandit",
        action="store_true",
        help="Treinar bandit com histórico real (com replay)"
    )

    parser.add_argument(
        "--explain",
        action="store_true",
        help="Explicar execução com LLM (com replay)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignorar cache e forçar regeneração"
    )

    args, unknown = parser.parse_known_args()

    load_env()

    decision_store.start()

    # ── replay command ──
    if args.command == "replay" or (args.prompt and args.prompt[0] == "replay"):
        rest = args.prompt[1:] if args.prompt else []
        exec_id = args.what_if if args.what_if and not rest else (rest[0] if rest and not rest[0].startswith("--") else None)

        if args.explain or (rest and "--explain" in rest):
            if not exec_id:
                print("\n  ❌ Informe o execution_id para explain\n")
                return
            replay = DecisionReplaySystem()
            result = replay.explain(exec_id)
            if result:
                ReplayRenderer.render_explain(result)
            else:
                print(f"\n  ❌ Execução {exec_id} não encontrada\n")
            return

        if args.train_bandit or (rest and "--train-bandit" in rest):
            if not exec_id:
                print("\n  ❌ Informe o execution_id para treinar o bandit\n")
                return
            replay = DecisionReplaySystem()
            credit = CreditAssignmentEngine()
            result = replay.train_bandit(exec_id, credit)
            ReplayRenderer.render_train_result(result)
            return

        if args.what_if:
            if not exec_id:
                print("\n  ❌ Informe o execution_id para what-if\n")
                return
            replay = DecisionReplaySystem()
            result = replay.what_if(exec_id, args.what_if)
            if result:
                ReplayRenderer.render_what_if(result)
            else:
                print(f"\n  ❌ Execução {exec_id} não encontrada\n")
            return

        if args.stats or (rest and "--stats" in rest):
            if exec_id:
                replay = DecisionReplaySystem()
                summary = replay.summary(exec_id)
                if summary:
                    ReplayRenderer.render_summary(summary)
                else:
                    print(f"\n  ❌ Execução {exec_id} não encontrada\n")
            else:
                _show_history_stats()
            return

        if args.model_metrics:
            model_stats = metrics.get_model_stats()
            provider_stats = metrics.get_provider_stats()
            print("\n" + metrics.format_metrics_report(model_stats, "Model Performance"))
            print("\n" + metrics.format_metrics_report(provider_stats, "Provider Performance"))
            return

        if exec_id:
            replay = DecisionReplaySystem()
            summary = replay.summary(exec_id)
            if summary:
                ReplayRenderer.render_summary(summary)
            else:
                print(f"\n  ❌ Execução {exec_id} não encontrada\n")
        else:
            _show_history_list()
        return

    # ── history command ──
    if args.command == "history" or (args.prompt and args.prompt[0] == "history"):
        rest = args.prompt[1:] if args.prompt else []

        if args.stats or (rest and rest[0] == "--stats"):
            _show_history_stats()
            return

        if args.list or (rest and rest[0] == "--list"):
            _show_history_list()
            return

        step_filter = args.step
        if not step_filter and rest:
            for i, r in enumerate(rest):
                if r == "--step" and i + 1 < len(rest):
                    step_filter = rest[i + 1]
                    break

        exec_id = None
        if rest and not rest[0].startswith("--"):
            exec_id = rest[0]

        if step_filter and exec_id:
            rows = decision_store.query(execution_id=exec_id, step=step_filter)
            HistoryRenderer.render_steps(rows, step_filter)
        elif exec_id:
            rows = decision_store.replay(exec_id)
            HistoryRenderer.render_execution(rows, exec_id)
        elif step_filter:
            rows = decision_store.query(step=step_filter)
            HistoryRenderer.render_steps(rows, step_filter)
        else:
            _show_history_list()
        return

    # ── evolution-lab command ──
    if args.command == "evolution-lab" or args.command == "evolution_lab" or \
       (args.prompt and args.prompt[0] in ("evolution-lab", "evolution_lab")):
        from iaglobal.cli.evolution_lab import run_evolution_lab
        rest = args.prompt[1:] if args.prompt else []
        # args.command may also contain a subcommand when unknown flags are present
        if args.command and args.command not in ("evolution-lab", "evolution_lab"):
            rest = [args.command] + rest
        # Put unknown global flags BEFORE the subcommand
        sub_argv = ["evolution-lab"] + unknown + rest
        sys.argv = sub_argv
        run_evolution_lab()
        return

    # ── status command ──
    orch = bootstrap.initialize()
    if args.command == "status" or (args.prompt and args.prompt[0] == "status"):
        Dashboard.show_status(orch)
        return

    if args.prompt:
        if args.prompt[0] == "run" and len(args.prompt) > 1:
            prompt = " ".join(args.prompt[1:])
        else:
            prompt = " ".join(args.prompt)
        print(f"🛰️ [IAGLOBAL] Processando tarefa...\n")
        result = orch.run(prompt, force=args.force)
        OutputRenderer.render(result)
        return

    if args.interactive:
        print("\nIAGlobal Interactive Mode")
        print("Digite 'exit' para sair\n")

        while True:
            try:
                prompt = input(">>> ")
                if prompt.lower().strip() in ["exit", "quit"]:
                    break
                print(f"🛰️ [IAGLOBAL] Processando tarefa...\n")
                result = orch.run(prompt, force=args.force)
                OutputRenderer.render(result)
                print()
            except KeyboardInterrupt:
                print("\nEncerrando...")
                break
    else:
        parser.print_help()


def _show_history_stats():
    total = decision_store.count()
    steps = [
        "memory_lookup", "candidate_selection", "model_selection",
        "lock", "execution_metrics", "memory_store", "evolution_check",
        "task_normalization",
    ]
    by_step = {}
    for s in steps:
        c = decision_store.count(step=s)
        if c:
            by_step[s] = c
    HistoryRenderer.render_stats({"total": total, "by_step": by_step})


def _show_history_list():
    from iaglobal.memory.db_manager import db
    conn = db._get_conn()
    try:
        cursor = conn.execute(
            "SELECT execution_id, COUNT(*), MAX(created_at) "
            "FROM decision_events GROUP BY execution_id "
            "ORDER BY MAX(created_at) DESC LIMIT 20"
        )
        rows = cursor.fetchall()
        entries = [(r[0], r[1], r[2]) for r in rows]
        HistoryRenderer.render_list(entries)
    finally:
        conn.close()
