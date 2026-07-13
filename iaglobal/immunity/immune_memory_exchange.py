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
from typing import Dict, Any, List
from datetime import datetime, timezone

from iaglobal.graphs.comms.membrane_key import MembraneKey
from iaglobal.graphs.comms.acetylcholine_bus import (
    AcetylcholineBus,
    AgentMessage,
)
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

        if hasattr(self._mhc, "_skills"):
            for name, data in self._mhc._skills.items():
                signatures.append(
                    {
                        "name": name,
                        "fingerprint": data.get("fingerprint", ""),
                        "created_at": data.get("created_at", ""),
                    }
                )

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
            payload={
                "immune_data": payload,
                "membrane_key": self._membrane._keys.get(node_id, {}).get("key"),
            },
        )

        await self._bus.publish(msg)
        logger.info(
            f"[IMMUNE-EXCHANGE] Broadcasted {len(payload['signatures'])} signatures"
        )
        return True

    async def import_immune_memory(
        self, remote_data: Dict[str, Any], source: str
    ) -> int:
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
            logger.info(
                f"[IMMUNE-EXCHANGE] Imported {imported} signatures from {source}"
            )

        return imported

    def _validate_signature_integrity(self, sig: Dict[str, Any]) -> bool:
        """Valida integridade da assinatura recebida."""
        fp = sig.get("fingerprint", "")
        # Fingerprint SHA3_512 deve ter 128 chars (64 bytes em hex)
        return len(fp) == 128 and all(c in "0123456789abcdef" for c in fp)

    # ── Vacinas por linhagem (cross-reference com VaccineLedger) ──────────

    async def publish_vaccine(
        self, lineage_marker: str, patterns: List[str], node_id: str = "local"
    ) -> bool:
        """
        Transmite vacinas (failure_patterns) de uma linhagem para a frota.

        As vacinas são marcadas com o `lineage_marker` — apenas nós que possuem
        (ou herdam) essa linhagem as consomem, impedindo autoimunidade entre
        famílias evolutivas distintas.
        """
        payload = {
            "lineage_marker": lineage_marker,
            "patterns": list(patterns),
            "node_id": node_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checksum": hashlib.sha3_256(
                (lineage_marker + str(patterns)).encode()
            ).hexdigest()[:32],
        }
        msg = AgentMessage(
            sender=node_id,
            receiver="immune_exchange",
            type="vaccine_broadcast",
            payload=payload,
        )
        await self._bus.publish(msg)
        logger.info(
            "[IMMUNE-EXCHANGE] Broadcasted %d vacina(s) p/ linhagem %s",
            len(patterns),
            lineage_marker,
        )
        return True

    async def import_vaccine(self, remote: Dict[str, Any], source: str) -> int:
        """
        Importa vacinas de uma linhagem remota.

        Gating evolutivo: a vacina só é persistida no ledger Obsidian se o
        `lineage_marker` remoto for reconhecido localmente (um EvoAgent desta
        linhagem existe ou já foi visto). Isso impede que linhagens estranhas
        injetem memória no subconsciente do organismo.

        Returns:
            Número de novos padrões persistidos no ledger da linhagem.
        """
        marker = remote.get("lineage_marker")
        if not marker:
            return 0
        try:
            from iaglobal.immunity.vaccine_ledger import vaccine_ledger
        except Exception as e:
            logger.debug("[IMMUNE-EXCHANGE] VaccineLedger indisponível: %s", e)
            return 0

        # Só aceita se este nó conhece a linhagem (mesmo DNA familiar)
        if not vaccine_ledger.owns_lineage(marker):
            logger.debug(
                "[IMMUNE-EXCHANGE] Vacina de linhagem %s recusada (não pertence a este nó)",
                marker,
            )
            return 0

        conteudo = await vaccine_ledger._vault.ler_vacina(marker)
        padroes = vaccine_ledger._parse_patterns(conteudo)
        existentes = {p.get("pattern") for p in padroes}
        novos = 0
        for pat in remote.get("patterns", []):
            if pat and pat not in existentes:
                padroes.append(
                    {
                        "pattern": pat,
                        "agent": f"remote:{source}",
                        "context": {"origin": source},
                    }
                )
                novos += 1
        if novos:
            await vaccine_ledger._vault.escrever_vacina(
                marker, vaccine_ledger._serialize(padroes, marker)
            )
            logger.info(
                "[IMMUNE-EXCHANGE] %d vacina(s) de %s persistida(s) p/ linhagem %s",
                novos,
                source,
                marker,
            )
        return novos

    def _owns_lineage(self, marker: str) -> bool:
        """Verifica se este nó possui (ou já viu) a linhagem informada."""
        try:
            from iaglobal.agents.agent_base import get_evo_registry

            return any(
                getattr(evo, "lineage_marker", "") == marker
                for evo in get_evo_registry().values()
            )
        except Exception:
            return False


# Singleton
immune_memory_exchange = ImmuneMemoryExchange()
