# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/genesis/certify_block.py

# (Selo de Autenticidade)

import hashlib
import cbor2
import logging
import os

from iaglobal.genesis.genesis_verifier import verify_genesis_hash


logger = logging.getLogger("iaglobal")


def get_genesis_hash_from_file(genesis_file_path: str) -> str:
    """
    Calcula o hash SHA3-512 determinístico de um arquivo CBOR.
    Usa o modo canônico para garantir que a ordem das chaves não mude o hash.
    """
    if not os.path.exists(genesis_file_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {genesis_file_path}")

    with open(genesis_file_path, "rb") as f:
        # Carregamos os dados brutos
        genesis_data = cbor2.load(f)

    # 🛡️ DETERMINISMO: Força a ordenação das chaves antes do hash
    serialized_genesis = cbor2.dumps(genesis_data, canonical=True)

    # SHA3-512: O padrão ouro do Multiverso WebHidden
    return hashlib.sha3_512(serialized_genesis).hexdigest()


def verify_genesis_integrity():
    """
    Compara a realidade atual (Evolutivo) com o DNA original (Blueprint).
    Faz duas checagens:
    1. Hash lógico (conteúdo CBOR canônico).
    2. Hash físico (byte-a-byte do arquivo).
    """
    # Caminhos alinhados com a estrutura real do projeto
    base_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "genesis", "data"
    )
    evolutive_path = os.path.join(base_dir, "webhidden_genesis_evolutive.cbor")
    blueprint_path = os.path.join(base_dir, "webhidden_genesis_blueprint.cbor")

    logging.info("⚖️ Iniciando Tribunal de Integridade do Genesis...")

    try:
        # 1. Calcula o Hash da Realidade Atual (conteúdo CBOR)
        calculated_hash = get_genesis_hash_from_file(evolutive_path)
        logging.info(f"🔍 Hash Atual (CBOR): {calculated_hash[:16]}...")

        # 2. Carrega a Verdade Congelada (Blueprint)
        if not os.path.exists(blueprint_path):
            logging.error(
                "🚨 CRITICAL: Blueprint original não encontrado! O nó está órfão."
            )
            return False

        with open(blueprint_path, "rb") as f:
            blueprint_data = cbor2.load(f)

        blueprint_hash = blueprint_data.get("hash")
        if not blueprint_hash:
            logging.warning(
                "⚠️ Blueprint não contém um campo 'hash'. Tentando calcular hash do conteúdo do blueprint..."
            )
            serialized_blueprint = cbor2.dumps(blueprint_data, canonical=True)
            blueprint_hash = hashlib.sha3_512(serialized_blueprint).hexdigest()

        # 3. Verificação byte-a-byte (hash físico)
        if not verify_genesis_hash(evolutive_path, blueprint_hash):
            logging.error(
                "❌ VIOLAÇÃO DE REALIDADE: O arquivo físico não corresponde ao hash esperado!"
            )
            return False

        # 4. O Veredito
        if calculated_hash == blueprint_hash:
            logging.info(
                "✅ CONSENSO: O Genesis evolutivo é legítimo. Realidade confirmada."
            )
            return True
        else:
            logging.error(
                "❌ VIOLAÇÃO DE REALIDADE: O hash lógico não bate com o Blueprint!"
            )
            logging.error(f"Esperado: {blueprint_hash[:16]}...")
            logging.error(f"Encontrado: {calculated_hash[:16]}...")
            return False

    except Exception as e:
        logging.error(f"💥 Falha catastrófica na certificação: {e}")
        return False


if __name__ == "__main__":
    # Se rodar este script diretamente, ele faz o diagnóstico
    success = verify_genesis_integrity()
    if not success:
        exit(1)  # Código de erro para impedir o bootstrap do Multiverso
