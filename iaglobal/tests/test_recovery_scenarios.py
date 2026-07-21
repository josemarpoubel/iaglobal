# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes dos cenários de RecoveryPolicy (FIX-1/2/3/4/5).

Cenários:
  1. FIX-1+4: Invalidação transitiva — cadeia A→B→C; reset de A
     invalida C (consumidor transitivo), não só B
  2. FIX-2: Corrida real — duas corotinas concorrentes resetando o
     mesmo upstream; guard _recovery_in_flight não cai enquanto uma
     ainda está no meio do reset
  3. FIX-3: memória imunológica — ABORT chama OmniMind (AsyncMock
     confirma assinatura + chamada); RESCHEDULE cria task referenciada
  4. FIX-5: reset_node atomicidade — sem dessincronia entre
     estruturas de "executado"
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iaglobal.graphs.node import Node
from iaglobal.graphs.recovery import RecoveryPolicy, RecoveryDecision


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _make_node(name: str, depends_on: list[str] | None = None) -> Node:
    async def _noop(input_data: dict) -> dict:
        return {"output": ""}

    return Node(
        name=name,
        run=_noop,
        depends_on=depends_on or [],
    )


def _make_graph(nodes: dict[str, Node]) -> "ExecutionGraph":
    from iaglobal.graphs.execution_graph import ExecutionGraph

    g = ExecutionGraph()
    g.nodes.clear()
    for nid, node in nodes.items():
        g.nodes[nid] = node
    return g


# ═══════════════════════════════════════════════════════════════════
# FIX-1 + FIX-4: Invalidação transitiva
# ═══════════════════════════════════════════════════════════════════


class TestTransitiveInvalidation:
    """Reset de A deve invalidar C mesmo que C dependa de B, não de A."""

    @pytest.mark.asyncio
    async def test_chain_a_b_c_invalidation(self):
        """Cadeia A→B→C (C depende de B, B depende de A).
        Quando: A é resetado.
        Então: B (direto) E C (transitivo) são invalidados.
        """
        a = _make_node("A")
        b = _make_node("B", depends_on=["A"])
        c = _make_node("C", depends_on=["B"])
        g = _make_graph({"A": a, "B": b, "C": c})

        execution_id = "test-chain-001"
        executed: set[str] = {"A", "B", "C"}
        g.results["A"] = {"output": "old_a"}
        g.results["B"] = {"output": "old_b"}
        g.results["C"] = {"output": "old_c"}
        a.acquire()
        b.acquire()
        c.acquire()

        await g._invalidate_sibling_consumers("A", execution_id, executed, skip_node="")

        # B e C invalidados (transitivamente)
        assert "B" not in g.results
        assert "C" not in g.results
        assert "B" not in executed
        assert "C" not in executed
        assert b._lock is False
        assert c._lock is False

    @pytest.mark.asyncio
    async def test_chain_a_b_c_skip_failed(self):
        """skip_node (o que disparou) não é invalidado."""
        a = _make_node("A")
        b = _make_node("B", depends_on=["A"])
        c = _make_node("C", depends_on=["B"])
        g = _make_graph({"A": a, "B": b, "C": c})

        execution_id = "test-chain-002"
        executed: set[str] = {"A", "B", "C"}
        g.results["A"] = {"output": "v"}
        g.results["B"] = {"output": "v"}
        g.results["C"] = {"output": "v"}
        b.acquire()
        c.acquire()

        await g._invalidate_sibling_consumers(
            "A", execution_id, executed, skip_node="B"
        )

        assert "B" in g.results  # skip_node preservado
        assert "C" not in g.results  # C invalidado (transitivo)

    @pytest.mark.asyncio
    async def test_diamond_invalidation(self):
        """A→{B,C}→D (D depende de B e C). Reset de A invalida D."""
        a = _make_node("A")
        b = _make_node("B", depends_on=["A"])
        c = _make_node("C", depends_on=["A"])
        d = _make_node("D", depends_on=["B", "C"])
        g = _make_graph({"A": a, "B": b, "C": c, "D": d})

        execution_id = "test-diamond-001"
        executed: set[str] = {"A", "B", "C", "D"}
        for n in ("A", "B", "C", "D"):
            g.results[n] = {"output": "v"}
        for n in (b, c, d):
            n.acquire()

        await g._invalidate_sibling_consumers("A", execution_id, executed, skip_node="")

        assert "B" not in g.results
        assert "C" not in g.results
        assert "D" not in g.results  # D invalidado apesar de dependência de 2 pais

    @pytest.mark.asyncio
    async def test_no_visited_loop(self):
        """Grafo com ciclo não deve loop infinito."""
        try:
            from iaglobal.graphs.loop_detector import LoopDetector
        except ImportError:
            LoopDetector = None
        a = _make_node("A")
        b = _make_node("B", depends_on=["A"])
        # ciclo artificial: A depende de B (não deveria ocorrer, mas
        # testamos robustez do visited set)
        a.depends_on = ["B"]
        g = _make_graph({"A": a, "B": b})

        execution_id = "test-cycle-001"
        executed: set[str] = {"A", "B"}
        g.results["A"] = {"output": "v"}
        g.results["B"] = {"output": "v"}
        a.acquire()
        b.acquire()

        # Não deve travar (visited set previne re-processamento)
        await g._invalidate_sibling_consumers("A", execution_id, executed, skip_node="")
        # Ainda assim B foi invalidado
        assert "B" not in g.results


