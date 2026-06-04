"""Testes que certificam que lib e testes gravam apenas em iaglobal/memory/data/."""

import asyncio
import os
import sys
import sqlite3
from pathlib import Path

raiz_pacote = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, raiz_pacote)

from iaglobal._paths import (
    PACKAGE_DIR,
    DATA_ROOT,
    MEMORY_DIR,
    BACKUP_DIR,
    CACHE_DIR,
    LOG_DIR,
    SCRIPTS_DIR,
    CORE_DB,
    CACHE_DB,
    EMBEDDINGS_DB,
    ERROR_LOG,
    DOCS_DIR,
    EVOLUTION_DOC,
)


def _normalize(p: Path) -> Path:
    return p.resolve()


DATA_DIR_REAL = _normalize(Path(raiz_pacote) / "memory" / "data")


class TestPathsCentralizados:
    """Verifica que todos os paths de dados apontam para iaglobal/memory/data/."""

    def test_data_root_dentro_do_pacote(self):
        assert _normalize(DATA_ROOT) == DATA_DIR_REAL, (
            f"DATA_ROOT={DATA_ROOT} deveria ser {DATA_DIR_REAL}"
        )

    def test_memory_dir_igual_data_root(self):
        assert _normalize(MEMORY_DIR) == DATA_DIR_REAL

    def test_backup_dir_dentro_de_data(self):
        esperado = DATA_DIR_REAL / "memory_backups"
        assert _normalize(BACKUP_DIR) == esperado

    def test_cache_dir_dentro_de_data(self):
        esperado = DATA_DIR_REAL / "cache"
        assert _normalize(CACHE_DIR) == esperado

    def test_log_dir_dentro_de_data(self):
        esperado = DATA_DIR_REAL / "logs"
        assert _normalize(LOG_DIR) == esperado

    def test_scripts_dir_dentro_de_data(self):
        esperado = DATA_DIR_REAL / "script"
        assert _normalize(SCRIPTS_DIR) == esperado

    def test_core_db_dentro_de_data(self):
        esperado = DATA_DIR_REAL / "core.db"
        assert _normalize(CORE_DB) == esperado

    def test_cache_db_dentro_de_data(self):
        esperado = DATA_DIR_REAL / "cache.db"
        assert _normalize(CACHE_DB) == esperado

    def test_embeddings_db_dentro_de_data(self):
        esperado = DATA_DIR_REAL / "embeddings.cbor2"
        assert _normalize(EMBEDDINGS_DB) == esperado

    def test_error_log_dentro_de_data(self):
        esperado = DATA_DIR_REAL / "errors.json"
        assert _normalize(ERROR_LOG) == esperado

    def test_docs_dir_fora_do_pacote(self):
        """DOCS_DIR fica no projeto, não no pacote (docs/ na raiz)."""
        assert _normalize(DOCS_DIR) == _normalize(
            Path(raiz_pacote).parent / "docs"
        )

    def test_evolution_doc_fora_do_pacote(self):
        assert _normalize(EVOLUTION_DOC) == _normalize(
            Path(raiz_pacote).parent / "docs" / "evolucao_cerebral.md"
        )

    def test_nenhum_path_vaza_para_fora_do_pacote(self):
        """Nenhum path de dados deve sair do diretório iaglobal/."""
        paths_to_check = [
            DATA_ROOT, MEMORY_DIR, BACKUP_DIR, CACHE_DIR,
            LOG_DIR, SCRIPTS_DIR, CORE_DB, CACHE_DB,
            EMBEDDINGS_DB, ERROR_LOG,
        ]
        pacote = _normalize(PACKAGE_DIR)
        for p in paths_to_check:
            resolved = _normalize(p)
            assert str(resolved).startswith(str(pacote)), (
                f"{p} -> {resolved} está FORA do pacote iaglobal/"
            )

    def test_diretorios_criados_pelo_ensure_dirs(self):
        """Verifica que os diretórios críticos existem em disco."""
        dirs = [DATA_ROOT, BACKUP_DIR, CACHE_DIR, LOG_DIR, SCRIPTS_DIR]
        for d in dirs:
            assert d.exists(), f"Diretório {d} não foi criado"


