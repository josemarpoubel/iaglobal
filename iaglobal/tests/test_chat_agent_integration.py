# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes de integração — iaglobal/interface/chat_agent.py

Valida:
  1. IntencaoBiologica — schema pydantic
  2. EvoAgentColony — registro, seleção, DNA gate, fallback fitness
  3. interagir_com_colonia — pipeline completo com arbitrar_geracao mockado
  4. criar_colonia_evoagents — fábrica
  5. Erro: DNA divergente rejeitado, colônia vazia
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iaglobal.interface.chat_agent import (
    IntencaoBiologica,
    EvoAgentColony,
    RegistroEvoAgent,
    interagir_com_colonia,
    criar_colonia_evoagents,
    LINEAGE_MARKER,
)
from iaglobal.evolution.evo_agent import EvoAgent


# ═══════════════════════════════════════════════════════════════════
# 1. IntencaoBiologica — schema
# ═══════════════════════════════════════════════════════════════════


class TestIntencaoBiologica:
    def test_campos_obrigatorios(self):
        i = IntencaoBiologica(comando="analise dados")
        assert i.comando == "analise dados"
        assert i.urgencia == "normal"
        assert i.familia_alvo is None
        assert i.contexto_adicional == {}

    def test_campos_completos(self):
        i = IntencaoBiologica(
            comando="corrigir bug critico",
            urgencia="critica",
            familia_alvo="debugger",
            contexto_adicional={"trace": "erro.txt"},
        )
        assert i.comando == "corrigir bug critico"
        assert i.urgencia == "critica"
        assert i.familia_alvo == "debugger"

    def test_serializacao(self):
        i = IntencaoBiologica(comando="teste")
        d = i.model_dump()
        assert d["comando"] == "teste"
        assert d["urgencia"] == "normal"


# ═══════════════════════════════════════════════════════════════════
# 2. EvoAgentColony — pool e DNA gate
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
async def evo_agent():
    agent = await EvoAgent.genesis(
        task_hint="test-agent",
        name="evo-test-agent",
        nadph_reserve=0.5,
    )
    yield agent
    if agent.running:
        await agent.apoptose("test_cleanup")


@pytest.fixture
def colony():
    return EvoAgentColony()


class TestEvoAgentColony:
    async def test_registrar_valido(self, colony, evo_agent):
        esp = await colony.registrar(evo_agent, "generalista")
        assert esp == "generalista"
        assert "generalista" in colony._agentes

    async def test_registrar_dna_divergente(self, colony):
        fake = MagicMock(spec=EvoAgent)
        fake.lineage_marker = ""
        with pytest.raises(ValueError, match="DNA"):
            await colony.registrar(fake, "invasor")

    async def test_registrar_tipo_invalido(self, colony):
        with pytest.raises(ValueError, match="DNA"):
            await colony.registrar("not_an_agent", "invasor")

    async def test_selecionar_por_especializacao(self, colony, evo_agent):
        await colony.registrar(evo_agent, "analista")
        registro = await colony.selecionar("analista")
        assert registro.especializacao == "analista"
        assert registro.instancia is evo_agent

    async def test_selecionar_fallback_menor_falha(self, colony):
        a1 = MagicMock(spec=EvoAgent)
        a1.lineage_marker = "a1b2c3d4e5f6a7b8"
        a2 = MagicMock(spec=EvoAgent)
        a2.lineage_marker = "b2c3d4e5f6a7b8c9"

        await colony.registrar(a1, "agente_a")
        await colony.registrar(a2, "agente_b")

        colony._agentes["agente_a"].execucoes = 10
        colony._agentes["agente_a"].falhas = 8
        colony._agentes["agente_b"].execucoes = 10
        colony._agentes["agente_b"].falhas = 1

        escolhido = await colony.selecionar(None)
        assert escolhido.especializacao == "agente_b"

    async def test_colonia_vazia(self, colony):
        with pytest.raises(RuntimeError, match="vazia"):
            await colony.selecionar()

    async def test_registrar_resultado(self, colony, evo_agent):
        await colony.registrar(evo_agent, "worker")
        await colony.registrar_resultado("worker", sucesso=True, latencia=0.1)
        r = colony._agentes["worker"]
        assert r.execucoes == 1
        assert r.falhas == 0
        assert r.latencia_media == 0.1

        await colony.registrar_resultado("worker", sucesso=False, latencia=0.3)
        assert r.execucoes == 2
        assert r.falhas == 1


# ═══════════════════════════════════════════════════════════════════
# 3. interagir_com_colonia — pipeline completo
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_critic():
    """Substitui _get_critic por um mock que retorna arbitrar_geracao controlado."""
    mock = MagicMock()
    mock.arbitrar_geracao = AsyncMock(
        return_value='{"comando": "processar relatorio", "urgencia": "normal", "familia_alvo": null, "contexto_adicional": {}}'
    )
    with patch("iaglobal.interface.chat_agent._get_critic", return_value=mock):
        yield mock


class TestInteragirComColonia:
    async def test_fluxo_completo(self, mock_critic, evo_agent):
        colonia = EvoAgentColony()
        await colonia.registrar(evo_agent, "generalista")

        resultado = await interagir_com_colonia(colonia, "processar relatorio")

        assert "erro" not in resultado
        assert resultado["synthesis"] is not None
        assert "EVO-AGENT" in resultado["synthesis"]
        assert resultado["agente_utilizado"] == "generalista"

        metrics = resultado["execution_metrics"]
        assert metrics["success"] is True
        assert metrics["latency"] is not None
        assert metrics["latency"] >= 0

    async def test_colonia_vazia_retorna_erro(self, mock_critic):
        colonia = EvoAgentColony()
        resultado = await interagir_com_colonia(colonia, "qualquer coisa")
        assert resultado.get("erro") == "colonia_vazia"

    async def test_extracao_falha_retorna_erro(self, evo_agent):
        mock_falho = MagicMock()
        mock_falho.arbitrar_geracao = AsyncMock(side_effect=RuntimeError("LLM down"))
        with patch("iaglobal.interface.chat_agent._get_critic", return_value=mock_falho):
            colonia = EvoAgentColony()
            await colonia.registrar(evo_agent, "generalista")

            resultado = await interagir_com_colonia(colonia, "qualquer coisa")
            assert resultado.get("erro") == "falha_extracao"

    async def test_execution_metrics_sempre_presentes(self, mock_critic, evo_agent):
        colonia = EvoAgentColony()
        await colonia.registrar(evo_agent, "generalista")

        resultado = await interagir_com_colonia(colonia, "gerar codigo")
        metrics = resultado["execution_metrics"]
        for chave in ("success", "latency", "cost", "model"):
            assert chave in metrics, f"Chave '{chave}' ausente em execution_metrics"


# ═══════════════════════════════════════════════════════════════════
# 4. criar_colonia_evoagents — fábrica
# ═══════════════════════════════════════════════════════════════════


class TestCriarColonia:
    async def test_cria_colonia_com_agentes_reais(self):
        colonia = await criar_colonia_evoagents(
            ["analista", "debugger"], nadph_reserve=0.5
        )
        assert len(colonia._agentes) == 2
        assert "analista" in colonia._agentes
        assert "debugger" in colonia._agentes

        # Agentes devem estar running com DNA válido (16-char marker)
        for esp, reg in colonia._agentes.items():
            assert reg.instancia.running, f"{esp} não está running"
            assert len(reg.instancia.lineage_marker) == 16

        # Cleanup
        for reg in colonia._agentes.values():
            if reg.instancia.running:
                await reg.instancia.apoptose("test_cleanup")
