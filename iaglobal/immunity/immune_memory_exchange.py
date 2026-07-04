# iaglobal/immunity/immune_memory_exchange.py
"""
ImmuneMemoryExchange — Compartilhamento de memória imunológica entre nós.

Protocolo de "vacina compartilhada":
- Um nó detecta nova ameaça → fingerprint propagado via AcetylcholineBus
- Nós receptor usam membrane_key para validar origem
- Signatures importadas são validadas antes do merge
"""
import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from iaglobal.graphs.communication.membrane_key import MembraneKey
from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus, AgentMessage
from iaglobal.immunity.mhc_detector import MHCDetector

logger = logging.getLogger(__name__)


class ImmuneMemoryExchange:
    """
    Exchange de memória imunológica entre instâncias.
    
    Operação:
    1. Exporta fingerprints validados
    2. Transmite via AcetylcholineBus (com membrane_key)
    3. Importa e valida assinaturas remotas
    4. Atualiza whitelist local
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._bus = AcetylcholineBus()
        self._membrane = MembraneKey()
        self._mhc = MHCDetector()

    async def export_immune_memory(self, node_id: str = "local") -> Dict[str, Any]:
        """
        Exporta memória imunológica local.
        
        Returns:
            {"signatures": list, "node_id": str, "timestamp": str}
        """
        signatures = []
        
        if hasattr(self._mhc, '_skills'):
            for name, data in self._mhc._skills.items():
                signatures.append({
                    "name": name,
                    "fingerprint": data.get("fingerprint", ""),
                    "created_at": data.get("created_at", ""),
                })
        
        return {
            "signatures": signatures,
            "node_id": node_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checksum": hashlib.sha3_256(str(signatures).encode()).hexdigest()[:32],
        }

    async def broadcast_immune_update(self, node_id: str = "local") -> bool:
        """
        Transmite atualização imunológica para toda a frota.
        """
        payload = await self.export_immune_memory(node_id)
        
        msg = AgentMessage(
            sender=node_id,
            receiver="immune_exchange",
            type="immune_vaccine",
            payload={"immune_data": payload, "membrane_key": self._membrane._keys.get(node_id, {}).get("key")},
        )
        
        await self._bus.publish(msg)
        logger.info(f"[IMMUNE-EXCHANGE] Broadcasted {len(payload['signatures'])} signatures")
        return True

    async def import_immune_memory(self, remote_data: Dict[str, Any], source: str) -> int:
        """
        Importa memória imunológica remota (vacina).
        
        Returns:
            Número de signatures importadas
        """
        imported = 0
        signature_list = remote_data.get("signatures", [])
        
        for sig in signature_list:
            name = sig.get("name")
            fp = sig.get("fingerprint", "")
            
            if not fp:
                continue
                
            # Valida checksum da assinatura
            if self._validate_signature_integrity(sig):
                self._mhc._fingerprints[name] = fp
                imported += 1
        
        if imported > 0:
            logger.info(f"[IMMUNE-EXCHANGE] Imported {imported} signatures from {source}")
        
        return imported

    def _validate_signature_integrity(self, sig: Dict[str, Any]) -> bool:
        """Valida integridade da assinatura recebida."""
        fp = sig.get("fingerprint", "")
        # Fingerprint SHA3_512 deve ter 128 chars (64 bytes em hex)
        return len(fp) == 128 and all(c in "0123456789abcdef" for c in fp)


# Singleton
immune_memory_exchange = ImmuneMemoryExchange()