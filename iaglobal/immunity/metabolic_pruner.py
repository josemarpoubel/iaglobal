# iaglobal/immunity/metabolic_pruner.py
"""
MetabolicPruner — Poda automática de assinaturas SHA3_512.

Operação metabólica:
- Remove fingerprints com TTL expirado (>30 dias)
- Merge fingerprints similares (distância hamming < 5%)
- Consolidate: agrupa padrões em clusters para eficiência
- Mantém audit trail em 03_Long_Term
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class MetabolicPruner:
    """
    Poda metabólica de fingerprints - mantém eficiência sem perder integridade.
    """

    _instance = None
    TTL_DAYS = 30  # Podar fingerprints mais antigas que 30 dias

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._pruning_log: List[Dict[str, Any]] = []

    def prune_old_signatures(self, signatures: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove fingerprints expirados.

        Args:
            signatures: {name: {fingerprint, created_at}}

        Returns:
            Dicionário com fingerprints ativos
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.TTL_DAYS)
        pruned = {}
        removed = []

        for name, data in signatures.items():
            created = data.get("created_at")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if created_dt < cutoff:
                        removed.append(name)
                        continue
                except Exception:
                    pass
            pruned[name] = data

        self._log_pruning(removed, "ttl_expired")
        return pruned

    def merge_similar_signatures(
        self, signatures: Dict[str, str], similarity_threshold: float = 0.05
    ) -> Dict[str, str]:
        """
        Merge fingerprints com hashsimilar (distância hamming < threshold).
        """
        if len(signatures) < 2:
            return signatures

        merged = {}
        clusters = []

        for name, fp in signatures.items():
            found_cluster = False
            for cluster in clusters:
                rep_fp = cluster[0][1]
                hamming = self._hamming_distance(fp, rep_fp)
                if hamming / len(rep_fp) < similarity_threshold:
                    cluster.append((name, fp))
                    found_cluster = True
                    break
            if not found_cluster:
                clusters.append([(name, fp)])

        for cluster in clusters:
            # Manter representative com maior fitness
            rep_name, rep_fp = max(cluster, key=lambda x: signatures.get(x[0], ""))
            merged[rep_name] = rep_fp

        removed = len(signatures) - len(merged)
        if removed > 0:
            self._log_pruning(
                [n for n, _ in cluster[1:] for cluster in clusters], "merged_similar"
            )

        return merged

    def _hamming_distance(self, fp1: str, fp2: str) -> int:
        """Calcula distância hamming entre fingerprints."""
        return sum(c1 != c2 for c1, c2 in zip(fp1, fp2))

    def consolidate_to_audit(self, pruned: Dict[str, Any]) -> Path:
        """
        Grava fingerprints consolidados em audit trail.
        """
        audit_dir = Path("iaglobal/obsidian/03_Long_Term")
        audit_dir.mkdir(parents=True, exist_ok=True)

        audit_content = f"""---
id: "mhc_audit_{datetime.now().strftime("%Y%m%d")}"
tipo: "AuditTrail"
timestamp: "{datetime.now(timezone.utc).isoformat()}Z"
total_signatures: {len(pruned)}
hashes_consolidated: {len(pruned)}
---

# MHC Audit Trail - {datetime.now().strftime("%Y-%m-%d")}
"""
        for name, data in pruned.items():
            audit_content += f"\n- {name}: {data.get('fingerprint', 'N/A')[:16]}..."

        audit_path = audit_dir / f"mhc_audit_{datetime.now().strftime('%Y%m%d')}.md"
        audit_path.write_text(audit_content)

        return audit_path

    def _log_pruning(self, names: List[str], reason: str) -> None:
        """Log da poda para auditoria."""
        self._pruning_log.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
                "names_removed": names,
            }
        )
        logger.info(f"[PRUNER] Removed {len(names)} signatures: {reason}")

    def get_pruning_stats(self) -> Dict[str, Any]:
        """Estatísticas de poda."""
        return {
            "total_pruning_events": len(self._pruning_log),
            "events_by_reason": self._aggregate_reasons(),
        }

    def _aggregate_reasons(self) -> Dict[str, int]:
        """Agrega eventos por motivo."""
        agg = {}
        for event in self._pruning_log:
            reason = event.get("reason", "unknown")
            agg[reason] = agg.get(reason, 0) + len(event.get("names_removed", []))
        return agg


# Singleton
metabolic_pruner = MetabolicPruner()