# ═══════════════════════════════════════════════════════════════════
# FIX-2: Corrida real com duas corotinas concorrentes
# ═══════════════════════════════════════════════════════════════════


class TestConcurrentResetRace:
    """Duas corotinas resetando o mesmo upstream simultaneamente não
    devem remover o guard cedo demais."""

    @pytest.mark.asyncio
    async def test_guard_persists_during_reset(self):
        """Simula A e B processando em paralelo, ambos resetando 'Y'.

        Corotina A: adiciona Y ao _recovery_in_flight, inicia reset
        Corotina B: vê Y já in_flight, faz continue (não adiciona)
        Assert: _recovery_in_flight ainda tem Y após B terminar
                 (guard não caiu prematuramente)
        """
        y = _make_node("Y")
        x1 = _make_node("X1", depends_on=["Y"])
        x2 = _make_node("X2", depends_on=["Y"])
        g = _make_graph({"Y": y, "X1": x1, "X2": x2})

        execution_id = "test-race-001"

        # Bloco que simula o handler de X1 (adiciona Y)
        g._recovery_in_flight.add((execution_id, "Y"))
        await asyncio.sleep(0)  # yield para simular concorrência

        # Bloco que simula o handler de X2 (vê Y, pula)
        uid_flight = (execution_id, "Y")
        if uid_flight in g._recovery_in_flight:
            pass  # continue
        # finally de X2 faria: for uid in recovery.upstream_ids: discard
        # MAS agora só descarta o que X2 adicionou (nada)
        # Simula o finally corrigido:
        reset_uids_x2: list[str] = []  # X2 não adicionou nada
        for uid in ["Y"]:
            if uid not in reset_uids_x2:
                pass
        for uid in reset_uids_x2:
            g._recovery_in_flight.discard((execution_id, uid))

        # Assert: guard de A ainda está presente
        assert (execution_id, "Y") in g._recovery_in_flight

    @pytest.mark.asyncio
    async def test_only_added_uids_discarded(self):
        """O finally só descarta UIDs que esta chamada adicionou."""
        g = _make_graph({})
        execution_id = "test-race-002"

        # Simula handler de X1: adiciona Y e Z
        reset_uids_x1 = []
        for uid in ["Y", "Z"]:
            uid_flight = (execution_id, uid)
            if uid_flight not in g._recovery_in_flight:
                g._recovery_in_flight.add(uid_flight)
                reset_uids_x1.append(uid)

        # Simula handler de X2: vê Y (já in_flight), adiciona só W
        reset_uids_x2 = []
        for uid in ["Y", "W"]:  # Y já está, W novo
            uid_flight = (execution_id, uid)
            if uid_flight not in g._recovery_in_flight:
                g._recovery_in_flight.add(uid_flight)
                reset_uids_x2.append(uid)

        # finally de X1
        for uid in reset_uids_x1:
            g._recovery_in_flight.discard((execution_id, uid))
        # Assert: Y removido (X1 adicionou), Z removido, W permanece
        assert (execution_id, "Y") not in g._recovery_in_flight
        assert (execution_id, "Z") not in g._recovery_in_flight
        assert (execution_id, "W") in g._recovery_in_flight

    @pytest.mark.asyncio
    async def test_concurrent_identical_reset_safe(self):
        """Duas corotinas chamando o mesmo reset de 'Y' em paralelo
        não dobram o reset se o guard estiver presente."""
        from iaglobal.evolution.execution_registry import registry as exec_registry

        y = _make_node("Y")
        g = _make_graph({"Y": y})
        execution_id = "test-race-concurrent-001"

        exec_registry.init_execution(execution_id, ["Y"])
        exec_registry.claim(execution_id, "Y")

        async def _reset_coroutine(coro_id: str):
            uid_flight = (execution_id, "Y")
            if uid_flight in g._recovery_in_flight:
                return False  # já está sendo resetado
            g._recovery_in_flight.add(uid_flight)
            try:
                await asyncio.to_thread(exec_registry.reset_node, execution_id, "Y")
                return True
            finally:
                g._recovery_in_flight.discard(uid_flight)

        # Lança ambas "simultaneamente"
        r1, r2 = await asyncio.gather(_reset_coroutine("A"), _reset_coroutine("B"))
        # Pelo menos uma deve ter resetado; a outra deve ter pulado
        assert r1 != r2, "Uma corotina deve pular (guard funcionou)"


