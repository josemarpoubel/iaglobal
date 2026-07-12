# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/security/pysecurity1024.py

import secrets
import hmac
import hashlib

from typing import Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.security.pysecurity1024")

CONSOANTES = ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v']
VOGAIS = ['a', 'e', 'i', 'o', 'u', 'y', 'w', 'ae', 'ai', 'ao', 'au', 'ea', 'ei', 'eo', 'eu', 'ou']


class Pysecurity1024:
    """
    Motor de Segurança Baseado em HMAC-SHA3-512 e codificação fonética.
    V8.2: Correção de entropia e fatiamento fonético resiliente.
    """

    def __init__(self, seed: Optional[bytes] = None):
        self.key_bytes = seed or secrets.token_bytes(64)

        if len(self.key_bytes) < 32:
            raise ValueError("[SECURITY] Seed insuficiente (min 32 bytes) para escala global.")

    def sign_mac(self, message: bytes) -> bytes:
        """Gera um MAC soberano usando HMAC-SHA3-512."""
        return hmac.new(self.key_bytes, message, hashlib.sha3_512).digest()

    @staticmethod
    def byte_para_silaba(b: int) -> str:
        """Mapeia 1 byte (0-255) para uma sílaba pronunciável única."""
        idx_consoante = (b >> 4) & 0x0F
        idx_vogal = b & 0x0F
        return CONSOANTES[idx_consoante] + VOGAIS[idx_vogal]

    @staticmethod
    def silaba_para_byte(silaba: str) -> int:
        """Reverte uma sílaba para o seu byte original."""
        silaba = silaba.strip().lower()
        if not silaba:
            return 0
        try:
            c = silaba[0]
            v = silaba[1:]
            return (CONSOANTES.index(c) << 4) | VOGAIS.index(v)
        except (ValueError, IndexError):
            raise ValueError(f"[DIVERGENCIA] Materia fonetica corrompida: {silaba}")

    @staticmethod
    def bytes_para_frase(dados: bytes) -> str:
        """Converte bytes para string fonética separada por hifens."""
        return "-".join(Pysecurity1024.byte_para_silaba(b) for b in dados)

    @staticmethod
    def frase_para_bytes(frase: str) -> bytes:
        """Converte frase fonética de volta para bytes brutos."""
        if not frase:
            return b""
        partes = [s for s in frase.split("-") if s.strip()]
        return bytes(Pysecurity1024.silaba_para_byte(s) for s in partes)


def gerar_node_id_soberano(public_key: bytes) -> str:
    """
    Gera um ID fonético de 128-bit (16 sílabas).
    Usa SHA3-512 para garantir que chaves públicas similares gerem IDs opostos.
    """
    if isinstance(public_key, str):
        public_key = public_key.encode()
    digest = hashlib.sha3_512(public_key).digest()[:32]
    return Pysecurity1024.bytes_para_frase(digest)


def gerar_semente_aleatoria(bits: int = 512) -> bytes:
    """Gera bytes de alta entropia via CSPRNG."""
    return secrets.token_bytes(bits // 8)
