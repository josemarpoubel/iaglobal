# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_proposal_quarantine.py
"""
no_proposal_quarantine — Nó de submissão de propostas para quarentena.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from iaglobal.evolution.proposal_quarantine import proposal_quarantine

logger = logging.getLogger(__name__)


async def run_proposal_quarantine(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Submete proposta para revisão antes do merge.

    Args:
        context: {"component": str, "changes": dict, "expected_ivm": float}

    Returns:
        {"proposal_id": str, "auto_approve": bool, "submitted": bool}
    """
    component = context.get("component", "unknown")
    changes = context.get("changes", {})
    expected_ivm = context.get("expected_ivm", 0.5)
    test_results = context.get("test_results", {})

    proposal_id = proposal_quarantine.submit_proposal(
        component, changes, expected_ivm, test_results
    )

    # Calcular taxa de aprovação
    pass_rate = test_results.get("pass_rate", 1.0)
    auto_approve = proposal_quarantine.should_auto_approve(expected_ivm, pass_rate)

    logger.info(f"[QUARANTINE] Proposal {proposal_id} - auto_approve={auto_approve}")

    return {
        "proposal_id": proposal_id,
        "auto_approve": auto_approve,
        "submitted": True,
        "execution_metrics": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "quarantine_submit": True,
        },
    }
