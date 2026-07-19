# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
dashboard_congestion — Observabilidade em tempo real do Tribunal Cognitivo.

Lê os JSONL de telemetria (intervenções, correções, congestão) via streaming
(mesma técnica do threshold_analyzer: O(1) memória) e imprime um snapshot
da "respiração" da colônia: carga por tier, precisão do Sentinela, alertas
ativos. Usado para acompanhar o stress test de 81 nós sem sobrecarregar o
sistema (apenas leitura offline dos logs).

Uso:
  python -m iaglobal.metabolism.dashboard_congestion [--watch N]
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.metabolism.dashboard")

JOL_DATA_DIR = Path(__file__).parent.parent / "memory" / "data" / "jol"
INTERVENTIONS = JOL_DATA_DIR / "jol_interventions.jsonl"
CORRECTIONS = JOL_DATA_DIR / "jol_corrections.jsonl"
CONGESTION = JOL_DATA_DIR / "jol_congestion.jsonl"

TIERS = ["glm4", "qwen", "lfm"]


def _stream(path: Path):
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield __import__("json").loads(line)
            except Exception:
                continue


def snapshot() -> Dict[str, Any]:
    """Coleta snapshot instantâneo da colônia a partir dos JSONL."""
    total_interv = total_corr = approved = rejected = cong_alerts = 0
    tier_rej: Dict[str, int] = {t: 0 for t in TIERS}
    tier_samples: Dict[str, int] = {t: 0 for t in TIERS}
    last_cong: Dict[str, Any] = {}

    for _ in _stream(INTERVENTIONS):
        total_interv += 1
    for r in _stream(CORRECTIONS):
        total_corr += 1
        if r.get("status") == "approved":
            approved += 1
        elif r.get("status") == "rejected":
            rejected += 1
    for r in _stream(CONGESTION):
        cong_alerts += 1
        t = r.get("tier", "unknown")
        if t in tier_rej:
            tier_rej[t] += int(r.get("rejections", 0))
            tier_samples[t] += 1
            last_cong[t] = r

    precision = round(approved / total_interv * 100, 1) if total_interv else 0.0

    return {
        "interventions": total_interv,
        "corrections": total_corr,
        "approved": approved,
        "rejected": rejected,
        "precision_pct": precision,
        "congestion_alerts": cong_alerts,
        "tier_rejections": tier_rej,
        "tier_samples": tier_samples,
        "last_congestion": last_cong,
    }


def render(s: Dict[str, Any]) -> str:
    lines = []
    lines.append("=" * 58)
    lines.append("  🧬 iaglobal — DASHBOARD DE HOMEOSTASE (Tribunal Cognitivo)")
    lines.append("=" * 58)
    lines.append(f"  Sentinela: intervenções={s['interventions']}  "
                 f"correções={s['corrections']}  precisão={s['precision_pct']}%")
    lines.append(f"  Falso-positivos (rejeições): {s['rejected']}  "
                 f"aprovadas: {s['approved']}")
    lines.append(f"  Alertas de congestão (total): {s['congestion_alerts']}")
    lines.append("-" * 58)
    lines.append("  TIER        REJEC.   AMOSTRAS   ÚLTIMO USO%   STATUS")
    for t in TIERS:
        rej = s["tier_rejections"][t]
        samp = s["tier_samples"][t]
        last = s["last_congestion"].get(t)
        usage = f"{last.get('usage_pct', 0):.1f}" if last else "—"
        status = "🔥 CONGESTIONADO" if last else "✅ estável"
        lines.append(f"  {t:<10}  {rej:<7}  {samp:<9}  {usage:>8}%   {status}")
    lines.append("=" * 58)
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Dashboard de congestão do iaglobal")
    ap.add_argument("--watch", type=int, default=0,
                    help="Segundos entre refreshes (0 = snapshot único)")
    args = ap.parse_args()

    try:
        if args.watch <= 0:
            print(render(snapshot()))
            return 0
        while True:
            # Clear screen de forma portável
            print("\033[2J\033[H", end="")
            print(render(snapshot()))
            print(f"\n[watch {args.watch}s] Ctrl+C para sair")
            time.sleep(args.watch)
    except KeyboardInterrupt:
        print("\n[dashboard encerrado]")
        return 0


if __name__ == "__main__":
    sys.exit(main())
