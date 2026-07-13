# iaglobal/cli/life_signals.py

import argparse
import json
import sys
from pathlib import Path

from iaglobal.utils.life_signal_collector import collector


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Life Signals — Telemetria de funções instrumentadas"
    )
    parser.add_argument(
        "command",
        choices=["status", "report", "clear", "export"],
        help="Comando: status (uma função), report (todas), clear (limpar), export (salvar JSON)",
    )
    parser.add_argument(
        "function",
        nargs="?",
        help="Nome da função (apenas para status)",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Arquivo de persistência (default: automático do bootstrap)",
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=3600,
        help="Idade máxima para considerar função viva (segundos, default: 3600)",
    )

    args = parser.parse_args()

    # Se não foi passado --file mas o collector já tem um, reutiliza
    target_file = args.file
    if target_file is None:
        # Tenta recuperar do handler instalado
        handler = getattr(collector, "_log_handler", None)
        if handler and hasattr(handler, "log_file") and handler.log_file:
            target_file = handler.log_file

    # Instala o collector se houver arquivo-alvo
    if target_file and not collector._log_handler:
        collector.install(target_file)

    try:
        if args.command == "status":
            if not args.function:
                print("ERRO: informe o nome da função", file=sys.stderr)
                return 1
            status = collector.get_status(args.function, max_age_seconds=args.max_age)
            print(json.dumps(status, indent=2, ensure_ascii=False))
            return 0

        elif args.command == "report":
            report = collector.get_report()
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0

        elif args.command == "clear":
            collector.clear()
            print("Sinais limpos.")
            return 0

        elif args.command == "export":
            path = target_file or Path("iaglobal/memory/data/life_signals.json")
            collector.save_to_file(path)
            print(f"Sinais exportados para {path}")
            return 0

    finally:
        if target_file:
            collector.uninstall()

    return 0


if __name__ == "__main__":
    sys.exit(main())