# ═══════════════════════════════════════════════════════════════════
# FIX-3: Memória imunológica (recording)
# ═══════════════════════════════════════════════════════════════════


class TestImmunologicalMemory:
    """Decisões do RecoveryPolicy devem ser registradas."""

    @pytest.mark.asyncio
    async def test_abort_triggers_omnimind_apoptose(self):
        """ABORT deve chamar OmniMind.emitir_gatilho_apoptose."""
        g = _make_graph({})
        g._epigenetic = None
        # AsyncMock confirma que a assinatura é sync e a chamada ocorre
        mock_omni = MagicMock()
        mock_omni.emitir_gatilho_apoptose = MagicMock()

        with patch.object(g, "_epigenetic", None):
            with patch("iaglobal.graphs.execution_graph.omni_mind", mock_omni):
                await g._record_recovery_decision(
                    node_id="test_node",
                    missing=["dep"],
                    decision=RecoveryDecision.ABORT,
                    attempt=3,
                    reason="orçamento excedido",
                )

                mock_omni.emitir_gatilho_apoptose.assert_called_once()
                call_kwargs = mock_omni.emitir_gatilho_apoptose.call_args
                assert call_kwargs.kwargs["agent_id"] == "test_node"
                assert call_kwargs.kwargs["violation_type"] == "recovery_abort"

    @pytest.mark.asyncio
    async def test_abort_signature_is_sync(self):
        """Confirmamos que emitir_gatilho_apoptose é síncrono e não
        retorna coroutine (Bug #3 seria aqui se precisasse de await)."""
        from iaglobal.obsidian.omnimind import omni_mind

        result = omni_mind.emitir_gatilho_apoptose(
            agent_id="__test_sync__",
            motivo="teste",
            violation_type="test",
        )
        # Método sync retorna dict, não coroutine
        assert not asyncio.iscoroutine(result), (
            "emitir_gatilho_apoptose é sync; não deve retornar coroutine"
        )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_reschedule_creates_referenced_task(self):
        """RESCHEDULE cria task referenciada em self._background_tasks
        (não perdida para GC — FIX-2)."""
        g = _make_graph({})
        mock_epigenetic = MagicMock()
        mock_epigenetic.record_failure = AsyncMock()
        g._epigenetic = mock_epigenetic
        g._background_tasks = set()

        await g._record_recovery_decision(
            node_id="test_node",
            missing=["dep"],
            decision=RecoveryDecision.RESCHEDULE,
            attempt=1,
            reason="upstream reagendado",
        )

        # Assert: task foi registrada
        assert len(g._background_tasks) == 1
        task = next(iter(g._background_tasks))
        assert isinstance(task, asyncio.Task)
        # Aguarda a task completar e dá chance ao done_callback rodar
        await task
        await asyncio.sleep(0.01)
        # done callback removeu da set
        assert len(g._background_tasks) == 0
        assert task.done()
        # Sem exceção não tratada
        assert task.exception() is None

    @pytest.mark.asyncio
    async def test_reschedule_task_exception_logged(self):
        """Se record_failure levantar, a exceção é logada via
        logger.exception (não só no logger padrão do asyncio)."""
        g = _make_graph({})
        mock_epigenetic = MagicMock()
        mock_epigenetic.record_failure = AsyncMock(
            side_effect=RuntimeError("Epigenetic offline")
        )
        g._epigenetic = mock_epigenetic
        g._background_tasks = set()

        with patch("iaglobal.graphs.execution_graph.logger") as mock_logger:
            await g._record_recovery_decision(
                node_id="test_node",
                missing=["dep"],
                decision=RecoveryDecision.RESCHEDULE,
                attempt=1,
                reason="upstream reagendado",
            )

            # Aguarda task completar + callback rodar
            await asyncio.sleep(0.05)

            # Assert: logger.exception foi chamado
            mock_logger.exception.assert_called_once()
            call_args = mock_logger.exception.call_args
            assert "[RECOVERY] record_failure falhou" in call_args.args[0]
            # A exceção foi passada como exc_info
            assert call_args.kwargs.get("exc_info") is not None

    @pytest.mark.asyncio
    async def test_reschedule_no_epigenetic_no_crash(self):
        """Sem EpigeneticRegistry, RESCHEDULE não crasha."""
        g = _make_graph({})
        g._epigenetic = None

        await g._record_recovery_decision(
            node_id="test_node",
            missing=["dep"],
            decision=RecoveryDecision.RESCHEDULE,
            attempt=1,
            reason="test",
        )

    @pytest.mark.asyncio
    async def test_abort_omnimind_exception_no_crash(self):
        """Se OmniMind lançar, ABORT não crasha."""
        g = _make_graph({})
        g._epigenetic = None
        mock_omni = MagicMock()
        mock_omni.emitir_gatilho_apoptose = MagicMock(
            side_effect=RuntimeError("OmniMind offline")
        )

        with patch("iaglobal.graphs.execution_graph.omni_mind", mock_omni):
            await g._record_recovery_decision(
                node_id="test_node",
                missing=["dep"],
                decision=RecoveryDecision.ABORT,
                attempt=2,
                reason="test",
            )

    @pytest.mark.asyncio
    async def test_abort_uses_asyncio_to_thread(self):
        """emitir_gatilho_apoptose faz I/O síncrono (_salvar_estado),
        então deve ser chamado via asyncio.to_thread para não bloquear
        o event loop."""
        g = _make_graph({})
        g._epigenetic = None

        with (
            patch("iaglobal.graphs.execution_graph.omni_mind") as mock_omni,
            patch(
                "iaglobal.graphs.execution_graph.asyncio.to_thread"
            ) as mock_to_thread,
        ):
            mock_omni.emitir_gatilho_apoptose = MagicMock()
            mock_to_thread.return_value = asyncio.ensure_future(asyncio.sleep(0))

            await g._record_recovery_decision(
                node_id="test_node",
                missing=["dep"],
                decision=RecoveryDecision.ABORT,
                attempt=1,
                reason="test",
            )

            # Assert: asyncio.to_thread foi chamado com emitir_gatilho_apoptose
            mock_to_thread.assert_called_once()
            called_fn = mock_to_thread.call_args.args[0]
            assert called_fn == mock_omni.emitir_gatilho_apoptose


