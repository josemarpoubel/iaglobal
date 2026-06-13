"""Benchmark: Provedores — reputação + score histórico."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from iaglobal.cognition.reputation_engine import reputation_engine
from iaglobal.cognition.outcome_tracker import outcome_tracker
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.providers.provider_metrics import metrics
from iaglobal.providers.provider_router import CREDIT_CANDIDATES

import statistics


def main():
    print("=" * 65)
    print("  Benchmark de Provedores — Reputação + Score")
    print("=" * 65)

    candidates = CREDIT_CANDIDATES()
    credit = CreditAssignmentEngine()

    rows = []
    for provider_name, model_name in candidates:
        model = f"{provider_name}/{model_name}"

        # Reputation score (0-1)
        rep_score = reputation_engine.score(model)

        # Credit score (histórico de sucesso para este modelo)
        credit_score = credit.score("benchmark", model, "general")

        # Metrics score (latência, custo)
        metric_score = 0.5
        try:
            m = metrics.get(model)
            if m:
                latency = m.get("avg_latency", 0) or 0
                success = m.get("success_rate", 0) or 0
                metric_score = (success * 0.6) + (max(0, 1 - latency / 30) * 0.4)
        except Exception:
            pass

        # Combined score (mesma fórmula do BanditPolicy)
        combined = (credit_score * 0.5) + (metric_score * 0.25) + (rep_score * 0.25)

        # Historical data from outcome_tracker
        try:
            avg_success = outcome_tracker.avg_success_rate(model)
            avg_lat = outcome_tracker.avg_latency(model)
        except Exception:
            avg_success = 0
            avg_lat = 0

        rows.append({
            "provider": provider_name,
            "model": model_name,
            "reputation": rep_score,
            "credit": credit_score,
            "metric": metric_score,
            "combined": combined,
            "success_rate": avg_success,
            "avg_latency": avg_lat,
        })

    # Sort by combined score descending
    rows.sort(key=lambda r: r["combined"], reverse=True)

    print(f"\n  Total de provedores: {len(rows)}")
    print(f"\n  {'Provider':<20} {'Model':<30} {'Reput':<6} {'Credit':<6} "
          f"{'Metric':<6} {'Total':<6} {'Sucesso':<7} {'Latência':<8}")
    print(f"  {'-'*20} {'-'*30} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*7} {'-'*8}")

    for r in rows:
        lat_str = f"{r['avg_latency']*1000:.0f}ms" if r['avg_latency'] else "N/A"
        print(f"  {r['provider']:<20} {r['model']:<30} "
              f"{r['reputation']:<6.2f} {r['credit']:<6.2f} "
              f"{r['metric']:<6.2f} {r['combined']:<6.2f} "
              f"{r['success_rate']:<7.2f} {lat_str:<8}")

    print("\n" + "-" * 65)

    top5 = rows[:5]
    print(f"\n  Top 5 provedores (combined score):")
    for i, r in enumerate(top5, 1):
        print(f"  {i}. {r['provider']}/{r['model']} — score={r['combined']:.2f} "
              f"(reput={r['reputation']:.2f} credit={r['credit']:.2f})")

    avg_rep = statistics.mean([r["reputation"] for r in rows]) if rows else 0
    avg_comb = statistics.mean([r["combined"] for r in rows]) if rows else 0
    print(f"\n  Média de reputação:  {avg_rep:.3f}")
    print(f"  Média combined:      {avg_comb:.3f}")
    print("-" * 65)


if __name__ == "__main__":
    main()
