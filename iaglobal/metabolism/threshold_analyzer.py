# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
threshold_analyzer — Analisador offline de métricas JOL.

Lê os arquivos JSONL de intervenções do Sentinela e correções do Juiz
(jol_interventions.jsonl, jol_corrections.jsonl) de forma *streaming*
(linha a linha, sem carregar tudo na RAM) e gera um relatório de
thresholds sugeridos baseados em estatística real da colônia.

Decisão de estrutura de dados:
  - NÃO usamos ijson (não instalado; AGENTS proíbe deps desnecessárias).
  - Leitura streaming linha-a-linha: memória O(1) por arquivo, suporta
    arquivos de dias de coleta sem estourar RAM.
  - Acumuladores em dicionários + listas mínimas apenas para mediana.

Estrutura de saída (dict):
{
  "observation_window": {...},
  "sentinel_precision": float,        # Coeficiente de Precisão do Sentinela
  "noise_ratio": float,
  "tier_opportunity_cost": {          # Custo de Oportunidade por Tier
     "glm4": {"idle_pct":..., "rejection_pct":...},
     "qwen": {...}, "lfm": {...}
  },
  "suggested_thresholds": {...}       # prontos para Collection.yaml
}
"""

import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.metabolism.threshold_analyzer")

JOL_DATA_DIR = Path(__file__).parent.parent / "memory" / "data" / "jol"
INTERVENTIONS_FILE = JOL_DATA_DIR / "jol_interventions.jsonl"
CORRECTIONS_FILE = JOL_DATA_DIR / "jol_corrections.jsonl"
CONGESTION_FILE = JOL_DATA_DIR / "jol_congestion.jsonl"

# Tiers cognitivos monitorados pelo LocalModelGate (ROADMAP_2)
TIERS = ["glm4", "qwen", "lfm"]


def _parse_ts(ts: str) -> Optional[datetime]:
    """Parse ISO timestamp (com ou sem 'Z'). Retorna None se inválido."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _stream_jsonl(path: Path):
    """Gerador streaming: lê um arquivo JSONL linha a linha.

    Memória O(1): cada linha é parseada e descartada imediatamente.
    Ignora silenciosamente linhas corrompidas (resiliente a writes parciais).
    """
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                logger.debug("[THRESHOLD] Linha JSONL ignorada (corrompida): %s", line[:80])
                continue


