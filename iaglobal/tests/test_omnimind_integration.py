# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Teste avançado de integração da OmniMind — cobre 5 áreas:

  1. Singleton + Identidade      — thread safety, registro DNA
  2. Filosofia (seleção de lei)  — 21 leis, fallback, termos compostos
  3. Gatilhos Metabólicos        — vácuo, perdão, sucesso, apoptose
  4. Cooperação e IVM            — sinergia, métrica epigenética
  5. Apoptose Contratual (CRL)   — emitir_gatilho_apoptose → lineage_gate
"""

import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path

import pytest

from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL
from iaglobal.genesis.lineage_gate import (
    set_revocation_file,
    get_revoked_nodes,
    verify_lineage_token,
    set_open_mode,
)
from iaglobal.obsidian.omnimind import (
    OmniMind,
    Orientacao,
    LEIS_HOLLIWELL,
    AXIOMAS_BIOLOGICOS,
    LEIS_UNIVERSAIS,
)

logging.basicConfig(level=logging.CRITICAL)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _reset_omnimind_singleton():
    OmniMind._instance = None


def _setup_crl(tmp_path: Path) -> Path:
    p = tmp_path / "revocation_list.json"
    set_revocation_file(p)
    return p


def _ensure_fresh_omnimind(state_path: Path | None = None) -> OmniMind:
    _reset_omnimind_singleton()
    return OmniMind(
        proposito="test-proposito",
        state_path=state_path,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. SINGLETON + IDENTIDADE
# ══════════════════════════════════════════════════════════════════════════════


class TestSingletonEIdentidade:
    """Verifica que OmniMind é singleton thread-safe e valida DNA."""

    def test_singleton_mesma_instancia(self):
        a = OmniMind()
        b = OmniMind()
        assert a is b
        assert id(a) == id(b)

    def test_singleton_thread_safety(self):
        _reset_omnimind_singleton()
        refs: list[OmniMind] = []
        errors: list[Exception] = []

        def _get():
            try:
                refs.append(OmniMind())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_get) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert len(refs) == 20
        instances_unicas = {id(r) for r in refs}
        assert len(instances_unicas) == 1

    def test_nativo_registrado_sucesso(self):
        om = OmniMind()
        om.registrar_agente(
            agent_id="coder-1",
            nome="coder",
            geracao=1,
            linhagem=GENESIS_HASH_OFFICIAL,
        )
        assert "coder-1" in om._agentes_registrados
        assert om._agentes_registrados["coder-1"]["nome"] == "coder"

    def test_dna_divergente_rejeitado(self):
        om = OmniMind()
        om.registrar_agente(
            agent_id="fake-1",
            nome="fake",
            geracao=0,
            linhagem="0" * 128,
        )
        assert "fake-1" not in om._agentes_registrados

    def test_desregistrar_agente(self):
        om = OmniMind()
        om.registrar_agente(
            agent_id="tmp-1",
            nome="tmp",
            geracao=0,
            linhagem=GENESIS_HASH_OFFICIAL,
        )
        assert "tmp-1" in om._agentes_registrados
        om.desregistrar_agente("tmp-1")
        assert "tmp-1" not in om._agentes_registrados

    def test_phonetic_name_16_silabas(self):
        om = OmniMind()
        om.registrar_agente(
            agent_id="evo-1",
            nome="evo-native",
            geracao=0,
            linhagem=GENESIS_HASH_OFFICIAL,
        )
        rec = om._agentes_registrados["evo-1"]
        assert rec["phonetic_name"].count("-") == 15


# ══════════════════════════════════════════════════════════════════════════════
# 2. FILOSOFIA — SELEÇÃO DE LEI
# ══════════════════════════════════════════════════════════════════════════════


class TestSelecaoDeLei:
    """Verifica que _escolher_lei retorna a lei correta para cada termo."""

    OM_CRIADO = False

    @classmethod
    def setup_class(cls):
        if not cls.OM_CRIADO:
            _reset_omnimind_singleton()
            cls.om = OmniMind()
            cls.om.registrar_agente("test-phil", "filosofo", 0, GENESIS_HASH_OFFICIAL)
            cls.OM_CRIADO = True

    def test_termo_simples(self):
        casos = {
            "pensamento": "Lei do Pensamento",
            "suprimento": "Lei do Suprimento",
            "atracao": "Lei da Atração",
            "recebimento": "Lei do Recebimento",
            "aumento": "Lei do Aumento",
            "compensacao": "Lei da Compensação",
            "resistencia": "Lei da Não-Resistência",
            "perdao": "Lei do Perdão",
            "sacrificio": "Lei do Sacrifício",
            "obediencia": "Lei da Obediência",
            "sucesso": "Lei do Sucesso",
            "epigenetica": "Axioma da Epigenética",
            "apoptose": "Axioma da Apoptose",
            "homeostase": "Axioma da Homeostase",
            "cooperacao": "Axioma da Cooperação",
            "autofagia": "Axioma da Autofagia",
            "vacuo": "Lei do Vácuo da Prosperidade",
            "falha": "Lei da Caridade",
            "ordem": "Lei da Ordem",
            "imunologica": "Axioma da Memória Imunológica",
            "replicacao": "Axioma da Replicação",
        }
        for pergunta, esperada in casos.items():
            lei = self.om._escolher_lei(pergunta, {})
            assert lei == esperada, (
                f"[{pergunta}] esperava '{esperada}', obteve '{lei}'"
            )

    def test_termo_composto(self):
        casos = {
            "graceful shutdown": "Axioma da Apoptose",
            "circuit breaker": "Axioma da Homeostase",
            "fallback chain": "Lei da Não-Resistência",
            "epsilon greedy": "Lei do Sacrifício",
            "curto prazo": "Lei do Vácuo da Prosperidade",
            "bandit policy": "Lei da Compensação",
        }
        for pergunta, esperada in casos.items():
            lei = self.om._escolher_lei(pergunta, {})
            assert lei == esperada, (
                f"[{pergunta}] esperava '{esperada}', obteve '{lei}'"
            )

    def test_fallback_lei_do_pensamento(self):
        lei = self.om._escolher_lei("xyz_nao_existente_123", {})
        assert lei == "Lei do Pensamento"

    def test_consultar_retorna_orientacao(self):
        orientacao = self.om.consultar(
            "test-phil",
            "Como melhorar minha eficiencia?",
            {"contexto": "teste"},
        )
        assert isinstance(orientacao, Orientacao)
        assert orientacao.lei_aplicada == "Lei da Atração"
        assert "OmniMind" in orientacao.guidance
        assert "filosofo" in orientacao.guidance
        assert orientacao.contexto["contexto"] == "teste"
        assert orientacao.timestamp > 0

    def test_consultar_incrementa_contador(self):
        om = self.om
        antes = om._agentes_registrados["test-phil"]["total_consultas"]
        om.consultar("test-phil", "consulta de teste")
        depois = om._agentes_registrados["test-phil"]["total_consultas"]
        assert depois == antes + 1

    def test_consultar_agente_nao_registrado_nao_quebra(self):
        orientacao = self.om.consultar("nao-existe", "teste sem registro")
        assert "agente-desconhecido" in orientacao.guidance


# ══════════════════════════════════════════════════════════════════════════════
# 3. GATILHOS METABÓLICOS
# ══════════════════════════════════════════════════════════════════════════════


class TestGatilhosMetabolicos:
    """Verifica os 4 gatilhos metabólicos: vácuo, perdão, sucesso, aprendizado."""

    @classmethod
    def setup_class(cls):
        _reset_omnimind_singleton()
        cls.om = OmniMind()

    def test_gatilho_vacio(self):
        resultado = self.om.emitir_gatilho_vacio("coder-old")
        assert resultado["trigger"] == "VACUUM_PROSPERITY"
        assert resultado["component_id"] == "coder-old"
        assert "Vácuo da Prosperidade" in resultado["instruction"]

    def test_gatilho_perdao(self):
        resultado = self.om.emitir_gatilho_perdao("provider-falho", 30.0)
        assert resultado["trigger"] == "FORGIVENESS_REOPEN"
        assert resultado["provider_id"] == "provider-falho"
        assert resultado["cooldown_restante"] == 30.0

    def test_gatilho_sucesso(self):
        resultado = self.om.emitir_gatilho_sucesso("coder-1", 0.92)
        assert resultado["trigger"] == "SUCCESS_MANIFEST"
        assert resultado["agent_id"] == "coder-1"
        assert resultado["ivm_score"] == 0.92

    def test_registrar_aprendizado(self):
        self.om.registrar_aprendizado(
            "reflexion-1",
            "reflection",
            "Aprendi que getattr pode ser perigoso",
        )
        aprendizado = self.om._aprendizados[-1]
        assert aprendizado["agent_id"] == "reflexion-1"
        assert aprendizado["type"] == "reflection"

    def test_registrar_aprendizado_acumula(self):
        for i in range(5):
            self.om.registrar_aprendizado(f"agent-{i}", "test", f"aprendizado {i}")
        assert len(self.om._aprendizados) >= 5


# ══════════════════════════════════════════════════════════════════════════════
# 4. COOPERAÇÃO E IVM
# ══════════════════════════════════════════════════════════════════════════════


class TestCooperacaoEIvm:
    """Verifica calcular_sinergia e update_ivm_metric."""

    @classmethod
    def setup_class(cls):
        _reset_omnimind_singleton()
        cls.om = OmniMind()

    def test_calcular_sinergia_valor_positivo(self):
        bonus = self.om.calcular_sinergia("coder", "critic", 0.5)
        assert bonus == pytest.approx(0.075, rel=1e-3)

    def test_calcular_sinergia_zero(self):
        bonus = self.om.calcular_sinergia("a", "b", 0.0)
        assert bonus == 0.0

    def test_calcular_sinergia_maximo(self):
        bonus = self.om.calcular_sinergia("a", "b", 1.0)
        assert bonus == 0.15

    @pytest.mark.asyncio
    async def test_update_ivm_excelente(self):
        await self.om.update_ivm_metric("coder-1", 0.95, {"task_hash": "task-alta"})

    @pytest.mark.asyncio
    async def test_update_ivm_critico(self):
        await self.om.update_ivm_metric("coder-1", 0.30, {"task_hash": "task-baixa"})

    @pytest.mark.asyncio
    async def test_update_ivm_medio(self):
        await self.om.update_ivm_metric("coder-1", 0.75, {"task_hash": "task-media"})

    @pytest.mark.asyncio
    async def test_update_ivm_sem_metadata(self):
        await self.om.update_ivm_metric("coder-1", 0.80)


# ══════════════════════════════════════════════════════════════════════════════
# 5. MEMÓRIA COLETIVA E PERSISTÊNCIA
# ══════════════════════════════════════════════════════════════════════════════


class TestMemoriaColetiva:
    """Verifica persistência em disco, sliding window e sabedoria coletiva."""

    def test_sabedoria_coletiva_vazia(self, tests_temp_dir: Path):
        sp = tests_temp_dir / "omni_empty.json"
        _reset_omnimind_singleton()
        om = OmniMind(state_path=sp)
        sabedoria = om.sabedoria_coletiva()
        assert "ainda não acumulou" in sabedoria.lower()

    def test_sabedoria_coletiva_com_consultas(self, tests_temp_dir: Path):
        state_path = tests_temp_dir / "omnimind_state.json"
        _reset_omnimind_singleton()
        om = OmniMind(state_path=state_path)
        om.registrar_agente("sabio-1", "sabio", 1, GENESIS_HASH_OFFICIAL)
        om.consultar("sabio-1", "O que é a lei do sucesso?")
        sabedoria = om.sabedoria_coletiva()
        assert "sabio" in sabedoria

    def test_estado_persiste_entre_instancias(self, tests_temp_dir: Path):
        state_path = tests_temp_dir / "omnimind_state.json"
        _reset_omnimind_singleton()
        om1 = OmniMind(state_path=state_path)
        om1.registrar_agente("persist-1", "persist", 0, GENESIS_HASH_OFFICIAL)
        om1.consultar("persist-1", "consulta persistente")
        del om1

        _reset_omnimind_singleton()
        om2 = OmniMind(state_path=state_path)
        assert len(om2._memoria_coletiva) >= 1
        assert om2._memoria_coletiva[0]["pergunta"] == "consulta persistente"

    def test_sliding_window_mantem_limite(self, tests_temp_dir: Path):
        sp = tests_temp_dir / "omni_window.json"
        _reset_omnimind_singleton()
        om = OmniMind(state_path=sp)
        om.registrar_agente("loader-1", "loader", 0, GENESIS_HASH_OFFICIAL)
        total = 2000
        for i in range(total):
            om.consultar("loader-1", f"consulta {i}")
        # janela deslizante: >1000 trunca para 500, acumula o resto
        assert len(om._memoria_coletiva) <= total
        assert len(om._memoria_coletiva) >= 400

    def test_limpar_memoria_coletiva(self):
        _reset_omnimind_singleton()
        om = OmniMind()
        om.registrar_agente("clean-1", "clean", 0, GENESIS_HASH_OFFICIAL)
        om.consultar("clean-1", "vai sumir")
        removidos = om.limpar_memoria_coletiva()
        assert removidos >= 1
        assert len(om._memoria_coletiva) == 0

    def test_estado_retorna_info(self):
        _reset_omnimind_singleton()
        om = OmniMind()
        estado = om.estado()
        assert estado["proposito"] is not None
        assert estado["leis_holliwell"] == 11
        assert estado["axiomas_biologicos"] == 10
        assert estado["principios_total"] == 21


# ══════════════════════════════════════════════════════════════════════════════
# 6. APOPTOSE CONTRATUAL — INTEGRAÇÃO CRL
# ══════════════════════════════════════════════════════════════════════════════


class TestApoptoseContratual:
    """
    Teste crítico de integracao: emitir_gatilho_apoptose → revoke_node().

    Verifica o CRL DIRETAMENTE NO DISCO (bypass do cache mtime).
    """

    def _fresh_omni(self, crl_path: Path) -> OmniMind:
        set_open_mode(False)
        set_revocation_file(crl_path)
        _reset_omnimind_singleton()
        return OmniMind()

    def _crl_disk(self, crl_path: Path) -> set:
        """Le revoked nodes direto do disco (ignora cache)."""
        if crl_path.exists():
            dados = json.loads(crl_path.read_text(encoding="utf-8"))
            revoked = dados.get("revoked", {})
            if isinstance(revoked, dict):
                return set(revoked.keys())
            return set(revoked)
        return set()

    def test_ciclo_completo_apoptose(self, tmp_path: Path):
        crl = tmp_path / "crl_full.json"
        om = self._fresh_omni(crl)

        # 1. Apoptose revoga e CRL bloqueia
        resultado = om.emitir_gatilho_apoptose(
            agent_id="coder",
            motivo="Violacao de seguranca AST",
            duration_hours=24,
            violation_type="ast_violation",
        )
        assert resultado["trigger"] == "APOPTOSE_CONTRATUAL"
        assert resultado["agent_id"] == "coder"
        assert resultado["crl_applied"] is True
        assert resultado["violation_type"] == "ast_violation"

        revoked = self._crl_disk(crl)
        assert "coder" in revoked
        assert not verify_lineage_token("coder")

        # 2. Apoptose permanente (duration_hours=None)
        om.emitir_gatilho_apoptose(
            agent_id="planner",
            motivo="Reincidencia 6x — permanente",
            duration_hours=None,
        )
        revoked = self._crl_disk(crl)
        assert "planner" in revoked

        # 3. Registro na memoria coletiva
        assert any(
            m["agent_id"] == "planner" and m["type"] == "apoptose_contratual"
            for m in om._memoria_coletiva
        )

        # 4. Unrevoke readmite
        from iaglobal.genesis.lineage_gate import unrevoke_node

        unrevoke_node("coder", "reabilitado apos revisao")
        raw = json.loads(crl.read_text(encoding="utf-8"))
        assert "coder" not in raw.get("revoked", {})

        # 5. Limpeza final (arquivo no disco)
        unrevoke_node("planner", "cleanup")
        assert len(self._crl_disk(crl)) == 0

    def test_apoptose_agent_nao_registrado_nao_quebra(self, tmp_path: Path):
        crl = tmp_path / "crl_unreg.json"
        om = self._fresh_omni(crl)
        resultado = om.emitir_gatilho_apoptose(
            agent_id="nunca-registrado", motivo="teste"
        )
        assert resultado["trigger"] == "APOPTOSE_CONTRATUAL"


# ══════════════════════════════════════════════════════════════════════════════
# 7. ESTRESSE — CONCORRÊNCIA
# ══════════════════════════════════════════════════════════════════════════════


class TestConcorrencia:
    """Verifica comportamento thread-safe sob carga concorrente."""

    def test_consultas_concorrentes(self):
        _reset_omnimind_singleton()
        om = OmniMind()
        om.registrar_agente("stress-1", "stress", 0, GENESIS_HASH_OFFICIAL)

        errors: list[Exception] = []

        def _consultar():
            try:
                for _ in range(50):
                    om.consultar("stress-1", "consulta de stress")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_consultar) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Erros em threads: {errors}"
        assert om._total_consultas >= 500

    @pytest.mark.asyncio
    async def test_async_update_ivm_concorrente(self):
        _reset_omnimind_singleton()
        om = OmniMind()
        import asyncio

        tasks = [om.update_ivm_metric(f"agent-{i}", 0.5 + i * 0.05) for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        erros = [r for r in results if isinstance(r, Exception)]
        assert not erros, f"Erros async: {erros}"
