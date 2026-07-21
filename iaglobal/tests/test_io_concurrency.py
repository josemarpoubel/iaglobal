# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes de integridade de I/O concorrente e drain de shutdown.

Cenários:
  1. _salvar_estado() thread-safe — múltiplas threads escrevendo
     concorrentemente não corrompem o JSON final
  2. drain_background_tasks() — tasks pendentes são aguardadas
     antes do shutdown (memória imunológica não é perdida)
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════
# FIX-1: Thread-safe _salvar_estado()
# ═══════════════════════════════════════════════════════════════════


class TestThreadSafeStateSave:
    """_salvar_estado() deve ser atômico para evitar corrupção."""

    @pytest.mark.asyncio
    async def test_concurrent_writes_no_corruption(self):
        """Múltiplas threads escrevendo concorrentemente não devem
        corromper o JSON final — usa lock + temp file + os.replace()."""
        from iaglobal.obsidian.omnimind import OmniMind
        import threading

        # Reset do singleton para teste isolado
        OmniMind._instance = None
        OmniMind._initialized = False

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp_path = Path(f.name)
            json.dump([], f)

        try:
            omni = OmniMind(state_path=tmp_path)
            # Limpa memória inicial carregada do disco
            omni._memoria_coletiva = []

            # Função que simula múltiplos abortos concorrentes
            def _trigger_apoptose(thread_id: int):
                omni.emitir_gatilho_apoptose(
                    agent_id=f"agent_{thread_id}",
                    motivo=f"Thread {thread_id} violou contrato",
                    violation_type="concurrent_test",
                )

            # Executa 10 threads concorrentemente
            num_threads = 10
            threads = []
            for i in range(num_threads):
                t = threading.Thread(target=_trigger_apoptose, args=(i,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # Verifica integridade do JSON final
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()

            # JSON deve ser válido (não corrompido)
            data = json.loads(content)
            assert isinstance(data, list)
            assert len(data) == num_threads, (
                f"Esperava {num_threads} entradas, encontrou {len(data)}"
            )

            # Verifica que todos os agentes estão presentes
            agent_ids = {entry["agent_id"] for entry in data}
            for i in range(num_threads):
                assert f"agent_{i}" in agent_ids

        finally:
            # Limpa arquivo temporário
            if tmp_path.exists():
                tmp_path.unlink()
            # Restaura singleton
            OmniMind._instance = None
            OmniMind._initialized = False

    @pytest.mark.asyncio
    async def test_atomic_write_uses_temp_file(self):
        """_salvar_estado() deve usar tempfile + os.replace()."""
        from iaglobal.obsidian.omnimind import OmniMind

        # Reset do singleton
        OmniMind._instance = None
        OmniMind._initialized = False

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp_path = Path(f.name)
            json.dump([], f)

        try:
            omni = OmniMind(state_path=tmp_path)
            omni._memoria_coletiva = [{"test": "data"}]

            # Mock de os.replace para verificar que foi chamado
            with patch("os.replace") as mock_replace:
                omni._salvar_estado()
                mock_replace.assert_called_once()
                # Verifica que o segundo argumento é o path final (tmp_path)
                # Primeiro argumento é o temp file (deve terminar com .tmp)
                temp_file_arg = mock_replace.call_args[0][0]
                final_file_arg = mock_replace.call_args[0][1]
                assert Path(str(tmp_path)) == Path(final_file_arg)
                assert str(temp_file_arg).endswith(".tmp")

        finally:
            if tmp_path.exists():
                tmp_path.unlink()
            OmniMind._instance = None
            OmniMind._initialized = False

    @pytest.mark.asyncio
    async def test_temp_file_cleaned_on_error(self):
        """Se escrita falhar, temp file deve ser limpo."""
        from iaglobal.obsidian.omnimind import OmniMind

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp_path = Path(f.name)
            json.dump([], f)

        try:
            omni = OmniMind(state_path=tmp_path)
            omni._memoria_coletiva = [{"test": "data"}]

            # Mock que falha no json.dump
            with patch("iaglobal.obsidian.omnimind.json.dump") as mock_dump:
                mock_dump.side_effect = RuntimeError("Simulated error")

                # Não deve lançar exceção (é tratada com warning)
                omni._salvar_estado()

            # Verifica que não sobraram arquivos temp
            temp_files = list(tmp_path.parent.glob(tmp_path.stem + "_*.tmp"))
            assert len(temp_files) == 0, "Temp file não foi limpo após erro"

        finally:
            if tmp_path.exists():
                tmp_path.unlink()


# ═══════════════════════════════════════════════════════════════════
# FIX-2: drain_background_tasks() no shutdown
# ═══════════════════════════════════════════════════════════════════


class TestBackgroundTasksDrain:
    """Background tasks devem ser drenadas antes do shutdown."""

    @pytest.mark.asyncio
    async def test_drain_waits_for_completion(self):
        """drain_background_tasks() deve aguardar tasks completarem."""
        from iaglobal.graphs.execution_graph import ExecutionGraph

        g = ExecutionGraph()

        # Cria task que demora para completar
        completed = False

        async def _slow_task():
            nonlocal completed
            await asyncio.sleep(0.1)
            completed = True

        task = asyncio.create_task(_slow_task())
        g._background_tasks.add(task)
        # Adiciona callback manualmente (como _record_recovery_decision faz)
        task.add_done_callback(g._on_recovery_task_done)

        # Drena
        await g.drain_background_tasks(timeout=2.0)
        # Dá chance ao done_callback rodar
        await asyncio.sleep(0.01)

        assert completed, "Task não completou durante drain"
        assert len(g._background_tasks) == 0, "Task não foi removida da set"

    @pytest.mark.asyncio
    async def test_drain_empty_set_no_op(self):
        """Drain com set vazio deve ser no-op."""
        from iaglobal.graphs.execution_graph import ExecutionGraph

        g = ExecutionGraph()
        g._background_tasks = set()

        # Não deve levantar
        await g.drain_background_tasks()

    @pytest.mark.asyncio
    async def test_drain_timeout(self):
        """Drain com timeout — tasks não completadas NÃO são canceladas,
        apenas logadas como pendentes."""
        from iaglobal.graphs.execution_graph import ExecutionGraph

        g = ExecutionGraph()

        async def _slow_task():
            await asyncio.sleep(0.5)  # Completa após timeout

        task = asyncio.create_task(_slow_task())
        g._background_tasks.add(task)

        # Timeout curto — task não completa
        await g.drain_background_tasks(timeout=0.05)

        # Task NÃO foi cancelada — ainda está rodando
        assert not task.cancelled()
        assert not task.done()

        # Aguarda task completar manualmente
        await task
        assert task.done()

    @pytest.mark.asyncio
    async def test_drain_handles_exceptions(self):
        """Drain deve lidar com tasks que levantam exceção."""
        from iaglobal.graphs.execution_graph import ExecutionGraph

        g = ExecutionGraph()

        async def _failing_task():
            raise RuntimeError("Task falhou")

        task = asyncio.create_task(_failing_task())
        g._background_tasks.add(task)
        # Adiciona callback manualmente (como _record_recovery_decision faz)
        task.add_done_callback(g._on_recovery_task_done)

        # Não deve levantar (return_exceptions=True)
        await g.drain_background_tasks(timeout=2.0)
        # Dá chance ao done_callback rodar
        await asyncio.sleep(0.01)

        # Task foi removida mesmo com exceção
        assert len(g._background_tasks) == 0


# ═══════════════════════════════════════════════════════════════════
# Integration: Pipeline drain
# ═══════════════════════════════════════════════════════════════════


class TestPipelineDrainIntegration:
    """Pipeline deve drenar tasks antes de retornar."""

    @pytest.mark.asyncio
    async def test_pipeline_drains_before_return(self):
        """Simula retorno do pipeline e verifica drain."""
        from iaglobal.graphs.execution_graph import ExecutionGraph

        g = ExecutionGraph()
        drained = False

        # Mock do drain para verificar chamada
        original_drain = g.drain_background_tasks

        async def _mock_drain(**kwargs):
            nonlocal drained
            drained = True
            return await original_drain(**kwargs)

        g.drain_background_tasks = _mock_drain

        # Simula adição de task
        async def _dummy():
            pass

        g._background_tasks.add(asyncio.create_task(_dummy()))

        # Simula retorno do pipeline
        await g.drain_background_tasks(timeout=2.0)

        assert drained, "Drain não foi chamado"
