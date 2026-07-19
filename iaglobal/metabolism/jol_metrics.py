# iaglobal/metabolism/jol_metrics.py
# JOL (Joint Optimization Loop) Metrics Collector — Observador Passivo.
#
# Coleta telemetria estruturada das intervenções do Sentinela e correções
# do Juiz via AcetylcholineBus (pub/sub). Armazena em JSONL para análise
# posterior com jq/pandas.
#
# Uso:
#   from iaglobal.metabolism.jol_metrics import JOLMetricsCollector
#   collector = JOLMetricsCollector()
#   collector.start()  # inscreve no barramento
#   ... execução do pipeline ...
#   collector.stop()
#   summary = collector.get_summary()

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from iaglobal.graphs.comms.acetylcholine_bus import (
    AcetylcholineBus, AgentMessage, bus as default_bus,
)
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.metabolism.jol_metrics")

# Paths padrão (iaglobal/memory/data/jol/)
JOL_DATA_DIR = Path(__file__).parent.parent / "memory" / "data" / "jol"
INTERVENTIONS_FILE = JOL_DATA_DIR / "jol_interventions.jsonl"
CORRECTIONS_FILE = JOL_DATA_DIR / "jol_corrections.jsonl"
CONGESTION_FILE = JOL_DATA_DIR / "jol_congestion.jsonl"


def _ensure_data_dir() -> None:
    """Cria diretório de dados se não existir."""
    JOL_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _write_jsonl(filepath: Path, record: Dict[str, Any]) -> None:
    """Escreve um registro em arquivo JSONL (line-buffered)."""
    _ensure_data_dir()
    with open(filepath, "a", buffering=1) as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


