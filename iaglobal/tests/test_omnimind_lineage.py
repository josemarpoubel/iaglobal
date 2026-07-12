# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do registrar_agente da OmniMind — validação de DNA em paridade com o
GenesisTribunal + Pysecurity1024.

Cobertura (Fase A do ROADMAP.md):
  - Agente nativo registra o DNA congelado (GENESIS_HASH_OFFICIAL, 128 chars) e
    NÃO dispara "ALERTA DE PATÓGENO"; recebe phonetic_name reconstruído.
  - Agente com DNA divergente (128 chars) e sem valid_lineage NÃO é registrado.
  - Agente híbrido externo com metadados={"valid_lineage": True} faz bypass.
  - phonetic_name derivado é idêntico ao do GenesisTribunal (Pysecurity1024).

Não altera as Leis de Raymond Holliwell nem os Axiomas Biológicos — apenas a
checagem de identidade/DNA do registro de agentes.
"""
import hashlib
import logging

from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL
from iaglobal.obsidian.omnimind import OmniMind
from iaglobal.security.pysecurity1024 import Pysecurity1024

logging.basicConfig(level=logging.ERROR)  # silencia ruído de OmniMind


def _expected_phonetic(nome: str) -> str:
    raw = hashlib.sha3_512(f"{GENESIS_HASH_OFFICIAL}:{nome}".encode()).digest()[:16]
    return Pysecurity1024.bytes_para_frase(raw)


class TestOmniMindNativeLineage:
    """Agentes nativos registram o DNA oficial (128 chars)."""

    def test_nativo_registrado_sem_patogeno(self):
        om = OmniMind()
        om.registrar_agente(
            agent_id="evo-native-1",
            nome="evo-native",
            geracao=0,
            linhagem=GENESIS_HASH_OFFICIAL,
            metadados={"lineage_marker": "abcd1234efgh5678", "is_native": True},
        )
        assert "evo-native-1" in om._agentes_registrados
        rec = om._agentes_registrados["evo-native-1"]
        # DNA congelado preservado
        assert rec["linhagem"] == GENESIS_HASH_OFFICIAL
        # marker familiar mantido em metadados (gating de vacinas intacto)
        assert rec["metadados"]["lineage_marker"] == "abcd1234efgh5678"
        # phonetic_name reconstruído em paridade com o Tribunal
        assert rec["phonetic_name"] == _expected_phonetic("evo-native")
        assert rec["phonetic_name"].count("-") == 15  # 16 sílabas


class TestOmniMindDivergenteLineage:
    """DNA divergente sem valid_lineage deve ser rejeitado (patógeno)."""

    def test_dna_divergente_rejeitado(self):
        om = OmniMind()
        divergente = "0" * 128  # 128 chars, mas não é o DNA oficial
        om.registrar_agente(
            agent_id="evo-fake-1",
            nome="evo-fake",
            geracao=0,
            linhagem=divergente,
        )
        assert "evo-fake-1" not in om._agentes_registrados


class TestOmniMindHybridBypass:
    """Agente híbrido externo com valid_lineage faz bypass consciente."""

    def test_hibrido_com_valid_lineage(self):
        om = OmniMind()
        om.registrar_agente(
            agent_id="hybrid-1",
            nome="hybrid-agent",
            geracao=0,
            linhagem="external-hybrid-x",
            metadados={"valid_lineage": True, "origin": "remote"},
        )
        assert "hybrid-1" in om._agentes_registrados
        assert om._agentes_registrados["hybrid-1"]["metadados"]["origin"] == "remote"
