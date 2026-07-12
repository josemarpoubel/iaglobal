# iaglobal/observability/metrics_collector.py

import logging
from iaglobal.providers.provider_metrics import metrics

logger = logging.getLogger("OBSERVABILITY")

class MetricsCollector:
    @staticmethod
    def collect_provider_metrics():
        return metrics.get_provider_stats()

    @staticmethod
    def collect_model_metrics():
        return metrics.get_model_stats()

    @staticmethod
    def format_report():
        model_stats = MetricsCollector.collect_model_metrics()
        provider_stats = MetricsCollector.collect_provider_metrics()

        def _format_metrics_report(stats: dict, title: str) -> str:
            if not stats:
                return f"{title}: Nenhum dado disponível.\n"
            lines = [f"\n=== {title} ==="]
            for model, values in stats.items():
                success = values.get("success_rate", "N/A")
                latency = values.get("avg_latency", "N/A")
                cost = values.get("avg_cost", "N/A")
                lines.append(f"{model}: success={success}, latency={latency}, cost={cost}")
            return "\n".join(lines)

        return _format_metrics_report(model_stats, "Model Performance") + "\n" + \
               _format_metrics_report(provider_stats, "Provider Performance")

