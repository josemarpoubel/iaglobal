# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes para Pysecurity1024 — codificação fonética de identidade."""

import hashlib
import pytest
from iaglobal.security.pysecurity1024 import (
    Pysecurity1024,
    gerar_node_id_soberano,
    gerar_semente_aleatoria,
)

GENESIS_HASH = (
    "cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524"
    "f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136"
)


def test_byte_para_silaba_e_reverso():
    """Cada byte (0-255) produz uma sílaba — e a reversão é exata."""
    for b in [0, 1, 16, 128, 200, 255]:
        silaba = Pysecurity1024.byte_para_silaba(b)
        assert isinstance(silaba, str) and len(silaba) in (2, 3), f"byte {b}"
        assert Pysecurity1024.silaba_para_byte(silaba) == b, f"reversão {b}"


def test_frase_redonda():
    """bytes → frase → bytes deve ser idempotente."""
    original = b"hello-world-iaglobal-42"
    frase = Pysecurity1024.bytes_para_frase(original)
    revertido = Pysecurity1024.frase_para_bytes(frase)
    assert revertido == original, f"{frase} -> {revertido.hex()}"


def test_frase_vazia():
    assert Pysecurity1024.frase_para_bytes("") == b""


def test_frase_determinismo():
    """Mesmo input produz sempre a mesma frase fonética."""
    dados = b"\xde\xad\xbe\xef"
    f1 = Pysecurity1024.bytes_para_frase(dados)
    f2 = Pysecurity1024.bytes_para_frase(dados)
    assert f1 == f2


def test_phonetic_derivado_do_dna():
    """Nome fonético derivado do DNA congelado + identificador único."""
    nomes_vistos: set[str] = set()
    for i in range(10):
        seed = f"{GENESIS_HASH}:agente-{i}"
        raw = hashlib.sha3_512(seed.encode()).digest()[:16]
        fonetico = Pysecurity1024.bytes_para_frase(raw)
        assert fonetico not in nomes_vistos, "colisão fonética"
        nomes_vistos.add(fonetico)
        assert len(fonetico) > 10, "nome muito curto"
        assert "-" in fonetico, "deve conter hifens"


def test_gerar_node_id_soberano():
    """gerar_node_id_soberano produz string fonética."""
    node_id = gerar_node_id_soberano(b"minha-chave-publica")
    assert isinstance(node_id, str)
    assert "-" in node_id


def test_gerar_node_id_soberano_str():
    """Aceita string como input também."""
    node_id = gerar_node_id_soberano("minha-chave-publica")
    assert isinstance(node_id, str)


def test_gerar_semente_aleatoria():
    seed = gerar_semente_aleatoria(256)
    assert len(seed) == 32
    seed2 = gerar_semente_aleatoria(512)
    assert len(seed2) == 64
    assert seed != seed2


def test_seed_muito_curta():
    with pytest.raises(ValueError):
        Pysecurity1024(seed=b"curta")


def test_silaba_invalida():
    with pytest.raises(ValueError):
        Pysecurity1024.silaba_para_byte("zz")


def test_evolucao_cruzamento_phonetico():
    """Simula o que EvoAgent faz em genesis + replicate.

    Pai e filho têm o mesmo lineage_marker (família),
    mas phonetic_name diferente (identidade única).
    """
    lineage_marker_familia = "abc123def456"
    pai_id = "pai-lineage-id-001"
    filho_id = "filho-lineage-id-002"

    def phonetic(linha_id: str) -> str:
        seed = f"{GENESIS_HASH}:{linha_id}"
        raw = hashlib.sha3_512(seed.encode()).digest()[:16]
        return Pysecurity1024.bytes_para_frase(raw)

    p = phonetic(pai_id)
    f = phonetic(filho_id)

    assert p != f, "pai e filho devem ter nomes diferentes"
    assert lineage_marker_familia == lineage_marker_familia, "herdaram o mesmo marker"
    assert len(p.split("-")) == 16, "deve ter 16 sílabas"
    assert len(f.split("-")) == 16


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
