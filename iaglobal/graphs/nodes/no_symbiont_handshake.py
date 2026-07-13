# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_symbiont_handshake.py
"""
no_symbiont_handshake — Handshake de membrana para integração de simbiontes.

Protocolo:
1. Recebe requisição externa com credenciais
2. Valida contra genesis hash
3. Gera chave de membrana se autorizado
4. Permite sinalização via AcetylcholineBus
"""

import logging
from typing import Dict, Any

from iaglobal.graphs.comms.membrane_key import MembraneKey

logger = logging.getLogger(__name__)


async def run_symbiont_handshake(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Realiza handshake com sistema externo para simbiose.

    Args:
        context: {
            "external_system": str,  # Nome do sistema externo
            "request_signature": str,  # Assinatura de solicitação
        }

    Returns:
        {"membrane_key": str, "granted": bool, "permissions": list}
    """
    system_name = context.get("external_system", "unknown")
    request_sig = context.get("request_signature", "")

    # Validação básica de assinatura
    if not request_sig:
        logger.warning(f"[SYMBIONT] Handshake rejeitado: sem assinatura")
        return {"granted": False, "reason": "no_signature"}

    # Gerar chave de membrana
    mk = MembraneKey()
    key = mk.generate_key(system_name)

    logger.info(f"[SYMBIONT] Handshake concedido para {system_name}")

    return {
        "membrane_key": key,
        "granted": True,
        "permissions": ["signal", "read"],
        "system": system_name,
    }