class JOLMetricsCollector:
    """Observador passivo de intervenções do Sentinela e correções do Juiz.

    Inscreve-se no AcetylcholineBus e captura:
      - sentinel_intervention: violações detectadas + LFM confirmation
      - critic_correction: correções aplicadas pelo Juiz (aprovadas/rejeitadas)

    Armazena em JSONL para análise offline.
    """

    def __init__(self, bus: Optional[AcetylcholineBus] = None) -> None:
        self.bus = bus or default_bus
        self._running = False
        self._stats = {
            "total_sentinel_interventions": 0,
            "total_critic_corrections": 0,
            "corrections_approved": 0,
            "corrections_rejected": 0,
            "false_alarms": 0,
            "tokens_spent_by_judge": 0,
            "total_congestion_alerts": 0,
            "first_event_timestamp": None,
            "last_event_timestamp": None,
        }
        self._intervention_callback = None
        self._correction_callback = None
        self._congestion_callback = None
        self._congestion_callback = None

    def _on_sentinel_intervention(self, msg: AgentMessage) -> None:
        """Callback para intervenções do Sentinela."""
        if not self._running:
            return

        timestamp = datetime.utcnow().isoformat() + "Z"
        task_id = msg.content.get("task_id", "unknown") if isinstance(msg.content, dict) else "unknown"
        violations = msg.content.get("violations", []) if isinstance(msg.content, dict) else []

        record = {
            "timestamp": timestamp,
            "event_type": "sentinel_intervention",
            "task_id": task_id,
            "violations_count": len(violations),
            "violations": [
                {
                    "requirement": v.get("requirement", "?"),
                    "check": v.get("check", "?"),
                    "category": v.get("category", "unknown"),
                }
                for v in violations
            ],
            "action": msg.content.get("action", "unknown") if isinstance(msg.content, dict) else "unknown",
            "sender": msg.sender,
        }

        _write_jsonl(INTERVENTIONS_FILE, record)
        self._stats["total_sentinel_interventions"] += 1
        self._update_timestamps(timestamp)

        logger.debug(
            "[JOL] Sentinel intervention: task=%s violations=%d",
            task_id, len(violations),
        )

    def _on_critic_correction(self, msg: AgentMessage) -> None:
        """Callback para correções do Juiz (Critic)."""
        if not self._running:
            return

        timestamp = datetime.utcnow().isoformat() + "Z"
        content = msg.content if isinstance(msg.content, dict) else {}

        task_id = content.get("task_id", "unknown")
        status = content.get("status", "unknown")  # approved, rejected
        tokens_used = content.get("tokens_used", 0)
        latency_ms = content.get("latency_ms", 0)

        record = {
            "timestamp": timestamp,
            "event_type": "critic_correction",
            "task_id": task_id,
            "status": status,
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
            "original_violations_count": content.get("original_violations_count", 0),
            "sender": msg.sender,
        }

        _write_jsonl(CORRECTIONS_FILE, record)
        self._stats["total_critic_corrections"] += 1
        self._update_timestamps(timestamp)

        if status == "approved":
            self._stats["corrections_approved"] += 1
        elif status == "rejected":
            self._stats["corrections_rejected"] += 1
            self._stats["false_alarms"] += 1

        self._stats["tokens_spent_by_judge"] += tokens_used

        logger.debug(
            "[JOL] Critic correction: task=%s status=%s tokens=%d",
            task_id, status, tokens_used,
        )

    def _on_tier_congestion(self, msg: AgentMessage) -> None:
        """Callback para alertas de congestão de tier do LocalModelGate.

        Persiste dados reais de rejeição/fila (não proxy) para o helper
        threshold_analyzer calcular rejection_pct e tendência de exaustão.
        """
        if not self._running:
            return

        content = msg.content if isinstance(msg.content, dict) else {}
        timestamp = datetime.utcnow().isoformat() + "Z"
        tier = content.get("tier", "unknown")

        record = {
            "timestamp": timestamp,
            "event_type": "tier_congestion_alert",
            "tier": tier,
            "status": content.get("status", "unknown"),
            "usage_pct": content.get("usage_pct", 0.0),
            "rejections": content.get("rejections", 0),
            "capacity": content.get("capacity", 0),
            "current_concurrency": content.get("current_concurrency", 0),
            "fill_rate": content.get("fill_rate", 0.0),
            "sender": msg.sender,
        }

        _write_jsonl(CONGESTION_FILE, record)
        self._stats["total_congestion_alerts"] = \
            self._stats.get("total_congestion_alerts", 0) + 1
        self._update_timestamps(timestamp)

        logger.debug(
            "[JOL] Congestion alert: tier=%s usage=%.1f%% conc=%d/%d rej=%d",
            tier, record["usage_pct"], record["current_concurrency"],
            record["capacity"], record["rejections"],
        )

    def _update_timestamps(self, timestamp: str) -> None:
        """Atualiza primeiro e último timestamp para cálculo de janela temporal."""
        if self._stats["first_event_timestamp"] is None:
            self._stats["first_event_timestamp"] = timestamp
        self._stats["last_event_timestamp"] = timestamp

    def start(self) -> None:
        """Inscreve o coletor no barramento (inicia coleta)."""
        if self._running:
            logger.warning("[JOL] Coletor já está rodando")
            return

        self._running = True
        self._intervention_callback = self._on_sentinel_intervention
        self._correction_callback = self._on_critic_correction
        self._congestion_callback = self._on_tier_congestion

        self.bus.subscribe("sentinel_intervention", self._intervention_callback)
        self.bus.subscribe("critic_correction", self._correction_callback)
        self.bus.subscribe("tier_congestion_alert", self._congestion_callback)

        logger.info(
            "[JOL] Coletor iniciado — interventions=%s corrections=%s congestion=%s",
            INTERVENTIONS_FILE, CORRECTIONS_FILE, CONGESTION_FILE,
        )

    def stop(self) -> None:
        """Cancela inscrição no barramento (para coleta)."""
        if not self._running:
            return

        self._running = False

        if self._intervention_callback:
            self.bus.unsubscribe("sentinel_intervention", self._intervention_callback)
        if self._correction_callback:
            self.bus.unsubscribe("critic_correction", self._correction_callback)
        if self._congestion_callback:
            self.bus.unsubscribe("tier_congestion_alert", self._congestion_callback)

        logger.info("[JOL] Coletor parado — stats=%s", self.get_summary())

    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo das métricas coletadas (para CLI/dashboard)."""
        total = self._stats["total_critic_corrections"]
        approved = self._stats["corrections_approved"]

        # intervention_precision = correções aprovadas / total intervenções
        precision = (approved / total * 100) if total > 0 else 0.0

        # intervention_rate = intervenções / correções (quanto >1, mais ruído)
        noise_ratio = (
            self._stats["total_sentinel_interventions"] / total
            if total > 0 else 0.0
        )

        return {
            **self._stats,
            "intervention_precision": round(precision, 2),
            "noise_ratio": round(noise_ratio, 2),
            "data_files": {
                "interventions": str(INTERVENTIONS_FILE),
                "corrections": str(CORRECTIONS_FILE),
                "congestion": str(CONGESTION_FILE),
            },
        }

    def reset_stats(self) -> None:
        """Zera estatísticas (útil para testes ou nova sessão)."""
        self._stats = {
            "total_sentinel_interventions": 0,
            "total_critic_corrections": 0,
            "corrections_approved": 0,
            "corrections_rejected": 0,
            "false_alarms": 0,
            "tokens_spent_by_judge": 0,
            "total_congestion_alerts": 0,
            "first_event_timestamp": None,
            "last_event_timestamp": None,
        }


# ── CLI Helper ──────────────────────────────────────────────────────

def print_summary() -> None:
    """Imprime resumo formatado para CLI (iaglobal status)."""
    collector = JOLMetricsCollector()
    summary = collector.get_summary()

    print("\n=== JOL (Joint Optimization Loop) Metrics ===")
    print(f"Total Sentinel Interventions:    {summary['total_sentinel_interventions']}")
    print(f"Total Critic Corrections:        {summary['total_critic_corrections']}")
    print(f"  → Approved:                    {summary['corrections_approved']}")
    print(f"  → Rejected (False Alarms):     {summary['corrections_rejected']}")
    print(f"Tokens Spent by Judge:           {summary['tokens_spent_by_judge']}")
    print()
    print(f"Intervention Precision:          {summary['intervention_precision']}%")
    print(f"Noise Ratio (interv/corr):       {summary['noise_ratio']}")
    print(f"Total Congestion Alerts:         {summary.get('total_congestion_alerts', 0)}")
    print()
    print(f"First Event:                     {summary['first_event_timestamp'] or 'N/A'}")
    print(f"Last Event:                      {summary['last_event_timestamp'] or 'N/A'}")
    print()
    print(f"Data Files:")
    print(f"  Interventions: {summary['data_files']['interventions']}")
    print(f"  Corrections:   {summary['data_files']['corrections']}")
    print()


# ── Auto-start (opcional) ───────────────────────────────────────────

_collector_instance: Optional[JOLMetricsCollector] = None


def get_collector() -> JOLMetricsCollector:
    """Retorna singleton do coletor (auto-inicia se necessário)."""
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = JOLMetricsCollector()
        _collector_instance.start()
    return _collector_instance


def stop_collector() -> None:
    """Para o coletor singleton (para shutdown gracioso)."""
    global _collector_instance
    if _collector_instance is not None:
        _collector_instance.stop()
        _collector_instance = None