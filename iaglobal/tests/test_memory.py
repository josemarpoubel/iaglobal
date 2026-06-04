import os
import sys
import json
import unittest
import tempfile
from unittest.mock import patch, MagicMock

raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_path = os.path.join(raiz_projeto, "src")
if raiz_projeto not in sys.path:
    sys.path.insert(0, raiz_projeto)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from iaglobal.memory.memory import carregar, salvar
from iaglobal.memory.memory_storage import init_storage, store_success, get_success_by_task, get_task_hash
from iaglobal.memory.memory_error import load_errors, save_errors, store_error, query_relevant_errors, format_errors_for_prompt
from iaglobal.memory.cache import get, set, hash_prompt, _cache
import iaglobal._paths as paths


class TestMemoryFile(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.original_data_dir = paths.DATA_DIR
        self.original_evolucao = paths.EVOLUTION_DOC
        paths.DATA_DIR = self.tmp_dir
        paths.EVOLUTION_DOC = os.path.join(self.tmp_dir, "evolucao_cerebral.md")

    def tearDown(self):
        paths.DATA_DIR = self.original_data_dir
        paths.EVOLUTION_DOC = self.original_evolucao
        for f in os.listdir(self.tmp_dir):
            os.remove(os.path.join(self.tmp_dir, f))
        os.rmdir(self.tmp_dir)

    def test_salvar_e_carregar_texto(self):
        salvar("teste de memoria")
        conteudo = carregar()
        self.assertIn("teste de memoria", conteudo)

    def test_carregar_sem_arquivo_retorna_vazia(self):
        resultado = carregar()
        self.assertEqual(resultado, "memória vazia")

    def test_salvar_acumula_conteudo(self):
        salvar("linha 1")
        salvar("linha 2")
        conteudo = carregar()
        self.assertIn("linha 1", conteudo)
        self.assertIn("linha 2", conteudo)


class TestMemoryStorage(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.original_cache_db = paths.CACHE_DB
        self.original_core_db = paths.CORE_DB
        self.original_memory_dir = paths.MEMORY_DIR
        paths.MEMORY_DIR = self.tmp_dir
        paths.CACHE_DB = os.path.join(self.tmp_dir, "cache.db")
        paths.CORE_DB = os.path.join(self.tmp_dir, "core.db")
        init_storage()

    def tearDown(self):
        paths.CACHE_DB = self.original_cache_db
        paths.CORE_DB = self.original_core_db
        paths.MEMORY_DIR = self.original_memory_dir
        for f in os.listdir(self.tmp_dir):
            os.remove(os.path.join(self.tmp_dir, f))
        os.rmdir(self.tmp_dir)

    def test_init_storage_cria_tabela(self):
        import sqlite3
        conn = sqlite3.connect(os.path.join(self.tmp_dir, "core.db"))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        self.assertIn("success_registry", tables)

    def test_get_task_hash_consistente(self):
        h1 = get_task_hash("  Tarefa Teste  ")
        h2 = get_task_hash("tarefa teste")
        self.assertEqual(h1, h2)

    def test_get_task_hash_diferente_para_tarefas_diferentes(self):
        h1 = get_task_hash("tarefa a")
        h2 = get_task_hash("tarefa b")
        self.assertNotEqual(h1, h2)

    def test_store_e_get_success(self):
        store_success("calcular soma", "def soma(a,b): return a+b", {"tipo": "matematica"})
        resultado = get_success_by_task("calcular soma")
        self.assertIsNotNone(resultado)
        self.assertIn("codigo", resultado)
        self.assertEqual(resultado["codigo"], "def soma(a,b): return a+b")
        self.assertEqual(resultado["metadata"]["tipo"], "matematica")

    def test_get_success_inexistente_retorna_none(self):
        resultado = get_success_by_task("tarefa_que_nunca_existiu")
        self.assertIsNone(resultado)

    def test_store_success_substitui_hash_existente(self):
        store_success("task", "v1")
        store_success("task", "v2")
        resultado = get_success_by_task("task")
        self.assertEqual(resultado["codigo"], "v2")


class TestMemoryError(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.original_errors = paths.ERROR_LOG
        self.original_memory_dir = paths.MEMORY_DIR
        paths.MEMORY_DIR = self.tmp_dir
        paths.ERROR_LOG = os.path.join(self.tmp_dir, "errors.json")

    def tearDown(self):
        paths.ERROR_LOG = self.original_errors
        paths.MEMORY_DIR = self.original_memory_dir
        if os.path.exists(os.path.join(self.tmp_dir, "errors.json")):
            os.remove(os.path.join(self.tmp_dir, "errors.json"))
        os.rmdir(self.tmp_dir)

    def test_load_errors_sem_arquivo_retorna_vazio(self):
        self.assertEqual(load_errors(), [])

    def test_save_e_load_errors(self):
        dados = [{"id": "1", "error_type": "RuntimeError"}]
        save_errors(dados)
        carregados = load_errors()
        self.assertEqual(len(carregados), 1)
        self.assertEqual(carregados[0]["error_type"], "RuntimeError")

    def test_store_error_adiciona_entrada(self):
        store_error("prompt", "resposta", "critica", "corrigido", "SecurityError")
        erros = load_errors()
        self.assertEqual(len(erros), 1)
        self.assertEqual(erros[0]["error_type"], "SecurityError")
        self.assertEqual(erros[0]["prompt"], "prompt")
        self.assertEqual(erros[0]["codigo_corrigido"], "corrigido")

    def test_store_error_multiplos_acumula(self):
        store_error("p1", "r1", "c1", "c1")
        store_error("p2", "r2", "c2", "c2")
        self.assertEqual(len(load_errors()), 2)

    def test_query_relevant_errors_sem_erros(self):
        result = query_relevant_errors("teste")
        self.assertEqual(result, [])

    def test_query_relevant_errors_com_keywords(self):
        store_error("criar um servidor flask", "codigo flask", "erro de rota", "corrigido")
        result = query_relevant_errors("preciso criar um servidor", limit=5)
        self.assertGreaterEqual(len(result), 1)

    def test_query_relevant_errors_sem_match_retorna_ultimos(self):
        store_error("assunto A", "cod A", "crit A", "cor A")
        store_error("assunto B", "cod B", "crit B", "cor B")
        result = query_relevant_errors("xyz sem match nenhum", limit=2)
        self.assertGreaterEqual(len(result), 0)

    def test_format_errors_for_prompt_vazio(self):
        self.assertEqual(format_errors_for_prompt([]), "")

    def test_format_errors_for_prompt_com_erros(self):
        erros = [{"error_type": "SecurityError", "prompt": "teste", "response_errada": "bad code", "critica_sandbox": "falha", "codigo_corrigido": "good code"}]
        resultado = format_errors_for_prompt(erros)
        self.assertIn("HISTÓRICO DE ERROS EVITADOS", resultado)
        self.assertIn("SecurityError", resultado)
        self.assertIn("good code", resultado)


class TestCache(unittest.TestCase):
    def setUp(self):
        _cache.clear()

    def test_hash_prompt_consistente(self):
        self.assertEqual(hash_prompt("teste"), hash_prompt("teste"))

    def test_get_sem_cache_retorna_none(self):
        resultado = get("chave_qualquer")
        self.assertIsNone(resultado)

    def test_set_e_get(self):
        set("minha_chave", "minha_resposta")
        resultado = get("minha_chave")
        self.assertEqual(resultado, "minha_resposta")

    def test_cache_diferente_para_chaves_diferentes(self):
        set("chave1", "valor1")
        set("chave2", "valor2")
        self.assertEqual(get("chave1"), "valor1")
        self.assertEqual(get("chave2"), "valor2")

    def test_cache_sobrescreve(self):
        set("chave", "valor_original")
        set("chave", "valor_novo")
        self.assertEqual(get("chave"), "valor_novo")

    @patch('iaglobal.memory.cache.get_success_by_task')
    def test_get_fallback_para_l2_quando_l1_vazio(self, mock_l2):
        mock_l2.return_value = {"codigo": "codigo_l2"}
        resultado = get("task_teste_l2")
        self.assertEqual(resultado, "codigo_l2")

    @patch('iaglobal.memory.cache.get_success_by_task')
    def test_get_fallback_l2_popula_l1(self, mock_l2):
        mock_l2.return_value = {"codigo": "codigo_l2"}
        get("task_teste_l2")
        self.assertIn(hash_prompt("task_teste_l2"), _cache)


class TestMemoryVector(unittest.TestCase):
    @patch('iaglobal.memory.memory_vector._get_model')
    def test_store_com_texto_valido(self, mock_get_model):
        import numpy as np
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        mock_get_model.return_value = mock_model
        import iaglobal.memory.memory_vector as mv
        original_core_db = paths.CORE_DB
        original_memory_dir = paths.MEMORY_DIR
        with tempfile.TemporaryDirectory() as tmp:
            paths.MEMORY_DIR = tmp
            paths.CORE_DB = os.path.join(tmp, "core.db")
            mv.init_db()
            mv.store("texto de teste", "fact")
            import sqlite3
            conn = sqlite3.connect(paths.CORE_DB)
            rows = conn.execute("SELECT content, type FROM memory").fetchall()
            conn.close()
        paths.CORE_DB = original_core_db
        paths.MEMORY_DIR = original_memory_dir
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "texto de teste")

    @patch('iaglobal.memory.memory_vector._get_model')
    def test_store_texto_vazio_nao_insere(self, mock_get_model):
        import iaglobal.memory.memory_vector as mv
        original_core_db = paths.CORE_DB
        original_memory_dir = paths.MEMORY_DIR
        with tempfile.TemporaryDirectory() as tmp:
            paths.MEMORY_DIR = tmp
            paths.CORE_DB = os.path.join(tmp, "core.db")
            mv.init_db()
            mv.store("", "fact")
            mv.store("   ", "fact")
            import sqlite3
            conn = sqlite3.connect(paths.CORE_DB)
            rows = conn.execute("SELECT count(*) FROM memory").fetchall()
            conn.close()
        paths.CORE_DB = original_core_db
        paths.MEMORY_DIR = original_memory_dir
        self.assertEqual(rows[0][0], 0)

    @patch('iaglobal.memory.memory_vector._get_model')
    def test_search_retorna_resultados(self, mock_get_model):
        import sqlite3
        import numpy as np
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        mock_get_model.return_value = mock_model
        import iaglobal.memory.memory_vector as mv
        original_core_db = paths.CORE_DB
        original_memory_dir = paths.MEMORY_DIR
        with tempfile.TemporaryDirectory() as tmp:
            paths.MEMORY_DIR = tmp
            paths.CORE_DB = os.path.join(tmp, "core.db")
            mv.init_db()
            vec = np.array([0.1, 0.2, 0.3], dtype=np.float32).tobytes()
            conn = sqlite3.connect(paths.CORE_DB)
            conn.execute("INSERT INTO memory (type, content, embedding) VALUES (?,?,?)",
                        ("fact", "teste", vec))
            conn.commit()
            conn.close()
            results = mv.search("consulta")
        paths.CORE_DB = original_core_db
        paths.MEMORY_DIR = original_memory_dir
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("text", results[0][1])

    @patch('iaglobal.memory.memory_vector._get_model')
    def test_search_sem_resultados_retorna_vazio(self, mock_get_model):
        import numpy as np
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.5, 0.5, 0.5], dtype=np.float32)
        mock_get_model.return_value = mock_model
        import iaglobal.memory.memory_vector as mv
        original_core_db = paths.CORE_DB
        original_memory_dir = paths.MEMORY_DIR
        with tempfile.TemporaryDirectory() as tmp:
            paths.MEMORY_DIR = tmp
            paths.CORE_DB = os.path.join(tmp, "core.db")
            mv.init_db()
            results = mv.search("consulta")
        paths.CORE_DB = original_core_db
        paths.MEMORY_DIR = original_memory_dir
        self.assertEqual(results, [])

    def test_search_query_vazia_retorna_vazio(self):
        import iaglobal.memory.memory_vector as mv
        results = mv.search("")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
