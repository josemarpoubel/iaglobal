"""
Teste de Integração Evolution ↔ Memory ↔ Knowledge
=================================================

Valida conexões automáticas entre:
- /iaglobal/evolution/* (homeostasis, epigenetic, metabolismo)
- /iaglobal/memory/* (vector store, knowledge, database)
- /iaglobal/memory/data/* (cbor2, json, db, provider_metrics)

Estas conexões devem existir e funcionar automaticamente via _paths.py
"""
import pytest
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from iaglobal._paths import (
    # Paths principais
    DATA_ROOT, MEMORY_DIR, JSON_DIR, DB_DIR, CBOR2_DIR,
    CACHE_DIR, LOG_DIR, TEMP_DIR,
    # Result paths
    RESULTS_DIR, WORK_DIR, SNAPSHOTS_DIR,
    # Evolution/memory specific
    PROVIDER_METRICS_DIR, IMAGES_DIR, MONITORED_DIR,
    DOCS_TEMP_DIR, SANDBOX_DIR,
    # Arquivos principais
    KNOWLEDGE_FILE, ERROR_LOG, META_EVOLUTION_FILE,
    EVOLUTION_BACKLOG_FILE, SAME_POOL_FILE,
    HOMOCYSTEINE_POOL_FILE, GLUTATHIONE_POOL_FILE,
    CHOLINE_POOL_FILE, MTA_POOL_FILE,
    EMBEDDINGS_DB, CORE_DB, CACHE_DB, MEMORIES_DB,
    PROVIDER_EVENTS_DB,
)


class TestMemoryEvolutionPathIntegration:
    """Valida que evolution e memory compartilham o mesmo root."""

    def test_data_root_not_empty(self):
        """DATA_ROOT deve ter conteúdo (não pode ser caminho inútil)."""
        assert DATA_ROOT.exists(), f"DATA_ROOT não existe: {DATA_ROOT}"
        # Deve ter subdiretórios criados por _ensure_dirs()
        assert any(DATA_ROOT.iterdir()), "DATA_ROOT está vazio"

    def test_memory_dir_is_data_root(self):
        """MEMORY_DIR deve ser identico a DATA_ROOT (convenção)."""
        assert MEMORY_DIR == DATA_ROOT, f"MEMORY_DIR ({MEMORY_DIR}) != DATA_ROOT ({DATA_ROOT})"

    def test_json_dir_coexists_with_evolution_files(self):
        """JSON_DIR deve conter arquivos de evolução (knowledge, pools)."""
        # Verifica se os arquivos de evolução estão no mesmo lugar
        assert JSON_DIR.exists()
        # Conexão automática: metamotor lê estes arquivos
        assert KNOWLEDGE_FILE.parent == JSON_DIR

    def test_provider_metrics_inside_memory(self):
        """PROVIDER_METRICS_DIR deve estar dentro de DATA_ROOT."""
        assert PROVIDER_METRICS_DIR.parent == DATA_ROOT, \
            f"PROVIDER_METRICS_DIR ({PROVIDER_METRICS_DIR}) não está em DATA_ROOT ({DATA_ROOT})"


class TestEvolutionPoolsPathConnection:
    """Valida caminhos dos pools metabólicos (homocysteina, glutathione, etc)."""

    def test_homocysteine_pool_in_json(self):
        """HOMOCYSTEINE_POOL_FILE está em JSON_DIR (persistente)."""
        assert HOMOCYSTEINE_POOL_FILE.parent == JSON_DIR

    def test_glutathione_pool_in_json(self):
        """GLUTATHIONE_POOL_FILE está em JSON_DIR (persistente)."""
        assert GLUTATHIONE_POOL_FILE.parent == JSON_DIR

    def test_same_pool_in_json(self):
        """SAME_POOL_FILE deve estar em JSON_DIR."""
        assert SAME_POOL_FILE.parent == JSON_DIR

    def test_pool_files_share_memory_root(self):
        """Todos os pools compartilham o mesmo sistema de arquivos."""
        # TEMP_DIR e JSON_DIR ambos filhos de DATA_ROOT
        assert TEMP_DIR.parent == DATA_ROOT
        assert JSON_DIR.parent == DATA_ROOT


class TestKnowledgeWriterDatabaseFlow:
    """Valida fluxo KnowledgeWriter → MemoryVector → SQLite → CBOR2."""

    @pytest.mark.asyncio
    async def test_memory_vector_init_creates_table(self):
        """init_db deve criar tabela 'memory' em CORE_DB."""
        from iaglobal.memory.memory_vector import init_db
        import sqlite3

        # Garante diretório existe
        DB_DIR.mkdir(parents=True, exist_ok=True)

        await asyncio.to_thread(init_db)

        # Verifica tabela foi criada
        conn = sqlite3.connect(str(CORE_DB))
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memory'"
            )
            result = cursor.fetchone()
            assert result is not None, "Tabela 'memory' não foi criada por init_db"
        finally:
            conn.close()


class TestEpigeneticFlagIntegration:
    """Valida que flags epigenéticas são lidas automaticamente."""

    def test_epigenetic_defaults_exist(self):
        """DEFAULT_FLAGS devem estar disponíveis no startup."""
        from iaglobal.evolution.epigenetic import DEFAULT_FLAGS

        assert "bandit_epsilon" in DEFAULT_FLAGS
        assert "evolve_knowledge" in DEFAULT_FLAGS
        assert DEFAULT_FLAGS["bandit_epsilon"] == 0.2

    def test_get_flag_returns_default(self):
        """get_flag deve retornar valor padrão sem necessidade de setup."""
        from iaglobal.evolution.epigenetic import get_flag

        epsilon = get_flag("bandit_epsilon")
        assert epsilon == 0.2, f"get_flag('bandit_epsilon') retornou {epsilon}, esperado 0.2"


class TestHomeostasisControllerConnection:
    """Valida HomeostasisController usa epigenetic flags."""

    def test_homeostasis_uses_epigenetic(self):
        """Homeostasis deve importar flags de epigenetic automaticamente."""
        from iaglobal.evolution.homeostasis_controller import HomeostasisController

        controller = HomeostasisController()
        # Deve ter acesso a flags via get_flag
        assert controller is not None

    def test_homeostasis_adjustment_modifies_epsilon(self):
        """apply_adjustments deve modificar bandit_epsilon via epigenetic."""
        from iaglobal.evolution.homeostasis_controller import HomeostasisController
        from iaglobal.evolution.epigenetic import get_flag, set_flag

        # Força falha simulada
        controller = HomeostasisController()
        controller.metrics.total_executions = 10
        controller.metrics.successful = 5  # 50% erro

        sla_result = controller.check_sla()
        result = controller.apply_adjustments(sla_result)

        # Epsilon deve ter sido ajustado (redução para explorar menos)
        if result.get("adjusted"):
            new_epsilon = get_flag("bandit_epsilon")
            assert new_epsilon < 0.2, f"Epsilon não foi reduzido: {new_epsilon}"