# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/genesis/genesis_verifier.py

import hashlib
import os
import logging


logger = logging.getLogger("iaglobal")


def verify_genesis_hash(genesis_file_path, expected_hash):
    """
    Verifica a integridade absoluta byte-a-byte.
    Se um único bit mudar no arquivo físico, o hash não baterá.
    """
    if not os.path.exists(genesis_file_path):
        return False

    # ESTRATÉGIA: LEITURA BRUTA (Raw Binary)
    # Não carregamos com cbor2.load(), lemos os bytes puros do disco.
    with open(genesis_file_path, "rb") as f:
        file_bytes = f.read()

    # Calcula o hash SHA3-512 sobre os bytes EXATOS do arquivo
    calculated_hash = hashlib.sha3_512(file_bytes).hexdigest()

    # Log para comparação manual se necessário
    # print(f"DEBUG - Real: {calculated_hash}")
    # print(f"DEBUG - Gold: {expected_hash}")

    return calculated_hash == expected_hash