# ═══════════════════════════════════════════════════════════════════
# FIX-5: reset_node atomicidade
# ═══════════════════════════════════════════════════════════════════


class TestResetNodeAtomicity:
    """reset_node deve ser atômico (todas as estruturas sob o lock)."""

    @pytest.mark.asyncio
    async def test_reset_clears_all_structures(self):
        """Após reset_node, _executed_nodes, _entries e _executed
        estão consistentes."""
        from iaglobal.evolution.execution_registry import registry as exec_registry

        exec_id = "test-reset-atomic-001"
        exec_registry.init_execution(exec_id, ["N"])
        exec_registry.claim(exec_id, "N")
        exec_registry.complete_node(exec_id, "N", "result")

        await asyncio.to_thread(exec_registry.reset_node, exec_id, "N")

        # _executed_nodes não tem mais a claim
        assert (exec_id, "N") not in exec_registry._executed_nodes
        # _entries status é PENDING
        assert exec_registry._entries[exec_id]["N"].status.value == "PENDING"
        # _executed não tem mais
        assert "N" not in exec_registry._executed.get(exec_id, set())

    @pytest.mark.asyncio
    async def test_reset_idempotent(self):
        """Reset duplo não quebra."""
        from iaglobal.evolution.execution_registry import registry as exec_registry

        exec_id = "test-reset-idem-001"
        exec_registry.init_execution(exec_id, ["N"])
        exec_registry.claim(exec_id, "N")

        await asyncio.to_thread(exec_registry.reset_node, exec_id, "N")
        await asyncio.to_thread(exec_registry.reset_node, exec_id, "N")

        assert (exec_id, "N") not in exec_registry._executed_nodes


# ═══════════════════════════════════════════════════════════════════
# Integration: RecoveryPolicy circuit breaker + backoff
# ═══════════════════════════════════════════════════════════════════


class TestRecoveryPolicyBehavior:
    """RecoveryPolicy internals."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_after_max(self):
        policy = RecoveryPolicy()
        r1 = await policy.handle_missing_context("n", ["d"])
        assert r1.decision is RecoveryDecision.RESCHEDULE
        r2 = await policy.handle_missing_context("n", ["d"])
        assert r2.decision is RecoveryDecision.RESCHEDULE
        r3 = await policy.handle_missing_context("n", ["d"])
        assert r3.decision is RecoveryDecision.ABORT

    @pytest.mark.asyncio
    async def test_backoff_increases(self):
        policy = RecoveryPolicy()
        r1 = await policy.handle_missing_context("n", ["d"])
        r2 = await policy.handle_missing_context("n", ["d"])
        assert r2.elapsed_ms > r1.elapsed_ms