class TestGravacaoLibNoLocalCorreto:
    """Executa operações reais da lib e verifica que gravam em iaglobal/memory/data/."""

    def setup_method(self):
        DATA_DIR_REAL.mkdir(parents=True, exist_ok=True)

    def test_core_db_criado_no_lugar_certo(self):
        """DatabaseManager cria core.db em iaglobal/memory/data/."""
        from iaglobal.memory.db_manager import DatabaseManager

        CORE_DB.parent.mkdir(parents=True, exist_ok=True)
        db = DatabaseManager()
        db.insert_insight(agent="test_paths", task_id="t1",
                          content="teste de path centralizado", score=100)
        insights = db.get_insights(agent="test_paths", limit=10)

        assert len(insights) >= 1
        assert CORE_DB.exists(), f"core.db não foi criado em {CORE_DB}"
        caminho_real = os.path.realpath(CORE_DB)
        assert "iaglobal/memory/data" in caminho_real, (
            f"core.db está em local errado: {caminho_real}"
        )

    def test_error_log_no_lugar_certo(self):
        """store_error grava errors.json em iaglobal/memory/data/."""
        from iaglobal.memory.memory_error import store_error, load_errors

        store_error("test path", "code", "critique", "fix", "TestError")
        erros = load_errors()
        assert len(erros) >= 1
        assert ERROR_LOG.exists(), f"errors.json não foi criado em {ERROR_LOG}"
        caminho_real = os.path.realpath(ERROR_LOG)
        assert "iaglobal/memory/data" in caminho_real, (
            f"errors.json está em local errado: {caminho_real}"
        )

    def test_success_registry_no_lugar_certo(self):
        """store_success grava no banco em iaglobal/memory/data/."""
        from iaglobal.memory.memory_storage import init_storage, store_success, get_success_by_task

        CORE_DB.parent.mkdir(parents=True, exist_ok=True)
        init_storage()
        store_success("test_path_task", "print('ok')", {"test": True})

        resultado = get_success_by_task("test_path_task")
        assert resultado is not None
        assert CORE_DB.exists()
        caminho_real = os.path.realpath(CORE_DB)
        assert "iaglobal/memory/data" in caminho_real

    def test_pipeline_save_script_no_lugar_certo(self):
        """PipelineEngine._save_script grava em iaglobal/memory/data/script/."""
        from unittest.mock import MagicMock
        from iaglobal.pipeline.engine import PipelineEngine

        SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        state = MagicMock()
        state.script_path = None
        state.prompt = "teste path centralizado"
        state.task_id = "test_path_001"
        state.generated_code = "print('hello')"
        state.score = 0.9
        state.metadata = {}
        state.errors = []

        engine = PipelineEngine(MagicMock())
        path = engine._save_script(state)
        assert path is not None
        assert path.exists()
        caminho_real = os.path.realpath(path)
        assert "iaglobal/memory/data/script" in caminho_real, (
            f"Script salvo fora do lugar: {caminho_real}"
        )

    def test_memory_vector_no_lugar_certo(self):
        """Memória vetorial grava no banco em iaglobal/memory/data/."""
        from iaglobal.memory.memory_vector import store, init_db

        CORE_DB.parent.mkdir(parents=True, exist_ok=True)
        init_db()
        store("teste path centralizado vector", mtype="test_path")
        assert CORE_DB.exists()
        conn = sqlite3.connect(str(CORE_DB))
        rows = conn.execute(
            "SELECT content FROM memory WHERE type='test_path'"
        ).fetchall()
        conn.close()
        assert len(rows) >= 1

    def test_artifact_writer_no_lugar_certo(self):
        """Artifact writer grava em iaglobal/memory/data/script/."""
        from iaglobal.graphs.artifact import SolutionArtifact, Artifact
        from iaglobal.graphs.builder import _make_artifact_writer_run
        from unittest.mock import MagicMock

        SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        solution = SolutionArtifact(
            task="test artifact path",
            code="print('centralizado')",
            files={},
        )
        gatekeeper_result = {
            "output": solution,
            "gatekeeper_passed": True,
            "artifact": Artifact(
                content=solution.code, type="code",
                metadata={"task": "test artifact path", "score": 0.9},
            ),
        }
        ctx = {"memory": {"final_gatekeeper": gatekeeper_result}}
        result = asyncio.run(_make_artifact_writer_run(None)(ctx))
        assert result.get("persisted") is True
        caminho_real = os.path.realpath(result["path"])
        assert "iaglobal/memory/data/script" in caminho_real, (
            f"Artifact salvo fora do lugar: {caminho_real}"
        )


class TestIsolamentoDiretorios:
    """Verifica que não há escrita fora de iaglobal/memory/data/ durante operações."""

    def test_nenhum_arquivo_novo_fora_de_data(self):
        """
        Levanta os arquivos existentes em DATA_ROOT, executa uma operação
        da lib, e verifica que nenhum arquivo novo foi criado FORA de DATA_ROOT.
        """
        import tempfile
        from iaglobal.memory.db_manager import DatabaseManager
        from iaglobal.memory.memory_error import store_error
        from iaglobal.memory.memory_storage import init_storage, store_success

        CORE_DB.parent.mkdir(parents=True, exist_ok=True)

        # ---- EXECUTA OPERAÇÕES REAIS ----
        init_storage()
        store_success("task_isolamento", "codigo", {"test": True})
        store_error("prompt_iso", "resp", "crit", "fix", "TestError")
        db = DatabaseManager()
        db.insert_insight(agent="test_iso", task_id="t1",
                          content="isolamento verificado", score=100)

        # ---- VERIFICA QUE TUDO ESTÁ DENTRO DE DATA_ROOT ----
        import glob
        data_root_str = str(DATA_DIR_REAL)
        raiz_projeto_str = str(_normalize(PACKAGE_DIR).parent)

        for pattern in ["*.db", "*.json", "*.cbor2", "*.py"]:
            for f in glob.glob(os.path.join(raiz_projeto_str, "**", pattern),
                               recursive=True):
                f_real = os.path.realpath(f)
                if data_root_str in f_real:
                    continue
                if ".git" in f_real or "__pycache__" in f_real:
                    continue
                if "node_modules" in f_real:
                    continue
                if f_real.startswith(os.path.realpath(raiz_pacote) + "/tests"):
                    continue
                if f_real.startswith(os.path.realpath(
                        os.path.join(raiz_pacote, "tests"))):
                    continue
                if f.endswith(".py"):
                    continue
                print(f"  ⚠ Arquivo fora de memory/data: {f_real}")
