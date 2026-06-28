# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_metabolic_pruning.py
"""
no_metabolic_pruning — Nó de poda metabólica para fingerprints SHA3_512.

Operação:
1. Prune fingerprints TTL expirado
2. Merge fingerprints similares
3. Consolidate em audit trail
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from iaglobal.immunity.metabolic_pruner import metabolic_pruner
from iaglobal.immunity.mhc_detector import mhc_detector

logger = logging.getLogger(__name__)


async def run_metabolic_pruning(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa poda metabólica dos fingerprints.
    
    Args:
        context: {"force": bool, "ttl_days": int}
    
    Returns:
        {"pruned_count": int, "merged_count": int, "audit_path": str}
    """
    # Prune old signatures
    # O MHC detector mantém _skills dictionary
    if hasattr(mhc_detector, '_skills'):
        original_count = len(mhc_detector._skills)
        pruned = metabolic_pruner.prune_old_signatures(mhc_detector._skills)
        mhc_detector._skills = pruned
        pruned_count = original_count - len(pruned)
    else:
        pruned_count = 0
    
    # Merge similar signatures
    if hasattr(mhc_detector, '_fingerprints'):
        fingerprints = mhc_detector._fingerprints
        merged = metabolic_pruner.merge_similar_signatures(fingerprints)
        mhc_detector._fingerprints = merged
        merged_count = len(fingerprints) - len(merged)
    else:
        merged_count = 0
    
    # Consolidate para audit
    audit_path = metabolic_pruner.consolidate_to_audit(
        getattr(mhc_detector, '_skills', {})
    )
    
    logger.info(f"[PRUNING] Removed {pruned_count} old, merged {merged_count} similar fingerprints")
    
    return {
        "pruned_count": pruned_count,
        "merged_count": merged_count,
        "audit_path": str(audit_path),
        "execution_metrics": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pruning_performed": True,
        },
    }