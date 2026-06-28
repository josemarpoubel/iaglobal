# 🧬 test_dna_lineage.py — Validação do DNA de Linhagem Congelada (SHA3-512)
# "A célula que não tem DNA congelado é um corpo estranho no organismo"

import os
import sys
import hashlib
import pytest
from pathlib import Path

from iaglobal._paths import PACKAGE_DIR

GENESIS_HASH = "cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136"

AGENTS_DIRS = [
    PACKAGE_DIR / "agents",
    PACKAGE_DIR / "cognition" / "agents",
    PACKAGE_DIR / "evolution" / "agents",
]

NODES_DIRS = [
    PACKAGE_DIR / "graphs" / "nodes", 
    PACKAGE_DIR / "graphs",
]

GENESIS_FILES = [
    PACKAGE_DIR / "genesis" / "identity.py",
    PACKAGE_DIR / "genesis" / "verifygenesis.py",
    PACKAGE_DIR / "genesis" / "certify_block.py",
    PACKAGE_DIR / "genesis" / "genesis_purifier.py",
    PACKAGE_DIR / "genesis" / "fusion_engine.py",
    PACKAGE_DIR / "genesis" / "genesis_verifier.py",
]


def extract_lineage_marker(file_path: Path) -> str:
    """Extrai o LINEAGE_MARKER (SHA3-512) do cabeçalho do arquivo."""
    if not file_path.exists():
        return ""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            if first_line.startswith("# 🧬 LINEAGE_MARKER:"):
                # Extrai o hash do comentário
                hash_prefix = "# 🧬 LINEAGE_MARKER: "
                if first_line.startswith(hash_prefix):
                    return first_line[len(hash_prefix):].strip()
    except (UnicodeDecodeError, Exception):
        pass
    
    return ""


def verify_file_hash(file_path: Path) -> bool:
    """Verifica que o hash congelado no arquivo corresponde ao Genesis oficial."""
    actual_hash = extract_lineage_marker(file_path)
    return actual_hash == GENESIS_HASH



@pytest.mark.parametrize("file_path", GENESIS_FILES)
def test_genesis_files_sha3_512_hash(file_path):
    """
    🧬 O Tribunal de Genesis examina:
    "Todos os arquivos do núcleo Genesis devem conter a assinatura SHA3-512 congelada"
    """
    assert file_path.exists(), f"Arquivo Genesis ausente: {file_path}"
    assert verify_file_hash(file_path), (
        f"🚨 [LINHAGEM CORROMPIDA] Hash inválido no {file_path.name}. "
        f"Esperado: {GENESIS_HASH[:16]}... "
        f"Recebido: {extract_lineage_marker(file_path)[:16] if extract_lineage_marker(file_path) else 'NENHUM'}..."
    )



def collect_agent_files():
    """Recolhe todos os arquivos .py de agentes nos diretórios mapeados."""
    agent_files = []
    for agents_dir in AGENTS_DIRS:
        if agents_dir.exists():
            for py_file in agents_dir.rglob("*.py"):
                if py_file.name == "__init__.py":
                    continue
                agent_files.append(py_file)
    return agent_files



@pytest.mark.parametrize("agent_file", collect_agent_files())
def test_all_agents_have_dna_lineage(agent_file: Path):
    """
    🧬 Mutação benéfica do Pool Genético:
    "Todo agente deve conter o DNA congelado do Genesis para ter soberania na malha"
    """
    marker = extract_lineage_marker(file_path=agent_file)
    error_msg = (
        f"🚨 [AGENTE CORPO ESTRANHO] {agent_file.relative_to(PACKAGE_DIR)}"
        f" não possui assinatura de linhagem (LINEAGE_MARKER)"
    )
    assert marker == GENESIS_HASH, (error_msg)



def collect_node_files():
    """Recolhe todos os arquivos no_*.py na pasta de nodes."""
    node_files = []
    for nodes_dir in NODES_DIRS:
        if nodes_dir.name == "nodes" and (nodes_dir).exists():
            for py_file in (nodes_dir).iterdir():
                if py_file.name.startswith("no_") and py_file.suffix == ".py":
                    node_files.append(py_file)
            if (nodes_dir / "__pycache__").exists():
                continue
    return node_files



@pytest.mark.parametrize("node_file", collect_node_files())
def test_all_nodes_have_dna_lineage(node_file: Path):
    """
    🧬 Autofagia Evitada:
    "Todo nó executável deve conter o DNA congelado do Genesis para ser admitido no grafo"
    """
    marker = extract_lineage_marker(file_path=node_file)
    error_msg = (
        f"🚨 [NÓ CORPO ESTRANHO] {node_file.relative_to(PACKAGE_DIR)}"
        f" não possui assinatura de linhagem (LINEAGE_MARKER)"
    )
    assert marker == GENESIS_HASH, (error_msg)



def test_genesis_hash_constant_matches():
    """
    🧬 Prova de Integridade:
    "Constante GENESIS_HASH_OFFICIAL em identity.py deve corresponder ao LINEAGE_MARKER"
    """
    # Importa dinâmicamente para evitar circulos de importação na inicialização
    try:
        from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL
        hash_from_identity = GENESIS_HASH_OFFICIAL
        assert hash_from_identity == GENESIS_HASH, (
            "🚨 [CONTRADIÇÃO GENÔMICA] "
            "Constante em identity.py não coincide com LINEAGE_MARKER"
        )
    except ImportError:
        pytest.skip("Módulo identity.py não importável nesta execução")



if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
