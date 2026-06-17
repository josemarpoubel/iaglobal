# test_salvar_telemetria.py

import unittest
import sqlite3
import cbor2

def salvar_telemetria_producao(cursor, prompt, tokens_in):
    """
    Regra de negócio: Se não há tokens ou o prompt está vazio, 
    não gasta armazenamento nem telemetria.
    """
    if tokens_in <= 0 or not prompt or not prompt.strip():
        return False
    
    payload = {"prompt": prompt, "tokens_in": tokens_in}
    dados_cbor = cbor2.dumps(payload)
    cursor.execute("INSERT INTO events (data) VALUES (?)", (dados_cbor,))
    return True

# --- Suíte de Testes ---
class TestTelemetria(unittest.TestCase):

    def setUp(self):
        """Configura um banco em memória antes de cada teste."""
        self.conn = sqlite3.connect(":memory:")
        self.cursor = self.conn.cursor()
        self.cursor.execute("CREATE TABLE events (data BLOB)")

    def tearDown(self):
        """Limpa o banco após cada teste."""
        self.conn.close()

    def test_descarte_quando_tokens_sao_zero(self):
        """Verifica se a função descarta corretamente dados com tokens zerados."""
        prompt = "Qualquer prompt"
        tokens_in = 0
        
        resultado = salvar_telemetria_producao(self.cursor, prompt, tokens_in)
        
        # O resultado deve ser False e nada deve estar no banco
        self.assertFalse(resultado, "A função deveria retornar False para tokens=0")
        self.cursor.execute("SELECT count(*) FROM events")
        self.assertEqual(self.cursor.fetchone()[0], 0, "O banco deveria estar vazio")

    def test_sucesso_quando_dados_validos(self):
        """Verifica se a função persiste dados corretamente quando válidos."""
        prompt = "Olá, mundo!"
        tokens_in = 10
        
        resultado = salvar_telemetria_producao(self.cursor, prompt, tokens_in)
        
        self.assertTrue(resultado)
        self.cursor.execute("SELECT count(*) FROM events")
        self.assertEqual(self.cursor.fetchone()[0], 1, "O evento deveria ter sido gravado")

if __name__ == "__main__":
    unittest.main()
