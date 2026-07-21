#!/usr/bin/env python3
# iaglobal/scripts/architecture_gate.py
"""
Architecture Regression Gate — Compara auditoria atual com baseline.

Uso:
    python -m iaglobal.scripts.architecture_gate

Retorna:
    0 se sem regressões
    1 se novas colisões ou símbolos não baselineados
"""

import json
import sys
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent.parent
BASELINE_PATH = PROJECT_DIR / "architecture" / "collision_baseline.json"


def run_audit() -> list:
    """Executa auditoria atual e retorna JSON."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "iaglobal.auditoria_arquitetural",
            "--json",
            "--include-functions",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_DIR,
    )
    return json.loads(result.stdout)


def load_baseline() -> dict:
    """Carrega baseline persistida."""
    with open(BASELINE_PATH) as f:
        return json.load(f)


def check_regressions(current: list, baseline: dict) -> tuple:
    """Compara atual com baseline e retorna diferenças."""
    current_names = {c["name"] for c in current}
    baseline_names = set(baseline.keys())

    new_symbols = current_names - baseline_names
    removed_symbols = baseline_names - current_names
    changed_classifications = []

    for name in current_names & baseline_names:
        curr_class = next(c["classification"] for c in current if c["name"] == name)
        base_class = baseline[name]["classification"]
        if curr_class != base_class:
            changed_classifications.append(
                {
                    "name": name,
                    "before": base_class,
                    "after": curr_class,
                }
            )

    return new_symbols, removed_symbols, changed_classifications


def main() -> int:
    current = run_audit()
    baseline = load_baseline()

    new_symbols, removed_symbols, changed = check_regressions(current, baseline)

    print("=== ARCHITECTURE REGRESSION GATE ===")
    print(f"Baseline: {len(baseline)} símbolos")
    print(f"Atual:    {len(current)} símbolos")
    print()

    if new_symbols:
        print(f"🆕 NOVOS SÍMBOLOS ({len(new_symbols)}):")
        for s in sorted(new_symbols):
            print(f"   + {s}")
        print()

    if removed_symbols:
        print(f"🗑️  SÍMBOLOS REMOVIDOS ({len(removed_symbols)}):")
        for s in sorted(removed_symbols):
            print(f"   - {s}")
        print()

    if changed:
        print(f"🔄 CLASSIFICAÇÕES ALTERADAS ({len(changed)}):")
        for c in changed:
            print(f"   {c['name']}: {c['before'][:50]}... → {c['after'][:50]}...")
        print()

    if not new_symbols and not removed_symbols and not changed:
        print("✅ SEM REGRESSÕES ARQUITETURAIS")
        return 0
    else:
        print("⚠️  REGRESSÕES DETECTADAS")
        print()
        print("Ações possíveis:")
        print("  1. Resolver colisões novas")
        print(
            "  2. Atualizar baseline: python -m iaglobal.auditoria_arquitetural --json > architecture/collision_baseline.json"
        )
        print("  3. Justificar mudança no PR")
        return 1


if __name__ == "__main__":
    sys.exit(main())
