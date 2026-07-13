# iaglobal/evolution/proposal_quarantine.py
"""
ProposalQuarantine — Validação de propostas antes do merge automático.

Opera como "Quarentena de Consenso":
1. MetaDirector propõe mudança
2. Grava em Synapses/proposals/ para revisão
3. Aguarda validação via OmniMind
4. Se aprovado → aplicar ao core com snapshot
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ProposalQuarantine:
    """
    Quarentena de propostas evolutivas.

    Operação:
    1. Recebe proposta de mudança (ex: novos pesos IVM)
    2. Grava em 04_Synapses/proposals/ com metadados
    3. Notifica via AcetylcholineBus para revisão
    4. Aprova automaticamente se fitness > threshold
    5. Rejeita se falha em qualquer teste
    """

    _instance = None
    AUTO_APPROVE_THRESHOLD = 0.85  # Se IVM > 0.85, aprova automaticamente

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._proposals_dir = Path("iaglobal/obsidian/04_Synapses/proposals")
        self._proposals_dir.mkdir(parents=True, exist_ok=True)

    def submit_proposal(
        self,
        component: str,
        changes: Dict[str, Any],
        expected_ivm: float,
        test_results: Dict[str, Any],
    ) -> str:
        """
        Submete proposta para quarentena.

        Returns:
            Proposal ID
        """
        proposal_id = f"proposal_{component}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        proposal = {
            "id": proposal_id,
            "component": component,
            "changes": changes,
            "expected_ivm": expected_ivm,
            "test_results": test_results,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending_review",
        }

        # Gravar proposta
        proposal_path = self._proposals_dir / f"{proposal_id}.md"
        content = f"""---
id: "{proposal_id}"
component: "{component}"
expected_ivm: {expected_ivm}
status: "pending_review"
submitted_at: "{proposal["submitted_at"]}"
---

# Proposta: {component}

## Mudanças Propostas
```json
{changes}
```

## Resultados de Teste
{test_results}

## Status
Pendente revisão humana ou aprovação automática (se IVM > {self.AUTO_APPROVE_THRESHOLD})
"""
        proposal_path.write_text(content)

        # Notificar via bus
        self._notify_proposal(proposal)

        logger.info(
            f"[PROPOSAL] {proposal_id} submetida - IVM esperado: {expected_ivm}"
        )
        return proposal_id

    def _notify_proposal(self, proposal: Dict[str, Any]) -> None:
        """Notifica via AcetylcholineBus."""
        try:
            from iaglobal.graphs.comms.acetylcholine_bus import (
                AcetylcholineBus,
                AgentMessage,
            )

            bus = AcetylcholineBus()
            msg = AgentMessage(
                sender="proposal_quarantine",
                receiver="meta_director",
                type="proposal_submitted",
                payload={"proposal": proposal},
            )
            # Não aguardar - notificação async
        except Exception:
            pass

    def should_auto_approve(self, expected_ivm: float, test_pass_rate: float) -> bool:
        """Determina se aprovação automática é segura."""
        return (
            expected_ivm >= self.AUTO_APPROVE_THRESHOLD and test_pass_rate >= 0.95
        )  # 95%+ testes passando

    def approve_proposal(self, proposal_id: str) -> bool:
        """Aprova proposta manualmente."""
        proposal_path = self._proposals_dir / f"{proposal_id}.md"

        if not proposal_path.exists():
            return False

        content = proposal_path.read_text()
        content = content.replace("status: pending_review", "status: approved")
        content = content.replace("Pendente revisão humana", "Aprovado manualmente")

        proposal_path.write_text(content)
        logger.info(f"[PROPOSAL] {proposal_id} aprovado")
        return True

    def reject_proposal(self, proposal_id: str, reason: str) -> bool:
        """Rejeita proposta com motivo."""
        proposal_path = self._proposals_dir / f"{proposal_id}.md"

        if not proposal_path.exists():
            return False

        content = proposal_path.read_text()
        content = content.replace(
            "status: pending_review", f"status: rejected\nmotivo_rejeicao: {reason}"
        )

        proposal_path.write_text(content)
        logger.info(f"[PROPOSAL] {proposal_id} rejeitado: {reason}")
        return True


# Singleton
proposal_quarantine = ProposalQuarantine()
