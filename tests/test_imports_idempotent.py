"""Testa que imports dos módulos principais NÃO alteram dados persistentes."""
import json
import pytest
from pathlib import Path
from iaglobal._paths import (
    KNOWLEDGE_FILE,
    META_EVOLUTION_FILE,
    EVOLUTION_BACKLOG_FILE,
    SAME_POOL_FILE,
    HOMOCYSTEINE_POOL_FILE,
    ERROR_LOG,
)


def _read_or_none(path: Path):
    if path.exists():
        return path.read_text()
    return None


SNAPSHOT_FILES = [
    KNOWLEDGE_FILE,
    META_EVOLUTION_FILE,
    EVOLUTION_BACKLOG_FILE,
    SAME_POOL_FILE,
    HOMOCYSTEINE_POOL_FILE,
]

# ERROR_LOG excluded because 'updated_at' timestamp changes on every build.
# errors.json is a runtime telemetry file, not a static config.


@pytest.fixture
def snapshot():
    data = {str(p): _read_or_none(p) for p in SNAPSHOT_FILES}
    yield
    for p in SNAPSHOT_FILES:
        saved = data.get(str(p))
        if saved is not None:
            p.write_text(saved)


def _verify_intact(snapshot_data):
    for p in SNAPSHOT_FILES:
        saved = snapshot_data.get(str(p))
        current = _read_or_none(p)
        if saved != current:
            print(f"DIFERENCA em {p.name}")
            print(f"  antes: {saved[:200] if saved else 'NONE'}")
            print(f"  depois: {current[:200] if current else 'NONE'}")


class TestImportsIdempotent:

    def test_builder_import_does_not_alter_files(self, snapshot):
        # Captura o estado atual dos arquivos de persistência antes do import
        snap = {str(p): _read_or_none(p) for p in SNAPSHOT_FILES}
        
        # Realiza o import do módulo sob teste
        from iaglobal.graphs.builder import build_pipeline_from_nodes
        
        # Verifica se houve alteração imediata durante o processo de importação
        _verify_intact(snap)
        
        # Validação final para garantir idempotência dos arquivos
        for p in SNAPSHOT_FILES:
            saved = snap.get(str(p))
            current = _read_or_none(p)
            # A mensagem abaixo agora possui a sintaxe f-string correta
            assert saved == current, f"O arquivo {p.name} foi alterado após o import do builder!"

    def test_evolution_modules_import_does_not_alter_files(self, snapshot):
        snap = {str(p): _read_or_none(p) for p in SNAPSHOT_FILES}
        import iaglobal.evolution.meta_evolver
        import iaglobal.evolution.agents.knowledge_agent
        import iaglobal.evolution.same_engine
        import iaglobal.evolution.metabolism.homocysteine_pool
        _verify_intact(snap)
        for p in SNAPSHOT_FILES:
            saved = snap.get(str(p))
            current = _read_or_none(p)
            assert saved == current, f"{p.name} foi alterado pelo import dos módulos de evolução"

    def test_all_node_handlers_import_does_not_alter_files(self, snapshot):
        snap = {str(p): _read_or_none(p) for p in SNAPSHOT_FILES}
        from iaglobal.graphs.builder import RUN_NODE_NAMES
        for name in RUN_NODE_NAMES:
            importlib = __import__("importlib")
            try:
                importlib.import_module(f"iaglobal.graphs.nodes.no_{name}")
            except Exception:
                pass
        _verify_intact(snap)
        for p in SNAPSHOT_FILES:
            saved = snap.get(str(p))
            current = _read_or_none(p)
            assert saved == current, f"{p.name} foi alterado pelo import de todos os handlers"

    def test_pipeline_build_does_not_alter_files(self, snapshot):
        snap = {str(p): _read_or_none(p) for p in SNAPSHOT_FILES}
        from iaglobal.graphs.builder import build_pipeline_from_nodes
        g = build_pipeline_from_nodes()
        assert len(g.nodes) > 50
        _verify_intact(snap)
        for p in SNAPSHOT_FILES:
            saved = snap.get(str(p))
            current = _read_or_none(p)
            assert saved == current, f"{p.name} foi alterado pelo build do pipeline"
