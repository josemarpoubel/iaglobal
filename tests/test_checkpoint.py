"""Testes para checkpoint seguro - sem pickling de corrotinas."""

import asyncio
import pytest
from iaglobal.storage.snapshotter import make_checkpoint_safe, snapshotter, Snapshotter
from iaglobal.graphs.state_store import SystemStateBuffer
from pathlib import Path
import tempfile


async def dummy_coro():
    await asyncio.sleep(0.01)
    return "done"


async def dummy_async_gen():
    yield 1
    yield 2


def test_make_checkpoint_safe_coroutine():
    """Testa que corrotinas são convertidas para dict seguro."""
    coro = dummy_coro()
    result = make_checkpoint_safe(coro)
    
    assert isinstance(result, dict)
    assert result["__type__"] == "coroutine"
    assert "repr" in result
    coro.close()


def test_make_checkpoint_safe_async_function():
    """Testa que funções assíncronas são convertidas."""
    result = make_checkpoint_safe(dummy_coro)
    
    assert isinstance(result, dict)
    assert result["__type__"] == "coroutine_function"
    assert result["name"] == "dummy_coro"


def test_make_checkpoint_safe_task():
    """Testa que Tasks são convertidas."""
    async def test_task():
        task = asyncio.create_task(dummy_coro())
        result = make_checkpoint_safe(task)
        assert isinstance(result, dict)
        assert result["__type__"] == "task"
        assert "id" in result
        assert "name" in result
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    asyncio.run(test_task())


def test_make_checkpoint_safe_async_generator():
    """Testa que async generators são convertidos."""
    gen = dummy_async_gen()
    result = dummy_async_gen()
    result = make_checkpoint_safe(gen)
    
    assert isinstance(result, dict)
    assert result["__type__"] == "async_generator"
    gen.aclose()


def test_make_checkpoint_safe_nested_dict():
    """Testa recursão em dicts aninhados."""
    coro = dummy_coro()
    data = {
        "level1": {
            "level2": {
                "coro": coro,
                "normal": "value"
            }
        },
        "list_with_coro": [coro, "item"]
    }
    result = make_checkpoint_safe(data)
    
    assert result["level1"]["level2"]["coro"]["__type__"] == "coroutine"
    assert result["level1"]["level2"]["normal"] == "value"
    assert result["list_with_coro"][0]["__type__"] == "coroutine"
    assert result["list_with_coro"][1] == "item"
    coro.close()


def test_make_checkpoint_safe_preserves_primitives():
    """Testa que tipos primitivos são preservados."""
    assert make_checkpoint_safe("string") == "string"
    assert make_checkpoint_safe(123) == 123
    assert make_checkpoint_safe(3.14) == 3.14
    assert make_checkpoint_safe(True) is True
    assert make_checkpoint_safe(None) is None


def test_snapshot_with_coroutine_in_state():
    """Testa criação de snapshot com corrotina no estado."""
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshots_dir = Path(tmpdir) / "snapshots"
        db_path = Path(tmpdir) / "test.db"
        
        snap = Snapshotter(db_path=db_path, snapshots_dir=snapshots_dir)
        
        # Estado com corrotina
        state_data = {
            "nodes": {
                "node1": {
                    "status": "RUNNING",
                    "output": dummy_coro(),
                    "attempt": 0
                }
            },
            "compressed": {}
        }
        
        snapshot_id = snap.create_snapshot(state_data)
        assert snapshot_id is not None
        
        # Verifica que pode carregar
        loaded = snap.load_snapshot(snapshot_id)
        assert loaded is not None
        assert loaded["state_data"]["nodes"]["node1"]["output"]["__type__"] == "coroutine"


def test_snapshot_with_task_in_state():
    """Testa criação de snapshot com Task no estado."""
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshots_dir = Path(tmpdir) / "snapshots"
        db_path = Path(tmpdir) / "test.db"
        
        snap = Snapshotter(db_path=db_path, snapshots_dir=snapshots_dir)
        
        async def test():
            task = asyncio.create_task(dummy_coro())
            state_data = {
                "nodes": {
                    "node1": {
                        "status": "RUNNING",
                        "output": task,
                        "attempt": 0
                    }
                },
                "compressed": {}
            }
            
            snapshot_id = snap.create_snapshot(state_data)
            assert snapshot_id is not None
            
            loaded = snap.load_snapshot(snapshot_id)
            assert loaded is not None
            assert loaded["state_data"]["nodes"]["node1"]["output"]["__type__"] == "task"
            
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        asyncio.run(test())


def test_systemstatebuffer_snapshot_roundtrip():
    """Testa roundtrip completo do SystemStateBuffer via snapshotter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshots_dir = Path(tmpdir) / "snapshots"
        db_path = Path(tmpdir) / "test.db"
        
        snap = Snapshotter(db_path=db_path, snapshots_dir=snapshots_dir)
        buffer = SystemStateBuffer(max_size=10, snapshot_interval_ops=5)
        
        # Adiciona dados incluindo corrotina
        coro = dummy_coro()
        buffer.set("task:123", "RUNNING", output=coro, attempt=1)
        buffer.set("task:456", "SUCCESS", output="completed", attempt=0)
        
        snap_data = buffer.get_snapshot_data()
        snapshot_id = snap.create_snapshot(snap_data)
        assert snapshot_id is not None
        
        # Restaura
        loaded = snap.load_snapshot(snapshot_id)
        assert loaded is not None
        
        new_buffer = SystemStateBuffer()
        new_buffer.load_snapshot(loaded["state_data"])
        
        # Verifica que dados foram restaurados (corrotina virou dict)
        restored = new_buffer.get("task:123")
        assert restored["output"]["__type__"] == "coroutine"
        
        restored2 = new_buffer.get("task:456")
        assert restored2["output"] == "completed"
        
        coro.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])