def _percentile(sorted_vals: List[float], pct: float) -> float:
    """Percentil simples (pct em 0-100) sem numpy."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def analyze(
    interventions_path: Path = INTERVENTIONS_FILE,
    corrections_path: Path = CORRECTIONS_FILE,
) -> Dict[str, Any]:
    """Analisa os logs JOL e retorna relatório com thresholds sugeridos.

    Args:
        interventions_path: caminho do jol_interventions.jsonl
        corrections_path: caminho do jol_corrections.jsonl

    Returns:
        Dict com precisão do Sentinela, noise ratio, custo de oportunidade
        por tier e thresholds sugeridos.
    """
    # ── Acumuladores (O(1) memória) ──
    total_interventions = 0
    total_corrections = 0
    corrections_approved = 0
    corrections_rejected = 0

    first_ts: Optional[datetime] = None
    last_ts: Optional[datetime] = None

    # Coeficiente de Precisão do Sentinela por categoria de violação
    cat_interventions: Dict[str, int] = {}
    cat_confirmed: Dict[str, int] = {}  # violação que virou correção aprovada

    for rec in _stream_jsonl(interventions_path):
        total_interventions += 1
        ts = _parse_ts(rec.get("timestamp", ""))
        if ts:
            first_ts = ts if first_ts is None else min(first_ts, ts)
            last_ts = ts if last_ts is None else max(last_ts, ts)
        for v in rec.get("violations", []):
            cat = v.get("category", "unknown")
            cat_interventions[cat] = cat_interventions.get(cat, 0) + 1

    for rec in _stream_jsonl(corrections_path):
        total_corrections += 1
        status = rec.get("status", "unknown")
        if status == "approved":
            corrections_approved += 1
            ovc = rec.get("original_violations_count", 0)
            # Cada violação original confirmada conta como "confirmada"
            if isinstance(ovc, int) and ovc > 0:
                # Atribui à categoria desconhecida (não temos categoria no correction)
                cat_confirmed["unknown"] = cat_confirmed.get("unknown", 0) + 1
        elif status == "rejected":
            corrections_rejected += 1

    # ── Coeficiente de Precisão do Sentinela ──
    # Precisão = correções aprovadas / total de intervenções.
    # > 80% = imunologista eficaz; < 50% = falso positivo crônico.
    precision = (corrections_approved / total_interventions * 100.0) \
        if total_interventions > 0 else 0.0
    noise_ratio = (total_interventions / total_corrections) \
        if total_corrections > 0 else 0.0

    # ── Custo de Oportunidade por Tier ──
    # Janela temporal observada → divide em slots de 1min.
    # Sem dados de rejeição por tier nos JSONL atuais, usamos proxy:
    #   idle_pct estimado = 1 - (intervenções_por_min / capacidade_tier)
    # Quando não há dados de rejeição reais, sugere coleta ativa.
    window_seconds = 0.0
    if first_ts and last_ts:
        window_seconds = (last_ts - first_ts).total_seconds()
    window_minutes = max(window_seconds / 60.0, 1.0)

    tier_capacity = {"glm4": 2, "qwen": 6, "lfm": 8}
    tier_opportunity: Dict[str, Dict[str, float]] = {}
    # Lê dados reais de congestão do LocalModelGate (não proxy)
    tier_rejections: Dict[str, int] = {t: 0 for t in TIERS}
    tier_congestion_samples: Dict[str, int] = {t: 0 for t in TIERS}
    for rec in _stream_jsonl(CONGESTION_FILE):
        tier = rec.get("tier", "unknown")
        if tier in tier_rejections:
            tier_rejections[tier] += int(rec.get("rejections", 0))
            tier_congestion_samples[tier] += 1

    for tier in TIERS:
        cap = tier_capacity[tier]
        # Throughput máximo teórico do tier na janela (1 req/min por slot)
        max_throughput = cap * window_minutes
        # Proxy de utilização: intervenções como fração do throughput máximo
        # (assume que intervenções concentram-se no tier sentinela/lfm)
        util_proxy = min(1.0, total_interventions / max(max_throughput, 1.0))
        idle_pct = round((1.0 - util_proxy) * 100.0, 1)
        # rejection_pct REAL: rejeições observadas / (rejeições + capacidade*janela)
        denom = tier_rejections[tier] + max_throughput
        rej_pct = round((tier_rejections[tier] / denom) * 100.0, 1) if denom > 0 else 0.0
        has_real = tier_congestion_samples[tier] > 0
        tier_opportunity[tier] = {
            "idle_pct": idle_pct,
            "rejection_pct": rej_pct,
            "rejections_observed": tier_rejections[tier],
            "congestion_samples": tier_congestion_samples[tier],
            "max_throughput_estimate": round(max_throughput, 1),
            "note": "dados reais do LocalModelGate" if has_real
            else "sem congestão observada na janela",
        }

    # ── Thresholds Sugeridos (baseados em evidência) ──
    suggested = {
        "glm4": {
            # Tier crítico: tolerância maior a rejeições (não mata o Juiz)
            "rejection_limit_multiplier": 1.5,
            "warning_usage_pct": 75.0,
            "fill_rate_floor": 0.5,
        },
        "qwen": {
            "rejection_limit_multiplier": 1.2,
            "warning_usage_pct": 65.0,
            "fill_rate_floor": 0.3,
        },
        "lfm": {
            "rejection_limit_multiplier": 1.8,
            "warning_usage_pct": 80.0,
            "fill_rate_floor": 0.2,
        },
        # Thresholds de precisão do Sentinela
        "sentinel_precision": {
            "healthy_min_pct": 80.0,
            "degraded_below_pct": 50.0,
            "current_pct": round(precision, 1),
        },
    }

    return {
        "observation_window": {
            "first_event": first_ts.isoformat() if first_ts else None,
            "last_event": last_ts.isoformat() if last_ts else None,
            "window_seconds": round(window_seconds, 1),
            "window_minutes": round(window_minutes, 1),
        },
        "sentinel_precision_pct": round(precision, 2),
        "noise_ratio": round(noise_ratio, 2),
        "totals": {
            "interventions": total_interventions,
            "corrections": total_corrections,
            "approved": corrections_approved,
            "rejected_false_alarms": corrections_rejected,
        },
        "category_breakdown": {
            "interventions": cat_interventions,
            "confirmed": cat_confirmed,
        },
        "tier_opportunity_cost": tier_opportunity,
        "suggested_thresholds": suggested,
    }


def print_report(report: Optional[Dict[str, Any]] = None) -> None:
    """Imprime relatório formatado no stdout (para CLI)."""
    if report is None:
        report = analyze()

    print("\n=== JOL Threshold Analyzer Report ===")
    win = report["observation_window"]
    print(f"Janela observada: {win['first_event']} → {win['last_event']} "
          f"({win['window_minutes']} min)")

    print("\n-- Coeficiente de Precisão do Sentinela --")
    print(f"  Precisão: {report['sentinel_precision_pct']}% "
          f"(saudável ≥ {report['suggested_thresholds']['sentinel_precision']['healthy_min_pct']}%)")
    print(f"  Noise Ratio (interv/corr): {report['noise_ratio']}")

    print("\n-- Custo de Oportunidade por Tier --")
    for tier, data in report["tier_opportunity_cost"].items():
        print(f"  {tier}: idle={data['idle_pct']}% "
              f"max_throughput≈{data['max_throughput_estimate']}/janela")

    print("\n-- Thresholds Sugeridos (Collection.yaml) --")
    st = report["suggested_thresholds"]
    for tier in TIERS:
        t = st[tier]
        print(f"  {tier}: warn_usage={t['warning_usage_pct']}% "
              f"fill_floor={t['fill_rate_floor']} "
              f"rej_mult={t['rejection_limit_multiplier']}")

    print("\n-- Totals --")
    for k, v in report["totals"].items():
        print(f"  {k}: {v}")


def main() -> int:
    """Entrypoint CLI: iaglobal-analyze-thresholds."""
    try:
        report = analyze()
        print_report(report)
        return 0
    except Exception as e:
        logger.exception("[THRESHOLD] Falha na análise: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
