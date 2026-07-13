"""Genesis Handshake Protocol — Autenticação segura entre nós remotos.

Baseado em SHA3-512 lineage markers, não em certificados X.509.
Similar ao TLS, mas adaptado para organismos computacionais iaglobal.

Fluxo:
1. CLIENT_HELLO: cliente envia lineage_marker + nonce
2. SERVER_HELLO: servidor responde com lineage_marker + nonce assinado
3. VERIFY_CROSS: ambos verificam se o outro deriva do genesis hash
4. SESSION_ESTABLISHED: sessão autenticada
"""

import hashlib
import hmac
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL

logger = logging.getLogger("iaglobal")


class HandshakeState(Enum):
    """Estados do handshake Genesis."""

    INIT = "init"
    CLIENT_HELLO_SENT = "client_hello_sent"
    SERVER_HELLO_SENT = "server_hello_sent"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass
class GenesisHandshake:
    """Protocolo de handshake baseado em DNA compartilhado."""

    node_id: str
    lineage_marker: str
    genesis_hash: str = field(default=GENESIS_HASH_OFFICIAL)
    state: HandshakeState = HandshakeState.INIT
    session_id: Optional[str] = None
    peer_lineage_marker: Optional[str] = None
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=time.time)

    def derive_from_genesis(self) -> bool:
        """Verifica se o lineage marker deriva do genesis hash."""
        return self.lineage_marker == self.genesis_hash

    def sign_nonce(self, nonce: str, secret: str) -> str:
        """Assina nonce com HMAC-SHA3-512."""
        return hmac.new(
            secret.encode(),
            nonce.encode(),
            hashlib.sha3_512,
        ).hexdigest()

    def verify_signature(self, nonce: str, signature: str, secret: str) -> bool:
        """Verifica assinatura de nonce."""
        expected = self.sign_nonce(nonce, secret)
        return hmac.compare_digest(expected, signature)

    def build_client_hello(self) -> Dict[str, str]:
        """Cliente inicia handshake."""
        self.state = HandshakeState.CLIENT_HELLO_SENT
        return {
            "type": "CLIENT_HELLO",
            "node_id": self.node_id,
            "lineage_marker": self.lineage_marker,
            "nonce": self.nonce,
            "timestamp": str(self.created_at),
        }

    def build_server_hello(
        self, client_hello: Dict[str, str], secret: str, max_age: float = 60.0
    ) -> Dict[str, str]:
        """Servidor responde ao handshake."""
        if client_hello.get("type") != "CLIENT_HELLO":
            self.state = HandshakeState.FAILED
            return {"type": "ERROR", "message": "Invalid handshake init"}

        # Verifica idade do nonce
        timestamp = float(client_hello.get("timestamp", 0))
        if time.time() - timestamp > max_age:
            self.state = HandshakeState.FAILED
            return {"type": "ERROR", "message": "Client hello expired"}

        self.peer_lineage_marker = client_hello.get("lineage_marker")
        peer_nonce = client_hello.get("nonce", "")

        # Verifica se o peer deriva do genesis
        if not self._verify_peer_lineage():
            self.state = HandshakeState.FAILED
            return {
                "type": "ERROR",
                "message": "Peer lineage marker does not derive from genesis",
            }

        # Gera novo nonce e assina o nonce do cliente
        self.nonce = uuid.uuid4().hex
        signature = self.sign_nonce(peer_nonce, secret)

        self.state = HandshakeState.SERVER_HELLO_SENT
        return {
            "type": "SERVER_HELLO",
            "node_id": self.node_id,
            "lineage_marker": self.lineage_marker,
            "nonce": self.nonce,
            "peer_nonce_signature": signature,
            "timestamp": str(self.created_at),
        }

    def build_verify_cross(
        self, server_hello: Dict[str, str], secret: str, max_age: float = 60.0
    ) -> Dict[str, str]:
        """Cliente finaliza verificação cruzada."""
        if server_hello.get("type") != "SERVER_HELLO":
            self.state = HandshakeState.FAILED
            return {"type": "ERROR", "message": "Invalid server hello"}

        # Verifica idade do server hello
        timestamp = float(server_hello.get("timestamp", 0))
        if time.time() - timestamp > max_age:
            self.state = HandshakeState.FAILED
            return {"type": "ERROR", "message": "Server hello expired"}

        self.peer_lineage_marker = server_hello.get("lineage_marker")
        peer_nonce_signature = server_hello.get("peer_nonce_signature", "")

        # Verifica assinatura do nonce próprio
        if not self.verify_signature(self.nonce, peer_nonce_signature, secret):
            self.state = HandshakeState.FAILED
            return {
                "type": "ERROR",
                "message": "Invalid server signature",
            }

        # Verifica lineage do servidor
        if not self._verify_peer_lineage():
            self.state = HandshakeState.FAILED
            return {
                "type": "ERROR",
                "message": "Server lineage marker does not derive from genesis",
            }

        self.session_id = uuid.uuid4().hex
        self.state = HandshakeState.VERIFIED

        return {
            "type": "SESSION_ESTABLISHED",
            "session_id": self.session_id,
            "node_id": self.node_id,
            "lineage_marker": self.lineage_marker,
        }

    def _verify_peer_lineage(self) -> bool:
        """Verifica se o peer deriva do genesis."""
        if not self.peer_lineage_marker:
            return False
        return self.peer_lineage_marker == self.genesis_hash

    def is_established(self) -> bool:
        """Handshake foi completado com sucesso."""
        return self.state == HandshakeState.VERIFIED

    def to_dict(self) -> Dict[str, str]:
        """Serializa estado."""
        return {
            "node_id": self.node_id,
            "lineage_marker": self.lineage_marker,
            "state": self.state.value,
            "session_id": self.session_id or "",
            "peer_lineage_marker": self.peer_lineage_marker or "",
            "nonce": self.nonce,
        }
