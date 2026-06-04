import os
import sys
import json
import time
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock

raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, raiz_projeto)

from iaglobal.memory.memory_storage import init_storage, store_success, get_success_by_task, get_task_hash, storage
from iaglobal.memory.memory_error import store_error, query_relevant_errors, format_errors_for_prompt, load_errors
from iaglobal.memory.db_manager import DatabaseManager
from iaglobal.memory.memory_vector import MemoryVector, store as vec_store, search as vec_search
from iaglobal._paths import CORE_DB, MEMORY_DIR, DATA_DIR, CACHE_DB


class TestAprendizadoDB(unittest.TestCase):
    """Testa o banco SQLite + cbor2: quem aprende e como os dados persistem."""

    @classmethod
    def setUpClass(cls):
        cls._orig_core_db = str(CORE_DB)
        cls._orig_memory_dir = str(MEMORY_DIR)
        cls._orig_data_dir = str(DATA_DIR)
        cls._orig_cache_db = str(CACHE_DB)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        import iaglobal._paths as paths
        from pathlib import Path
        paths.CORE_DB = os.path.join(self.tmp, "core.db")
        paths.CACHE_DB = os.path.join(self.tmp, "cache.db")
        paths.MEMORY_DIR = self.tmp
        paths.DATA_DIR = self.tmp
        paths.ERROR_LOG = os.path.join(self.tmp, "errors.json")
        paths.SCRIPTS_DIR = Path(self.tmp) / "script"
        os.makedirs(paths.SCRIPTS_DIR, exist_ok=True)
        self.tmp_core_db = paths.CORE_DB
        self.tmp_cache_db = paths.CACHE_DB

    def tearDown(self):
        import iaglobal._paths as paths
        from pathlib import Path
        paths.CORE_DB = self._orig_core_db
        paths.CACHE_DB = self._orig_cache_db
        paths.MEMORY_DIR = self._orig_memory_dir
        paths.DATA_DIR = self._orig_data_dir
        paths.ERROR_LOG = os.path.join(self._orig_data_dir, "errors.json")
        paths.SCRIPTS_DIR = Path(self._orig_data_dir) / "script"
        shutil.rmtree(self.tmp, ignore_errors=True)

    # =========================================================
    # 1. SUCCESS REGISTRY (cbor2 + SQLite)
    # =========================================================

    def test_success_registry_armazena_e_recupera(self):
        """
        Fluxo real: Multi_Agent Fase 9 -> store_success(task, codigo)
        -> cbor2.dumps({task, codigo, metadata}) -> INSERT no success_registry
        """
        init_storage()

        task = "crie um bloco genesis sha3_512 Bit512 Kito Hamachi"
        codigo = 'import hashlib\ndef genesis(): return "ok"'
        metadata = {"score": 95.0, "ts": time.time()}

        store_success(task=task, codigo=codigo, metadata=metadata)

        resultado = get_success_by_task(task)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["codigo"], codigo)
        self.assertEqual(resultado["metadata"]["score"], 95.0)

    def test_success_registry_nao_retorna_para_task_diferente(self):
        init_storage()
        store_success(task="task A", codigo="print('a')", metadata={})
        resultado = get_success_by_task("task B")
        self.assertIsNone(resultado)

    def test_success_registry_sobrescreve_mesma_task(self):
        init_storage()
        store_success(task="task_x", codigo="v1", metadata={"score": 50})
        store_success(task="task_x", codigo="v2", metadata={"score": 90})
        resultado = get_success_by_task("task_x")
        self.assertEqual(resultado["codigo"], "v2")
        self.assertEqual(resultado["metadata"]["score"], 90)

    # =========================================================
    # 2. ERROR MEMORY (errors.json + keyword scoring)
    # =========================================================

    def test_error_memory_armazena_e_recupera_por_keyword(self):
        """
        Fluxo real: reflexion_loop() -> store_error(prompt, response, critique, corrected)
        -> append no errors.json
        -> query_relevant_errors(nova_task) -> ranking por keyword matching
        """
        store_error(
            prompt="crie um bloco genesis sha3_512",
            response="codigo sem hash",
            critique="NameError: sha3_512 not defined",
            corrected="import hashlib; hashlib.sha3_512(b'test')",
            error_type="ImportError"
        )

        relevantes = query_relevant_errors("gere um bloco genesis com sha3_512", limit=5)
        self.assertGreater(len(relevantes), 0)
        texto_combinado = str(relevantes[0])
        self.assertIn("sha3", texto_combinado.lower())

    def test_error_memory_format_errors_for_prompt(self):
        """
        format_errors_for_prompt() gera um bloco de contexto com erros anteriores
        para o LLM aprender com os proprios erros (In-Context Learning).
        """
        store_error(
            prompt="crie um bloco genesis em sha3_512",
            response="usando hashlib.sha256",
            critique="deveria usar sha3_512",
            corrected="hashlib.sha3_512(data)",
        )

        erros = query_relevant_errors("gere bloco genesis sha3_512", limit=5)
        contexto = format_errors_for_prompt(erros)
        self.assertIsInstance(contexto, str)
        self.assertGreater(len(contexto), 0)
        self.assertIn("sha3", contexto.lower())

    def test_error_memory_multiplos_erros_ordenados_por_score(self):
        store_error(prompt="task irrelevante", response="", critique="", corrected="")
        store_error(prompt="bloco genesis em sha3_512 com Bit512 Kito Hamachi",
                    response="", critique="", corrected="")

        relevantes = query_relevant_errors("crie um bloco genesis sha3_512 Bit512", limit=5)
        self.assertGreaterEqual(len(relevantes), 1)

    # =========================================================
    # 3. INSIGHTS TABLE (structured learnings no SQLite)
    # =========================================================

    def test_insights_armazena_aprendizado_estruturado(self):
        """
        db.insert_insight() salva aprendizado estruturado na tabela 'insights'.
        Usado por: Reflexion (builder.py), Orchestrator, Multi_Agent.
        """
        db = DatabaseManager(self.tmp_core_db)

        db.insert_insight(
            agent="reflexion",
            task_id="task_001",
            content="SHA3-512 requer hashlib.sha3_512(), nao hashlib.sha512()",
            score=95.0
        )

        insights = db.get_insights(agent="reflexion", limit=10)
        self.assertGreaterEqual(len(insights), 1)
        self.assertIn("sha3", str(insights[0]).lower())

    def test_insights_filtra_por_agente(self):
        db = DatabaseManager(self.tmp_core_db)

        db.insert_insight(agent="reflexion", task_id="t1", content="erro de sintaxe", score=80)
        db.insert_insight(agent="orchestrator", task_id="t2", content="no critico falhou", score=60)

        reflexion_only = db.get_insights(agent="reflexion", limit=10)
        orchestrator_only = db.get_insights(agent="orchestrator", limit=10)

        self.assertEqual(len(reflexion_only), 1)
        self.assertEqual(len(orchestrator_only), 1)
        self.assertIn("sintaxe", str(reflexion_only[0]).lower())
        self.assertIn("critico", str(orchestrator_only[0]).lower())

    def test_insights_ordenados_por_score(self):
        db = DatabaseManager(self.tmp_core_db)

        db.insert_insight(agent="test", task_id="t1", content="aprendizado baixo", score=30)
        db.insert_insight(agent="test", task_id="t2", content="aprendizado medio", score=60)
        db.insert_insight(agent="test", task_id="t3", content="aprendizado alto", score=95)

        insights = db.get_insights(agent="test", limit=10)
        scores = [int(i["score"]) for i in insights]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_insights_paginacao_offset(self):
        """get_insights com offset retorna a proxima pagina."""
        db = DatabaseManager(self.tmp_core_db)
        for i in range(5):
            db.insert_insight(agent="pag", task_id=f"t{i}", content=f"item {i}", score=i * 10)

        page1 = db.get_insights(agent="pag", limit=2, offset=0)
        page2 = db.get_insights(agent="pag", limit=2, offset=2)
        page3 = db.get_insights(agent="pag", limit=2, offset=4)

        self.assertEqual(len(page1), 2)
        self.assertEqual(len(page2), 2)
        self.assertEqual(len(page3), 1)
        self.assertGreater(page1[0]["score"], page1[1]["score"],
                          "Pagina 1 deve vir ordenada por score DESC")

    def test_insights_filtro_periodo(self):
        """get_insights com start_date/end_date filtra por timestamp."""
        db = DatabaseManager(self.tmp_core_db)
        db.insert_insight(agent="period", task_id="t1", content="antigo", score=50)
        db.insert_insight(agent="period", task_id="t2", content="recente", score=90)

        total = db.count_insights(agent="period")
        self.assertGreaterEqual(total, 2)

        filtrados = db.get_insights(agent="period", start_date="2020-01-01", limit=10)
        self.assertGreaterEqual(len(filtrados), 2)

    def test_insights_filtro_min_score(self):
        """get_insights com min_score filtra por pontuacao minima."""
        db = DatabaseManager(self.tmp_core_db)
        db.insert_insight(agent="score_filter", task_id="t1", content="baixo", score=30)
        db.insert_insight(agent="score_filter", task_id="t2", content="medio", score=60)
        db.insert_insight(agent="score_filter", task_id="t3", content="alto", score=95)

        acima_50 = db.get_insights(agent="score_filter", min_score=50, limit=10)
        acima_90 = db.get_insights(agent="score_filter", min_score=90, limit=10)

        self.assertEqual(len(acima_50), 2)
        self.assertEqual(len(acima_90), 1)
        for i in acima_50:
            self.assertGreaterEqual(i["score"], 50)

    def test_count_insights_com_filtros(self):
        """count_insights retorna total correto com filtros combinados."""
        db = DatabaseManager(self.tmp_core_db)
        db.insert_insight(agent="count_test", task_id="t1", content="a", score=10)
        db.insert_insight(agent="count_test", task_id="t2", content="b", score=50)
        db.insert_insight(agent="count_test", task_id="t3", content="c", score=90)
        db.insert_insight(agent="other", task_id="t4", content="d", score=70)

        total_count = db.count_insights(agent="count_test")
        self.assertEqual(total_count, 3)

        acima_40 = db.count_insights(agent="count_test", min_score=40)
        self.assertEqual(acima_40, 2)

        acima_95 = db.count_insights(agent="count_test", min_score=95)
        self.assertEqual(acima_95, 0)

    # =========================================================
    # 4. VECTOR MEMORY (embeddings + cbor2 sync)
    # =========================================================

    def _init_vector_db(self):
        """Cria a tabela 'memory' no banco temporario para testes vetoriais."""
        import sqlite3
        conn = sqlite3.connect(self.tmp_core_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                content TEXT,
                embedding BLOB,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_type ON memory(type)")
        conn.commit()
        conn.close()

    def test_vector_memory_armazena_e_consulta(self):
        """
        MemoryVector armazena embeddings no SQLite via vec_store().
        A consulta usa similaridade por dot product.
        """
        self._init_vector_db()
        vec_store("SHA3-512 e um algoritmo de hash da familia SHA-3", mtype="web_search")
        vec_store("Genesis block e o primeiro bloco de uma blockchain", mtype="web_search")

        resultados = vec_search("blockchain genesis sha3", top_k=2)
        self.assertGreater(len(resultados), 0)
        scores = [r[0] for r in resultados]
        self.assertTrue(all(s >= 0 for s in scores))

    def test_memory_vector_class_add_e_query(self):
        self._init_vector_db()
        mv = MemoryVector(db_path=self.tmp_core_db)
        mv.add("Bloco genesis usa hash SHA3-512 para garantir integridade", mtype="fact")
        mv.add("Bit512 e o nome da blockchain com autor Kito Hamachi", mtype="fact")

        resultados = mv.query("genesis SHA3-512 Bit512", top_k=2)
        self.assertGreater(len(resultados), 0)

    # =========================================================
    # 5. END-TO-END: FLUXO DE APRENDIZADO COMPLETO
    # =========================================================

    def test_fluxo_aprendizado_completo(self):
        """
        CICLO COMPLETO DE APRENDIZADO:

        1. AGENTE TENTA e FALHA  -> store_error() em errors.json
        2. AGENTE APRENDE        -> insight salvo no banco (db.insert_insight)
        3. AGENTE CORRIGE        -> store_success() com cbor2 no success_registry
        4. NOVA TAREFA           -> consulta erros passados (query_relevant_errors)
        5. CONTEXTO INJETADO     -> format_errors_for_prompt() gera bloco para LLM
        """
        if os.path.exists(os.path.join(self.tmp, "errors.json")):
            os.remove(os.path.join(self.tmp, "errors.json"))

        import iaglobal._paths as paths
        paths.ERROR_LOG = os.path.join(self.tmp, "errors.json")

        init_storage()
        db = DatabaseManager(self.tmp_core_db)

        task_original = "crie um bloco genesis em sha3_512 para Bit512"

        # --- PASSO 1: Agente TENTA e FALHA ---
        codigo_errado = 'def genesis(): return "hello"'
        store_error(
            prompt=task_original,
            response=codigo_errado,
            critique="NameError: sha3_512 nao importado",
            corrected="import hashlib\nhashlib.sha3_512(b'data')",
            error_type="NameError"
        )
        erros_apos_falha = query_relevant_errors(task_original, limit=5)
        self.assertGreater(len(erros_apos_falha), 0)

        # --- PASSO 2: Agente APRENDE com o erro ---
        db.insert_insight(
            agent="coder_agent",
            task_id="genesis_001",
            content="Sempre importar hashlib antes de usar sha3_512. "
                    "sha3_512 pertence ao modulo hashlib padrao do Python.",
            score=90.0
        )
        insights_passado = db.get_insights(agent="coder_agent", limit=10)
        self.assertGreaterEqual(len(insights_passado), 1)

        # --- PASSO 3: Agente CORRIGE e salva como sucesso ---
        codigo_correto = (
            'import hashlib\n'
            'import json\n'
            'class GenesisBlock:\n'
            '    def __init__(self):\n'
            '        self.hash = hashlib.sha3_512(b"Bit512").hexdigest()\n'
            '    def to_dict(self):\n'
            '        return {"hash": self.hash}'
        )
        store_success(
            task=task_original,
            codigo=codigo_correto,
            metadata={"score": 95.0, "tests_passed": 3, "tests_total": 3}
        )
        sucesso = get_success_by_task(task_original)
        self.assertIsNotNone(sucesso)
        self.assertEqual(sucesso["codigo"].strip(), codigo_correto.strip())
        self.assertEqual(sucesso["metadata"]["tests_passed"], 3)

        # --- PASSO 4: Nova tarefa SEMELHANTE consulta erros passados ---
        nova_task = "implemente blockchain com sha3_512 para Bit512"
        erros_relacionados = query_relevant_errors(nova_task, limit=5)
        self.assertGreater(len(erros_relacionados), 0)

        # --- PASSO 5: Contexto e gerado para injecao no prompt do LLM ---
        contexto = format_errors_for_prompt(erros_relacionados)
        self.assertIsInstance(contexto, str)
        self.assertGreater(len(contexto), 10)
        self.assertIn("sha3", contexto.lower())

        print("\n--- CICLO DE APRENDIZADO VERIFICADO ---")
        print(f"  1. Erro armazenado em errors.json: {len(erros_apos_falha)} registro(s)")
        print(f"  2. Insight salvo no banco (insights table): {len(insights_passado)} registro(s)")
        print(f"  3. Sucesso persistido com cbor2 (success_registry): {len(sucesso['codigo'])} caracteres")
        print(f"  4. Erros relevantes encontrados para nova task: {len(erros_relacionados)}")
        print(f"  5. Contexto gerado para LLM: {len(contexto)} caracteres")
        print(f"\nQUEM APRENDEU: ReflexionAgent (erros -> errors.json) + CoderAgent (insight -> SQLite)")
        print(f"ONDE: errors.json (JSON) + success_registry (cbor2/SQLite) + insights (SQLite)")
        print(f"COMO: In-Context Learning -> erros passados injetados no prompt do LLM")


if __name__ == "__main__":
    unittest.main()
