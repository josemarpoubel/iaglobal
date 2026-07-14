# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_auditor_sentinel.py
"""
no_auditor_sentinel — Auditoria de integridade do genesis em tempo real.

Detecta divergências hash e dispara shutdown preventivo.
"""

import logging
from typing import Dict, Any

from iaglobal.immunity.entropy_sentinel import entropy_sentinel

logger = logging.getLogger(__name__)


async def run_auditor_sentinel(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Audita integridade do genesis e alerta se divergir.

    Args:
        context: {"force_check": bool, "expected_hash": str}

    Returns:
        {"integrity_ok": bool, "current_hash": str, "alert_triggered": bool}
    """
    from iaglobal.core.graceful_shutdown import graceful_shutdown

    expected = context.get("expected_hash") or entropy_sentinel._genesis_hash
    current = entropy_sentinel._genesis_hash


logger = logging.getLogger(__name__)


async def run_auditor_sentinel(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Audita integridade do genesis e alerta se divergir.

    Args:
        context: {"force_check": bool, "expected_hash": str}

    Returns:
        {"integrity_ok": bool, "current_hash": str, "alert_triggered": bool}
    """
    expected = context.get("expected_hash") or entropy_sentinel._genesis_hash
    current = entropy_sentinel._genesis_hash

    # Verificar se genesis foi corrompido
    if expected and current != expected:
        logger.error(
            f"[AUDITOR] Genesis CORRUPTO! Esperado: {expected[:16]}..., Atual: {current[:16]}..."
        )

        # Trigger shutdown preventivo
        await graceful_shutdown.trigger_emergency_shutdown(
            reason="genesis_integrity_violation",
            details={"expected": expected[:16], "current": current[:16]},
        )

        return {
            "integrity_ok": False,
            "current_hash": current,
            "alert_triggered": True,
            "emergency_shutdown": True,
        }

    return {
        "integrity_ok": True,
        "current_hash": current,
        "alert_triggered": False,
    }
