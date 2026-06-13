"""
Teste para garantir que imports repetidos não alteram arquivos JSON persistentes.
"""
import json
import tempfile
import shutil
from pathlib import Path


def test_imports_do_not_mutate_json_files():
    """
    Garante que realizar múltiplos imports de módulos globais
    não cause corrupção ou alteração indevida de arquivos JSON.
    """
    # Copiar todos os JSONs importantes para um diretório temporário
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # Arquivos JSON críticos que são frequentemente lidos/escritos
        json_files = [
            "memory/data/knowledge.json",
            "memory/data/provider_state.json",
            "memory/data/meta_evolution.json",
            "memory/data/errors.json",
            "memory/data/insights.json",
        ]

        backups = {}
        for jf in json_files:
            src = Path(__file__).resolve().parent.parent.parent / jf
            dst = temp_dir / Path(jf).name
            if src.exists():
                shutil.copy2(src, dst)
                backups[jf] = dst
            else:
                # Arquivo não existe, pulamos
                continue

        # Realizar importação múltiplas vezes para garantir idempotência
        for _ in range(3):
            try:
                # Simular o que acontece quando múltiplos handlers são executados
                from iaglobal._paths import DATA_ROOT
                from iaglobal.memory.memory_storage import storage
                from iaglobal.providers.provider_state import provider_state
                from iaglobal.evolution.meta_evolution import meta_evolution

                # Ler novamente para confirmar que arquivos não foram alterados
                for jf, backup_path in backups.items():
                    current_path = Path(__file__).resolve().parent.parent.parent / jf
                    if current_path.exists():
                        with open(current_path) as f:
                            current_content = json.load(f)
                        with open(backup_path) as f:
                            original_content = json.load(f)
                        assert current_content == original_content, (
                            f"Arquivo {jf} foi alterado após import!
                            "
                            f"Conteúdo original: {original_content}\
"
                            f"Conteúdo atual: {current_content}"
                        )

            except Exception as e:
                raise AssertionError(f"Importação causou erro ou alterou estado: {e}")

        print("[PASS] Todos os imports são idempotentes — arquivos JSON preservados.")

    finally:
        # Restaurar arquivos originais se existiam
        for jf, backup_path in backups.items():
            src = Path(__file__).resolve().parent.parent.parent / jf
            if src.exists():
                shutil.copy2(backup_path, src)
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_imports_do_not_mutate_json_files()