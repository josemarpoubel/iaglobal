# iaglobal/genesis/genesis_verifier.py

import hashlib
import os
import logging

from iaglobal.utils.logger import get_logger

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
    with open(genesis_file_path, 'rb') as f:
        file_bytes = f.read()

    # Calcula o hash SHA3-512 sobre os bytes EXATOS do arquivo
    calculated_hash = hashlib.sha3_512(file_bytes).hexdigest()

    # Log para comparação manual se necessário
    # print(f"DEBUG - Real: {calculated_hash}")
    # print(f"DEBUG - Gold: {expected_hash}")

    return calculated_hash == expected_hash
