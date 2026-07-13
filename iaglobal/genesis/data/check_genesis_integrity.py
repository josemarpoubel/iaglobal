# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/genesis/test_genesis_integrity.py

import os
import hashlib
import cbor2
import sys


def calculate_file_hash(file_path: str) -> str:
    """
    Calcula SHA3-512 diretamente dos bytes do arquivo.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    with open(file_path, "rb") as f:
        return hashlib.sha3_512(f.read()).hexdigest()


def load_blueprint_hash(blueprint_path: str) -> str:
    """
    Extrai o hash armazenado no blueprint.
    """
    if not os.path.exists(blueprint_path):
        raise FileNotFoundError(f"Blueprint não encontrado: {blueprint_path}")

    with open(blueprint_path, "rb") as f:
        data = cbor2.load(f)

    if "hash" not in data:
        raise ValueError("Blueprint inválido: campo 'hash' ausente")

    return data["hash"]


def test_genesis_origin():
    """
    Teste principal:
    Verifica se o blueprint foi gerado a partir do arquivo evolutivo.
    """
    base_dir = os.path.dirname(__file__)

    evolutive_path = os.path.join(base_dir, "webhidden_genesis_evolutive.cbor")
    blueprint_path = os.path.join(base_dir, "webhidden_genesis_blueprint.cbor")

    print("\n🧪 Iniciando teste de origem do Genesis...\n")

    try:
        # 1. Hash real do arquivo evolutivo
        real_hash = calculate_file_hash(evolutive_path)
        print(f"🔍 Hash calculado: {real_hash[:32]}...")

        # 2. Hash armazenado no blueprint
        blueprint_hash = load_blueprint_hash(blueprint_path)
        print(f"📜 Hash no blueprint: {blueprint_hash[:32]}...")

        # 3. Comparação
        if real_hash == blueprint_hash:
            print("\n✅ TESTE PASSOU: O blueprint foi gerado a partir do evolutivo.")
            return True
        else:
            print("\n❌ TESTE FALHOU: O blueprint NÃO corresponde ao evolutivo.")
            return False

    except Exception as e:
        print(f"\n💥 ERRO NO TESTE: {e}")
        return False


if __name__ == "__main__":
    success = test_genesis_origin()
    sys.exit(0 if success else 1)
