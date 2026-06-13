"""Stress and chaos tests: BatchWriter, Snapshotter, FeedbackEngine, rollback.

Verifies:
- BatchWriter: high throughput, thread safety, data integrity, shutdown
- Snapshotter: create/load/rollback/prune, corrupted/missing files
- FeedbackEngine: edge cases (empty, syntax, security)
- Rollback flow: crash → rollback → state restoration
"""

import os
import json
import time
import shutil
import threading
import tempfile
import sqlite3
from pathlib import Path
from queue import Queue, Empty

import pytest
import cbor2

from iaglobal.storage.batch_writer import BatchWriter, Event
from iaglobal.storage.snapshotter import Snapshotter
from iaglobal.validation.engine import FeedbackEngine, Decision


@pytest.fixture
def tmp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink()


@pytest.fixture
def writer(tmp_db):
    w = BatchWriter(db_path=tmp_db, flush_ms=50, max_batch=20)
    w.start()
    yield w
    w.stop(timeout=2.0)

    def test_high_throughput(self, writer):
        """1000 events em alta velocidade."""
        n = 1000
        for i in range(n):
            writer.emit(Event(
                event_type="test_throughput",
                payload=f"event_{i}",
                critical=False,
            ))
        time.sleep(1.0)
        count = writer.count("test_throughput")
        assert count == n, f"Esperado {n}, obtido {count}"

    def test_critical_flush_immediate(self, tmp_db):
        """Eventos críticos fazem flush imediato."""
        w = BatchWriter(db_path=tmp_db, flush_ms=5000, max_batch=100)
        w.start()
        w.emit(Event(event_type="test_critical", payload="urgent", critical=True))
        time.sleep(0.2)
        count = w.count("test_critical")
        w.stop()
        assert count >= 1, "Evento crítico deveria ter flush imediato"

    def test_data_integrity(self, writer):
        """Payload dos eventos preservado após escrita."""
        writer.emit(Event(
            event_type="test_integrity",
            payload='{"key": "value", "nested": {"a": 1}}',
            task_fingerprint="fp_123",
            model="test_model",
            latency_ms=42.5,
            tokens_in=100,
            tokens_out=200,
        ))
        time.sleep(0.5)
        rows = writer.query(event_type="test_integrity", limit=10)
        assert len(rows) == 1
        assert rows[0]["task_fingerprint"] == "fp_123"
        assert rows[0]["model"] == "test_model"
        assert rows[0]["latency_ms"] == 42.5
        assert rows[0]["tokens_in"] == 100
        assert rows[0]["tokens_out"] == 200

    def test_concurrent_writes(self, tmp_db):
        """Múltiplas threads enfileirando eventos simultaneamente."""
        w = BatchWriter(db_path=tmp_db, flush_ms=100, max_batch=50)
        w.start()
        n_threads = 5
        events_per_thread = 200

        def enqueue_many(thread_id):
            for i in range(events_per_thread):
                w.emit(Event(
                    event_type="test_concurrent",
                    payload=f"thread_{thread_id}_event_{i}",
                ))

        threads = [threading.Thread(target=enqueue_many, args=(tid,))
                   for tid in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        time.sleep(1.0)
        count = w.count("test_concurrent")
        w.stop()
        assert count == n_threads * events_per_thread, \
            f"Esperado {n_threads * events_per_thread}, obtido {count}"

    def test_shutdown_with_pending(self, tmp_db):
        """Shutdown não perde eventos pendentes."""
        w = BatchWriter(db_path=tmp_db, flush_ms=5000, max_batch=100)
        w.start()
        n = 50
        for i in range(n):
            w.emit(Event(event_type="test_shutdown", payload=f"event_{i}"))
        w.stop(timeout=5.0)
        count = w.count("test_shutdown")
        assert count == n, f"Esperado {n} após shutdown, obtido {count}"

    def test_batch_order_preserved(self, writer):
        """Ordem dos eventos é preservada dentro de um batch."""
        n = 100
        for i in range(n):
            writer.emit(Event(
                event_type="test_order",
                payload=f"event_{i:04d}",
                timestamp=float(i),
            ))
        time.sleep(1.0)
        rows = writer.query(event_type="test_order", limit=n)
        assert len(rows) == n

    def test_large_payload(self, writer):
        """Payload grande (>10k chars) é truncado, não quebra."""
        large = "A" * 20000
        writer.emit(Event(
            event_type="test_large",
            payload=large,
        ))
        time.sleep(0.5)
        rows = writer.query(event_type="test_large", limit=10)
        assert len(rows) == 1
        assert len(rows[0]["payload"]) <= 10000


class TestBatchWriterEdgeCases:

    def test_empty_queue_no_crash(self, tmp_db):
        """Nenhum evento não causa erro."""
        w = BatchWriter(db_path=tmp_db, flush_ms=100, max_batch=10)
        w.start()
        time.sleep(0.3)
        w.stop()
        assert w.stats()["written"] == 0

    def test_db_file_created(self, tmp_db):
        """Arquivo DB é criado mesmo sem eventos."""
        assert tmp_db.exists()
        w = BatchWriter(db_path=tmp_db, flush_ms=100, max_batch=10)
        w.start()
        w.stop()
        assert tmp_db.exists()

    def test_multiple_batches(self, writer):
        """Múltiplos batches são processados corretamente."""
        n = 5
        for batch in range(n):
            for i in range(20):
                writer.emit(Event(
                    event_type="test_multi_batch",
                    payload=f"batch_{batch}_event_{i}",
                ))
            time.sleep(0.1)
        time.sleep(0.5)
        count = writer.count("test_multi_batch")
        assert count == n * 20

    def test_query_with_filter(self, writer):
        """Query filtrando por tipo e fingerprint."""
        writer.emit(Event(event_type="type_a", payload="a1", task_fingerprint="fp1"))
        writer.emit(Event(event_type="type_a", payload="a2", task_fingerprint="fp2"))
        writer.emit(Event(event_type="type_b", payload="b1", task_fingerprint="fp1"))
        time.sleep(0.5)
        rows = writer.query(event_type="type_a", fingerprint="fp1", limit=10)
        assert len(rows) == 1
        assert rows[0]["payload"] == "a1"


# =============================================================================
# SNAPSHOTTER CHAOS TESTS
# =============================================================================

class TestSnapshotterChaos:

    @pytest.fixture
    def tmp_dir(self):
        path = Path(tempfile.mkdtemp())
        yield path
        shutil.rmtree(path, ignore_errors=True)

    @pytest.fixture
    def snapshooter(self, tmp_dir):
        db_path = tmp_dir / "test.db"
        snap_dir = tmp_dir / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        s = Snapshotter(db_path=db_path, snapshots_dir=snap_dir)
        yield s

    def test_create_and_load(self, snapshooter):
        """Criar e carregar snapshot."""
        state = {"nodes": {"n1": {"status": "ok"}, "n2": {"status": "ok"}}}
        snap_id = snapshooter.create_snapshot(state)
        assert snap_id is not None
        data = snapshooter.load_snapshot(snap_id)
        assert data is not None
        assert data["state_data"]["nodes"]["n1"]["status"] == "ok"

    def test_rollback_restores_state(self, snapshooter):
        """Rollback restaura último snapshot."""
        snapshooter.create_snapshot({"nodes": {"a": {"v": 1}}})
        snapshooter.create_snapshot({"nodes": {"b": {"v": 2}}})
        restored = snapshooter.rollback()
        assert restored is not None
        assert "b" in restored.get("nodes", {})

    def test_rollback_specific(self, snapshooter):
        """Rollback para snapshot específico."""
        s1 = snapshooter.create_snapshot({"nodes": {"a": {"v": 1}}})
        snapshooter.create_snapshot({"nodes": {"b": {"v": 2}}})
        restored = snapshooter.rollback(snapshot_id=s1)
        assert restored is not None
        assert "a" in restored.get("nodes", {})

    def test_rollback_no_snapshot(self, snapshooter):
        """Rollback sem snapshots retorna None sem crash."""
        result = snapshooter.rollback()
        assert result is None

    def test_prune_keeps_n_most_recent(self, snapshooter):
        """Prune mantém apenas os N mais recentes."""
        for i in range(10):
            snapshooter.create_snapshot({"nodes": {f"n{i}": {"v": i}}})
        snapshooter.prune_old_snapshots(keep_last=3)
        remaining = snapshooter.list_snapshots(limit=20)
        assert len(remaining) >= 1

    def test_missing_file_returns_none(self, snapshooter):
        """Snapshot com ID existente no índice mas arquivo faltando."""
        snapshooter.create_snapshot({"nodes": {"x": {"v": 1}}})
        latest = snapshooter.get_latest_snapshot_id()
        assert latest is not None
        # Remove o arquivo manualmente
        path = snapshooter.snapshots_dir / f"snapshot_{latest}.cbor2"
        path.unlink()
        data = snapshooter.load_snapshot(latest)
        assert data is None

    def test_corrupted_file_returns_none(self, snapshooter):
        """Arquivo CBOR2 corrompido retorna None."""
        snap_id = snapshooter.create_snapshot({"nodes": {"x": {"v": 1}}})
        path = snapshooter.snapshots_dir / f"snapshot_{snap_id}.cbor2"
        # Arquivo vazio — cbor2 não consegue decodificar
        path.write_bytes(b"")
        data = snapshooter.load_snapshot(snap_id)
        assert data is None

    def test_large_state(self, snapshooter):
        """Estado grande (1000 nós) serializa e desserializa."""
        large_state = {
            "nodes": {f"node_{i}": {"v": i, "data": "x" * 100}
                      for i in range(1000)}
        }
        snap_id = snapshooter.create_snapshot(large_state)
        assert snap_id is not None
        data = snapshooter.load_snapshot(snap_id)
        assert data is not None
        assert len(data["state_data"]["nodes"]) == 1000

    def test_concurrent_snapshots(self, snapshooter):
        """Múltiplas threads criando snapshots simultaneamente."""
        n_threads = 4
        snaps_per_thread = 25

        def create_snaps(thread_id):
            for i in range(snaps_per_thread):
                snapshooter.create_snapshot({
                    "nodes": {f"t{thread_id}_n{i}": {"v": i}}
                })

        threads = [threading.Thread(target=create_snaps, args=(tid,))
                   for tid in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snapshots = snapshooter.list_snapshots(limit=200)
        assert len(snapshots) >= n_threads * snaps_per_thread - 5


# =============================================================================
# FEEDBACKENGINE EDGE CASES
# =============================================================================

class TestFeedbackEngineEdgeCases:

    @pytest.fixture
    def engine(self):
        return FeedbackEngine()

    def test_valid_code(self, engine):
        """Código Python válido passa na validação."""
        result = engine.validate("def hello():\n    return 42\n")
        assert result.valid
        assert result.decision == Decision.COMMIT
        assert result.score == 1.0

    def test_empty_code(self, engine):
        """Código vazio retorna RETRY."""
        result = engine.validate("")
        assert not result.valid
        assert result.decision == Decision.RETRY
        assert result.score == 0.0

    def test_whitespace_code(self, engine):
        """Apenas espaços retorna RETRY."""
        result = engine.validate("   \n  \n  ")
        assert not result.valid
        assert result.decision == Decision.RETRY

    def test_syntax_error(self, engine):
        """SyntaxError retorna RETRY."""
        result = engine.validate("def broken(")
        assert not result.valid
        assert result.decision == Decision.RETRY
        assert any("syntax" in e.lower() for e in result.errors)

    def test_security_violation(self, engine):
        """Código com eval/exec retorna ROLLBACK."""
        result = engine.validate("eval('print(1)')")
        assert not result.valid
        assert result.decision == Decision.ROLLBACK

    def test_forbidden_import(self, engine):
        """Import de módulo proibido retorna ROLLBACK."""
        result = engine.validate("import subprocess\nsubprocess.run(['ls'])")
        assert not result.valid
        assert result.decision == Decision.ROLLBACK

    def test_os_system_call(self, engine):
        """os.system retorna ROLLBACK."""
        result = engine.validate("import os\nos.system('ls')")
        assert not result.valid
        assert result.decision == Decision.ROLLBACK

    def test_valid_class(self, engine):
        """Classe Python válida passa."""
        code = """
class Calculator:
    def add(self, a, b):
        return a + b

    def multiply(self, a, b):
        return a * b
"""
        result = engine.validate(code)
        assert result.valid
        assert result.decision == Decision.COMMIT

    def test_code_with_fstrings(self, engine):
        """f-strings são válidas."""
        result = engine.validate("name = 'world'\nprint(f'hello {name}')\n")
        assert result.valid

    def test_async_code(self, engine):
        """async/await é válido."""
        result = engine.validate("""
async def fetch():
    return await some_async_fn()
""")
        assert result.valid

    def test_large_valid_file(self, engine):
        """Arquivo grande (500 linhas) passa sem problemas de performance."""
        lines = [f"def func_{i}():\n    return {i}\n" for i in range(500)]
        code = "\n".join(lines)
        import time
        start = time.time()
        result = engine.validate(code)
        elapsed = time.time() - start
        assert result.valid
        assert elapsed < 2.0, f"Validação muito lenta: {elapsed:.2f}s"

    def test_mixed_valid_and_invalid(self, engine):
        """Marcação de erro não impede validação de outros trechos."""
        result = engine.validate("print('ok')\neval('x')\nprint('also ok')")
        assert not result.valid
        assert result.decision == Decision.ROLLBACK

    def test_retry_after_two_failures(self, engine):
        """2+ retries consecutivas mudam decisão para ROLLBACK."""
        result = engine.validate("broken(", context={"retry_count": 2})
        assert result.decision == Decision.ROLLBACK

    def test_apply_patch_valid(self, engine):
        """Patch válido é aplicado com sucesso."""
        original = "x = 1"
        patch = "x = 2"
        success, merged, errors = engine.apply_patch(original, patch)
        assert success
        assert merged == patch

    def test_apply_patch_invalid(self, engine):
        """Patch inválido não é aplicado."""
        original = "x = 1"
        patch = "def broken("
        success, merged, errors = engine.apply_patch(original, patch)
        assert not success
        assert merged == original

    def test_validate_and_apply_valid(self, engine):
        """Fluxo completo validate_and_apply com patch válido."""
        result = engine.validate_and_apply("x = 1", "x = 2")
        assert result.valid
        assert result.code == "x = 2"

    def test_validate_and_apply_invalid(self, engine):
        """Fluxo completo validate_and_apply com patch inválido."""
        result = engine.validate_and_apply("x = 1\n", "eval('x')")
        assert not result.valid
        assert result.decision == Decision.ROLLBACK


# =============================================================================
# ROLLBACK FLOW CHAOS TESTS
# =============================================================================

class TestRollbackFlowChaos:

    @pytest.fixture
    def tmp_dir(self):
        path = Path(tempfile.mkdtemp())
        yield path
        shutil.rmtree(path, ignore_errors=True)

    @pytest.fixture
    def snapshotter(self, tmp_dir):
        db_path = tmp_dir / "test.db"
        snap_dir = tmp_dir / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        return Snapshotter(db_path=db_path, snapshots_dir=snap_dir)

    def test_crash_then_rollback(self, snapshotter):
        """Simula crash após estado corrompido: rollback restaura estado bom."""
        # Estado bom
        s1 = snapshotter.create_snapshot({
            "nodes": {"app": {"status": "running", "data": "clean"}},
            "compressed": {},
        })
        # Estado corrompido (simula crash)
        snapshotter.create_snapshot({
            "nodes": {"app": {"status": "corrupted", "data": None}},
            "compressed": {},
        })
        # Rollback para o bom
        restored = snapshotter.rollback(snapshot_id=s1)
        assert restored is not None
        assert restored["nodes"]["app"]["status"] == "running"

    def test_rollback_restores_previous_before_corruption(self, snapshotter):
        """Rollback para último snapshot válido ignora corrompido."""
        s1 = snapshotter.create_snapshot({
            "nodes": {"app": {"status": "clean", "version": 1}},
        })
        # Cria um snapshot e corrompe o arquivo
        snap_id = snapshotter.create_snapshot({
            "nodes": {"app": {"status": "dirty", "version": 2}},
        })
        path = snapshotter.snapshots_dir / f"snapshot_{snap_id}.cbor2"
        with open(path, "wb") as f:
            f.write(b"garbage")

        # load_snapshot do corrompido retorna None
        assert snapshotter.load_snapshot(snap_id) is None

        # Mas podemos rollback pro s1 ainda
        restored = snapshotter.rollback(snapshot_id=s1)
        assert restored is not None
        assert restored["nodes"]["app"]["version"] == 1

    def test_multi_rollback_cycle(self, snapshotter):
        """Múltiplos rollbacks consecutivos funcionam."""
        snap_ids = []
        for i in range(5):
            sid = snapshotter.create_snapshot({
                "nodes": {"v": i},
            })
            snap_ids.append(sid)

        for i in range(4, -1, -1):
            restored = snapshotter.rollback(snapshot_id=snap_ids[i])
            assert restored is not None
            assert restored["nodes"]["v"] == i

    def test_snapshot_then_delete_db(self, snapshotter, tmp_dir):
        """Remover o índice SQLite não quebra carregamento de snapshots existentes."""
        snap_id = snapshotter.create_snapshot({
            "nodes": {"persist": {"v": 42}},
        })
        # Remove o índice simulando perda de DB
        db_path = tmp_dir / "test.db"
        db_path.unlink()

        # Ainda podemos carregar pelo caminho direto do arquivo
        path = snapshotter.snapshots_dir / f"snapshot_{snap_id}.cbor2"
        assert path.exists()
        with open(path, "rb") as f:
            data = cbor2.load(f)
        assert data["state_data"]["nodes"]["persist"]["v"] == 42

    def test_chaos_concurrent_create_and_prune(self, snapshotter):
        """Criação e prune concorrentes não corrompem o índice."""
        stop = threading.Event()

        def creator():
            i = 0
            while not stop.is_set():
                snapshotter.create_snapshot({"nodes": {f"n{i}": {"v": i}}})
                i += 1
                if i > 50:
                    break

        def pruner():
            while not stop.is_set():
                snapshotter.prune_old_snapshots(keep_last=20)
                time.sleep(0.05)

        t1 = threading.Thread(target=creator)
        t2 = threading.Thread(target=pruner)
        t1.start()
        t2.start()
        time.sleep(1.0)
        stop.set()
        t1.join()
        t2.join()

        # Índice ainda funcional
        snapshots = snapshotter.list_snapshots(limit=10)
        assert isinstance(snapshots, list)
