# refactor_metabolic.py

import os
import ast
import subprocess

# CONFIGURAÇÕES DE PROTEÇÃO
DRY_RUN = True  # Mude para False somente após testar
TARGET_DIR = '/home/kitohamachi/iaglobal-main/iaglobal'

def validate_and_format(filepath):
    """
    Usa o 'ruff' para formatar o arquivo de forma segura.
    Se o ruff não puder formatar, o arquivo está corrompido.
    """
    try:
        # Tenta verificar a sintaxe com ast
        with open(filepath, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        
        # Se for válido, formata usando ruff (padrão da indústria)
        if not DRY_RUN:
            subprocess.run(["ruff", "format", filepath], check=True)
            print(f"✅ Formatação aplicada: {os.path.basename(filepath)}")
        else:
            print(f"🔍 Verificado (DRY_RUN): {os.path.basename(filepath)}")
        return True
        
    except (SyntaxError, Exception) as e:
        print(f"❌ Erro sintático crítico em {filepath}: {e}")
        return False

def run_recursive(root_dir):
    print(f"🚀 Iniciando varredura metabólica... (DRY_RUN={DRY_RUN})")
    for root, _, files in os.walk(root_dir):
        for file in files:
            # Pula a si mesmo e a pasta de trabalho (work)
            if file.endswith('.py') and file != 'refactor_metabolic.py' and 'work' not in root:
                full_path = os.path.join(root, file)
                validate_and_format(full_path)

if __name__ == "__main__":
    run_recursive(TARGET_DIR)
