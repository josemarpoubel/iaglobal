import subprocess
import tempfile
import os
from brain import escolher_modelo
from executor import executar


MAX_ITERS = 5


def executar_codigo(codigo):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as f:
        f.write(codigo.encode())
        path = f.name

    try:
        result = subprocess.run(
            ["python3", path],
            capture_output=True,
            text=True,
            timeout=5
        )

        return result.returncode, result.stdout, result.stderr

    except Exception as e:
        return -1, "", str(e)

    finally:
        os.remove(path)

def auto_train(task):

    modelo = escolher_modelo(task)

    prompt = f"""
Você é um engenheiro Python.

Resolva o problema abaixo gerando APENAS código executável:

PROBLEMA:
{task}
"""

    codigo = executar(modelo, prompt)

    for i in range(MAX_ITERS):

        code = extrair_codigo(codigo)

        status, out, err = executar_codigo(code)

        if status == 0:
            return code, out

        # 🔥 CORREÇÃO INTELIGENTE
        fix_prompt = f"""
O código falhou.

ERRO:
{err}

CÓDIGO:
{code}

Corrija e devolva apenas o código completo funcionando.
"""

        codigo = executar(modelo, fix_prompt)

    return None, "falhou após tentativas"

import re

def extrair_codigo(texto):
    match = re.search(r"```python(.*?)```", texto, re.DOTALL)
    if match:
        return match.group(1).strip()
    return texto
    
    store_error(
    prompt=task,
    response=code,
    critique=err,
    corrected="auto-fixed-success"
)
