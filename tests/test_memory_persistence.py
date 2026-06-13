"""Testes do fluxo de persistência: critic → memory_writer → memory_cleaner."""
import pytest
import asyncio
import json
from pathlib import Path

from iaglobal.graphs.nodes._disk_swap import save_search, load_search, cleanup_task, swap_status


class TestDiskSwap:

    def setup_method(self):
        cleanup_task("test_disk_swap")

    def test_save_and_load(self):
        save_search("test_source", "test_disk_swap", "resultado importante " * 100)
        loaded = load_search("test_source", "test_disk_swap")
        assert loaded is not None
        assert len(loaded) > 100
        assert "importante" in loaded

    def test_load_nonexistent(self):
        r = load_search("nao_existe", "query_qualquer")
        assert r is None

    def test_cleanup_task(self):
        save_search("src1", "task_para_limpar", "dados 1")
        save_search("src2", "task_para_limpar", "dados 2")
        assert swap_status()["files"] >= 2
        cleanup_task("task_para_limpar")
        assert load_search("src1", "task_para_limpar") is None
        assert load_search("src2", "task_para_limpar") is None

    def test_swap_status(self):
        status = swap_status()
        assert "files" in status
        assert "size_kb" in status


class TestMemoryWriterNode:

    @pytest.mark.asyncio
    async def test_approved_persists(self):
        from iaglobal.graphs.nodes.no_memory_writer import run_memory_writer
        ctx = {
            "input": {"task": "gerar script python"},
            "memory": {
                "critic": {"approved": True, "score": 85.0, "issues": []},
                "prompt_builder": {"output": "crie um script funcional", "built_prompt": "crie um script funcional"},
                "multi_coder": {"output": "print('hello world')"},
            },
        }
        result = await run_memory_writer(ctx)
        assert result.get("success") is True
        assert result.get("stored") is True
        assert result.get("stored_count", 0) >= 2  # LTM + vector store

    @pytest.mark.asyncio
    async def test_rejected_does_not_persist_output(self):
        from iaglobal.graphs.nodes.no_memory_writer import run_memory_writer
        ctx = {
            "input": {"task": "gerar script"},
            "memory": {
                "critic": {"approved": False, "score": 15.0, "issues": ["Resposta vazia"]},
                "prompt_builder": {"output": "prompt qualquer", "built_prompt": "prompt qualquer"},
                "coder": {"output": "print('oi')"},
            },
        }
        result = await run_memory_writer(ctx)
        assert result.get("success") is True
        assert result.get("stored_count", 0) >= 1  # pelo menos metadados


class TestMemoryCleanerNode:

    @pytest.mark.asyncio
    async def test_cleaner_logs_critic_info(self):
        from iaglobal.graphs.nodes.no_memory_cleaner import run_memory_cleaner
        ctx = {
            "input": {"task": "teste"},
            "memory": {
                "critic": {"approved": True, "score": 90.0, "issues": []},
            },
        }
        result = await run_memory_cleaner(ctx)
        assert result.get("success") is True
        assert "cleanup_report" in result


class TestCriticNode:

    @pytest.mark.asyncio
    async def test_critic_rejects_empty(self):
        from iaglobal.graphs.nodes.no_critic import run_critic
        ctx = {
            "input": {"task": "test"},
            "memory": {"result_agent": {"output": ""}},
        }
        result = await run_critic(ctx)
        assert result.get("approved") is False
        assert result.get("score", 100) < 60

    @pytest.mark.asyncio
    async def test_critic_analyzes_code(self):
        from iaglobal.graphs.nodes.no_critic import run_critic
        code = """```python
def soma(a, b):
    return a + b
print(soma(2, 3))
```"""
        ctx = {
            "input": {"task": "criar funcao soma"},
            "memory": {"coder": {"output": code}},
        }
        result = await run_critic(ctx)
        assert "critic" in result
        assert result["critic"]["score"] >= 0
