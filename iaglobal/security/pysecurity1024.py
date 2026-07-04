# iaglobal/security/pysecurity1024.py

import secrets
import hmac
import hashlib
import logging
import re

from typing import Optional, List

logger = logging.getLogger("PySecurity")

# Matriz 16x16: A fundação da identidade auditável
# Cada combinação Consoante + Vogal representa exatamente 1 byte (0-255)
CONSOANTES = ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v']
VOGAIS = ['a', 'e', 'i', 'o', 'u', 'y', 'w', 'ae', 'ai', 'ao', 'au', 'ea', 'ei', 'eo', 'eu', 'ou']

class Pysecurity1024:
    """
    Motor de Segurança Baseado em HMAC-SHA3-512 e codificação fonética.
    V8.2: Correção de entropia e fatiamento fonético resiliente.
    """
    
    def __init__(self, seed: Optional[bytes] = None):
        # 🎲 Garante entropia real se a seed for nula (Tchau, Gardenal!)
        self.key_bytes = seed or secrets.token_bytes(64)
        
        if len(self.key_bytes) < 32:
            raise ValueError("🛡️ [SECURITY] Seed insuficiente (min 32 bytes) para escala global.")

    def sign_mac(self, message: bytes) -> bytes:
        """Gera um MAC soberano usando HMAC-SHA3-512."""
        return hmac.new(self.key_bytes, message, hashlib.sha3_512).digest()

    @staticmethod
    def byte_para_silaba(b: int) -> str:
        """Mapeia 1 byte (0-255) para uma sílaba pronunciável única."""
        # 4 bits altos para consoante, 4 bits baixos para vogal
        idx_consoante = (b >> 4) & 0x0F
        idx_vogal = b & 0x0F
        return CONSOANTES[idx_consoante] + VOGAIS[idx_vogal]

    @staticmethod
    def silaba_para_byte(silaba: str) -> int:
        """Reverte uma sílaba para o seu byte original (Inverso da Matriz 16x16)."""
        silaba = silaba.strip().lower()
        if not silaba: return 0
        
        # 🧠 O DESAFIO: Vogais podem ter 1 ou 2 caracteres.
        # Como as consoantes são sempre 1 char (Matriz 16x16), pegamos o resto.
        try:
            c = silaba[0]
            v = silaba[1:]
            
            return (CONSOANTES.index(c) << 4) | VOGAIS.index(v)
        except (ValueError, IndexError):
            raise ValueError(f"🧬 [DIVERGÊNCIA] Matéria fonética corrompida: {silaba}")

    @staticmethod
    def bytes_para_frase(dados: bytes) -> str:
        """Converte bytes para string fonética separada por hifens."""
        return "-".join(Pysecurity1024.byte_para_silaba(b) for b in dados)

    @staticmethod
    def frase_para_bytes(frase: str) -> bytes:
        """Converte frase fonética de volta para bytes brutos."""
        if not frase: return b""
        # Remove espaços e limpa hifens duplos
        partes = [s for s in frase.split("-") if s.strip()]
        return bytes(Pysecurity1024.silaba_para_byte(s) for s in partes)

# --- API de Conveniência (Soberania de Identidade) ---

def gerar_node_id_soberano(public_key: bytes) -> str:
    """
    🚀 ALGORITMO FÊNIX: Gera um ID fonético de 128-bit (16 sílabas).
    Usa SHA3-512 para garantir que chaves públicas similares gerem IDs opostos.
    """
    # 16 bytes de SHA3 = 256 bits de entropia = Desprezível probabilidade de colisão
    digest = hashlib.sha3_512(public_key).digest()[:32]
    return Pysecurity1024.bytes_para_frase(digest)

def gerar_semente_aleatoria(bits: int = 512) -> bytes:
    """Gera bytes de alta entropia via CSPRNG (Hardware Noise)."""
    return secrets.token_bytes(bits // 8)
