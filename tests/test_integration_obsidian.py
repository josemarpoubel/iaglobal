"""Teste de integração do ecossistema Obsidian: EvoAgent + OmniMind + Subconsciente + Memória.

Valida o ciclo completo de vida dos agentes com o espírito guia OmniMind,
registro de falhas no subconsciente, consolidação REM, e memórias de curto/longo prazo.

Cobre:
1. EvoAgent → OmniMind (registro, consulta, desregistro)
2. EvoAgent.handle() → OmniMind.consultar() no pipeline
3. EvoAgent.replicate() → OmniMind registra filho
4. OmniMind + SubconsciousAPI (escrita no vault)
5. IAGlobalAgentWrapper + SubconsciousAPI (intuição)
6. REMSleepEngine (consolidação short→long term)
7. ShortTermMemory + LongTermMemory
8. Ciclo completo: erro → capture → short term → REM → long term → intuição
"""

import os
import sys
import json
import time
import asyncio
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def vault_tmp(tmp_path):
    return tmp_path / "vault_obsidian"


@pytest.fixture
def db_tmp(tmp_path):
    return tmp_path / "memory_db"


@pytest.fixture
async def evo_agent():
    from iaglobal.evolution.evo_agent import EvoAgent
    agent = await EvoAgent.genesis(
        task_hint="teste integração obsidian",
        name="evo-obsidian-test",
        nadph_reserve=0.8,
    )
    yield agent
    if agent.running:
        await agent.apoptose("test_cleanup")


# ─────────────────────────────────────────────────────────────────────
# 1. EvoAgent → OmniMind (Ciclo de Vida)
# ─────────────────────────────────────────────────────────────────────

class TestEvoAgentOmniMindLifecycle:
    """Valida que o EvoAgent registra, consulta e desregistra na OmniMind."""

    @pytest.mark.asyncio
    async def test_genesis_registra_na_omnimind(self, evo_agent):
        from iaglobal.obsidian.omnimind import omni_mind
        estado = omni_mind.estado()
        agentes = [a for a in estado["agentes"] if a["nome"] == evo_agent.name]
        assert len(agentes) == 1
        assert agentes[0]["geracao"] == 0
        assert agentes[0]["linhagem"] == evo_agent.lineage_marker[:8]

    @pytest.mark.asyncio
    async def test_handle_consulta_omnimind(self, evo_agent):
        expr = await evo_agent.handle("erro de parsing no modulo de configuracao")
        assert expr is not None
        assert expr.agent_name == evo_agent.name
        assert expr.synthesis is not None

    @pytest.mark.asyncio
    async def test_handle_registra_guidance_no_enriched(self, evo_agent):
        from iaglobal.obsidian.omnimind import omni_mind
        consultas_antes = omni_mind.estado()["total_consultas"]
        await evo_agent.handle("teste de consulta")
        assert omni_mind.estado()["total_consultas"] == consultas_antes + 1

    @pytest.mark.asyncio
    async def test_replicate_registra_filho(self, evo_agent):
        from iaglobal.obsidian.omnimind import omni_mind
        child = await evo_agent.replicate(mutation_hint="especialista-obsidian")
        estado = omni_mind.estado()
        nomes = [a["nome"] for a in estado["agentes"]]
        assert child.name in nomes
        assert child.running
        await child.apoptose("test_cleanup")

    @pytest.mark.asyncio
    async def test_apoptose_desregistra_agente(self, evo_agent):
        from iaglobal.obsidian.omnimind import omni_mind
        name = evo_agent.name
        lineage_id = evo_agent.lineage_id
        await evo_agent.apoptose("test_apoptose")
        assert not evo_agent.running
        estado = omni_mind.estado()
        nomes = [a["nome"] for a in estado["agentes"]]
        assert name not in nomes


# ─────────────────────────────────────────────────────────────────────
# 2. OmniMind — Consulta e Leis Universais
# ─────────────────────────────────────────────────────────────────────

class TestOmniMindConsultas:
    """Valida a lógica de consulta e aplicação de leis."""

    def test_consultar_sem_registro_retorna_orientacao(self):
        from iaglobal.obsidian.omnimind import OmniMind
        mind = OmniMind()
        orientacao = mind.consultar(
            agent_id="nao_existente",
            pergunta="erro de timeout no modulo x",
            contexto={"urgency": "high"},
        )
        assert orientacao.guidance is not None
        assert orientacao.lei_aplicada is not None
        assert "Lei" in orientacao.lei_aplicada
        assert orientacao.timestamp > 0

    def test_consultar_erro_aplica_lei_da_caridade(self):
        from iaglobal.obsidian.omnimind import OmniMind
        mind = OmniMind()
        orientacao = mind.consultar(
            agent_id="test",
            pergunta="falha critica no modulo de importacao",
        )
        assert orientacao.lei_aplicada == "Lei da Caridade"
        assert "contexto" in orientacao.guidance.lower()

    def test_consultar_autofagia_aplica_lei_autofagia(self):
        from iaglobal.obsidian.omnimind import OmniMind
        mind = OmniMind()
        orientacao = mind.consultar(
            agent_id="test",
            pergunta="subproduto toxico acumulado no pipeline",
        )
        assert orientacao.lei_aplicada == "Lei da Autofagia"
        assert "reciclados" in orientacao.guidance.lower()

    def test_sabedoria_coletiva_apos_consultas(self):
        from iaglobal.obsidian.omnimind import OmniMind
        mind = OmniMind()
        mind.consultar("a1", "erro de conexao")
        mind.consultar("a2", "memoria insuficiente")
        sabedoria = mind.sabedoria_coletiva()
        assert "Sabedoria Coletiva" in sabedoria
        assert "Total de consultas" in sabedoria

    def test_estado_retorna_metricas(self):
        from iaglobal.obsidian.omnimind import OmniMind
        mind = OmniMind()
        estado = mind.estado()
        assert "proposito" in estado
        assert "principios" in estado
        assert "agentes_registrados" in estado
        assert "total_consultas" in estado
        assert "memoria_coletiva" in estado

    def test_registrar_agente_incrementa_contagem(self):
        from iaglobal.obsidian.omnimind import OmniMind
        mind = OmniMind()
        before = mind.estado()["agentes_registrados"]
        mind.registrar_agente("id_1", "agente_x", 2, "marker_abc")
        assert mind.estado()["agentes_registrados"] == before + 1
        mind.desregistrar_agente("id_1")
        assert mind.estado()["agentes_registrados"] == before

    def test_consultar_por_ordem_aplica_lei_da_ordem(self):
        from iaglobal.obsidian.omnimind import OmniMind
        mind = OmniMind()
        o = mind.consultar("t", "preciso preservar metadados da funcao")
        assert o.lei_aplicada == "Lei da Ordem"
        assert "metadados" in o.guidance.lower()

    def test_consultar_cooperacao(self):
        from iaglobal.obsidian.omnimind import OmniMind
        mind = OmniMind()
        o = mind.consultar("t", "comunicacao entre agentes via eventos")
        assert o.lei_aplicada == "Lei da Cooperação"
        assert "comunicar" in o.guidance.lower()

    def test_consultar_memoria_imunologica(self):
        from iaglobal.obsidian.omnimind import OmniMind
        mind = OmniMind()
        o = mind.consultar("t", "padrao de erro recorrente identificado")
        assert o.lei_aplicada == "Lei da Memória Imunológica"
        assert "analisado" in o.guidance.lower()


# ─────────────────────────────────────────────────────────────────────
# 3. OmniMind + SubconsciousAPI (Escrita no Vault)
# ─────────────────────────────────────────────────────────────────────

class TestOmniMindSubconscious:
    """Valida integração OmniMind + SubconsciousAPI no vault."""

    def test_omnimind_consulta_e_subconscious_escreve(self, vault_tmp):
        from iaglobal.obsidian.omnimind import OmniMind
        from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
        mind = OmniMind()
        sub = SubconsciousAPI(vault_tmp)
        orientacao = mind.consultar(
            agent_id="agent_1",
            pergunta="erro de importacao",
            contexto={"agente": "test", "tarefa": "importar modulo"},
        )
        caminho = sub.escrever_curto_prazo(
            "consulta_omnimind",
            orientacao.guidance,
            tags=["#omnimind", "#orientacao"],
        )
        assert caminho.exists()
        conteudo = caminho.read_text()
        assert "OmniMind orienta" in conteudo
        assert orientacao.lei_aplicada in conteudo

    def test_erro_capture_integrado_com_omnimind(self, vault_tmp):
        from iaglobal.obsidian.error_capture import ErrorCapture
        from iaglobal.obsidian.omnimind import OmniMind
        mind = OmniMind()
        capture = ErrorCapture(vault_path=vault_tmp, agente="integrated_agent")
        try:
            raise ValueError("falha integrada omnimind")
        except ValueError as e:
            nome = capture.capturar("tarefa_integrada", e, tags=["#omnimind"])
        orientacao = mind.consultar(
            agent_id="integrated_agent",
            pergunta=f"erro capturado: {nome}",
        )
        assert orientacao.lei_aplicada == "Lei da Caridade"
        arquivo_erro = vault_tmp / "02_Short_Term" / f"{nome}.md"
        assert arquivo_erro.exists()


# ─────────────────────────────────────────────────────────────────────
# 4. IAGlobalAgentWrapper + SubconsciousAPI
# ─────────────────────────────────────────────────────────────────────

class TestIAGlobalAgentWrapper:
    """Valida o wrapper que injeta intuição do subconsciente no prompt."""

    def test_preparar_prompt_sem_memoria_retorna_fallback(self, vault_tmp):
        from iaglobal.obsidian.learning_system import IAGlobalAgentWrapper
        wrapper = IAGlobalAgentWrapper(agent_instance=None, vault_path=vault_tmp)
        prompt = wrapper.preparar_prompt_com_intuicao(
            prompt_original_usuario="criar API Flask",
            tags_da_tarefa=["#api", "#flask"],
        )
        assert "CAMADA SUBCONSCIENTE" in prompt
        assert "CAMADA CONSCIENTE" in prompt
        assert "criar API Flask" in prompt

    def test_preparar_prompt_com_memoria_no_vault(self, vault_tmp):
        from iaglobal.obsidian.learning_system import IAGlobalAgentWrapper
        from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
        sub = SubconsciousAPI(vault_tmp)
        sub.escrever_longo_prazo(
            "LicaoFlask",
            "Rotas Flask devem usar Blueprint para organização.",
            tags=["#api", "#flask"],
            fitness=0.9,
        )
        sub.atualizar_mapa_conexoes()
        wrapper = IAGlobalAgentWrapper(agent_instance=None, vault_path=vault_tmp)
        prompt = wrapper.preparar_prompt_com_intuicao(
            prompt_original_usuario="criar API Flask com CRUD",
            tags_da_tarefa=["#api", "#flask"],
        )
        assert "Blueprint" in prompt
        assert "criar API Flask com CRUD" in prompt

    def test_learning_system_processa_requisicao(self, vault_tmp):
        from iaglobal.obsidian.learning_system import LearningSystem
        ls = LearningSystem(vault_path=vault_tmp)
        prompt = ls.processar_requisicao_agente(
            agente_nome="agente_flask",
            tarefa_texto="criar CRUD com Flask",
            tags_contexto=["#api"],
        )
        assert "Tarefa: criar CRUD com Flask" in prompt
        assert "SUBCONSCIENTE" in prompt
        assert "CONSCIENTE" in prompt


# ─────────────────────────────────────────────────────────────────────
# 5. REMSleepEngine — Consolidação
# ─────────────────────────────────────────────────────────────────────

class TestREMSleepIntegration:
    """Valida o ciclo REM com dados reais de curto prazo."""

    def test_consolidate_short_to_long_term(self, vault_tmp):
        from iaglobal.obsidian.consolidation import REMSleepEngine
        from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
        sub = SubconsciousAPI(vault_tmp)
        sub.escrever_curto_prazo(
            "memoria_bruta_1",
            "Erro de conexao com banco de dados resolvido com pool de conexoes.",
            tags=["#erro", "#banco"],
        )
        assert len(list(vault_tmp.joinpath("02_Short_Term").glob("*.md"))) >= 1
        rem = REMSleepEngine(vault_path=vault_tmp)
        resultado = rem.iniciar_fase_rem()
        assert resultado["status"] == "concluido"
        assert resultado["memorias_processadas"] >= 1
        assert resultado["memorias_consolidadas"] >= 1
        short_files = list(vault_tmp.joinpath("02_Short_Term").glob("*.md"))
        assert len(short_files) == 0
        long_files = list(vault_tmp.joinpath("03_Long_Term").glob("*.md"))
        assert len(long_files) >= 1

    def test_consolidate_multiplas_memorias(self, vault_tmp):
        from iaglobal.obsidian.consolidation import REMSleepEngine
        from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
        sub = SubconsciousAPI(vault_tmp)
        for i in range(3):
            sub.escrever_curto_prazo(
                f"log_{i}",
                f"Log de execução número {i} do pipeline.",
                tags=["#log", "#pipeline"],
            )
        rem = REMSleepEngine(vault_path=vault_tmp)
        resultado = rem.iniciar_fase_rem()
        assert resultado["memorias_processadas"] == 3
        assert resultado["memorias_consolidadas"] == 3

    def test_consolidate_vazio_retorna_sem_memorias(self, vault_tmp):
        from iaglobal.obsidian.consolidation import REMSleepEngine
        rem = REMSleepEngine(vault_path=vault_tmp)
        resultado = rem.iniciar_fase_rem()
        assert resultado["status"] == "sem_memorias"

    def test_consolidate_atualiza_mapa_conexoes(self, vault_tmp):
        from iaglobal.obsidian.consolidation import REMSleepEngine
        from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
        sub = SubconsciousAPI(vault_tmp)
        sub.escrever_curto_prazo(
            "dados_importantes",
            "otimizacao de query reduziu latencia em 40%",
            tags=["#otimizacao", "#sql"],
        )
        rem = REMSleepEngine(vault_path=vault_tmp)
        rem.iniciar_fase_rem()
        mapa = vault_tmp / "04_Synapses" / "Mapa_Mental_Subconsciente.md"
        assert mapa.exists()
        conteudo = mapa.read_text()
        assert "dados_importantes" in conteudo


# ─────────────────────────────────────────────────────────────────────
# 6. ShortTermMemory + LongTermMemory
# ─────────────────────────────────────────────────────────────────────

class TestMemoryIntegration:
    """Valida as memórias de curto e longo prazo."""

    def test_short_term_add_and_get(self, db_tmp):
        from iaglobal.memory.term_short import ShortTermMemory
        stm = ShortTermMemory(max_size=10, db_path=db_tmp / "stm.db")
        stm.add("item de teste", {"source": "integration_test"})
        recent = stm.get_recent(5)
        assert "item de teste" in recent

    def test_short_term_search(self, db_tmp):
        from iaglobal.memory.term_short import ShortTermMemory
        stm = ShortTermMemory(max_size=20, db_path=db_tmp / "stm_search.db")
        stm.add("erro de conexao com banco")
        stm.add("otimizacao de query sql")
        results = stm.search("conexao")
        assert len(results) >= 1
        assert "conexao" in results[0]["content"]

    def test_long_term_store_and_retrieve(self, db_tmp):
        from iaglobal.memory.term_long import LongTermMemory
        ltm = LongTermMemory(max_size=100, db_path=db_tmp / "ltm.db")
        ltm.store("pool de conexoes resolve erro de banco", source="test")
        results = ltm.retrieve("erro de banco", top_k=3)
        assert len(results) >= 1
        assert "pool" in results[0]["content"]

    def test_long_term_consolidate_funde_memorias(self, db_tmp):
        from iaglobal.memory.term_long import LongTermMemory
        ltm = LongTermMemory(max_size=100, db_path=db_tmp / "ltm_merge.db")
        ltm.store("usar pool de conexoes para banco de dados", source="test")
        merged = ltm.consolidate("pool de conexoes resolve falhas de banco")
        assert merged is True
        results = ltm.retrieve("banco", top_k=3)
        assert len(results) == 1

    def test_long_term_get_stats(self, db_tmp):
        from iaglobal.memory.term_long import LongTermMemory
        ltm = LongTermMemory(max_size=100, db_path=db_tmp / "ltm_stats.db")
        ltm.store("aprendizado A", source="test")
        ltm.store("aprendizado B", source="test")
        stats = ltm.get_stats()
        assert stats["count"] == 2
        assert stats["avg_importance"] > 0

    def test_short_term_ttl_expira(self, db_tmp):
        from iaglobal.memory.term_short import ShortTermMemory
        stm = ShortTermMemory(max_size=5, ttl_seconds=0, db_path=db_tmp / "stm_ttl.db")
        stm.add("item que expira")
        time.sleep(0.1)
        recent = stm.get_recent(5)
        assert "item que expira" not in recent


# ─────────────────────────────────────────────────────────────────────
# 7. Ciclo Completo: Erro → Capture → REM → Intuição
# ─────────────────────────────────────────────────────────────────────

class TestCicloCompleto:
    """Valida o pipeline completo do ecossistema Obsidian."""

    def test_ciclo_completo_erro_ate_intuicao(self, vault_tmp):
        from iaglobal.obsidian.error_capture import ErrorCapture
        from iaglobal.obsidian.consolidation import REMSleepEngine
        from iaglobal.obsidian.learning_system import IAGlobalAgentWrapper
        from iaglobal.obsidian.omnimind import OmniMind

        mind = OmniMind()
        mind.registrar_agente("ciclo_agent", "agente_ciclo_completo", 1, "marker_ciclo")

        capture = ErrorCapture(vault_path=vault_tmp, agente="ciclo_agent")
        try:
            raise ValueError("falha no modulo de parsing")
        except ValueError as e:
            nome_erro = capture.capturar("parse_config", e, tags=["#parsing"])
        assert nome_erro is not None

        orientacao = mind.consultar(
            agent_id="ciclo_agent",
            pergunta="erro de parsing detectado e capturado",
        )
        assert orientacao.lei_aplicada == "Lei da Caridade"

        rem = REMSleepEngine(vault_path=vault_tmp)
        resultado = rem.iniciar_fase_rem()
        assert resultado["status"] == "concluido"
        assert resultado["memorias_consolidadas"] >= 1

        arquivos_st = list(vault_tmp.joinpath("02_Short_Term").glob("*.md"))
        assert len(arquivos_st) == 0

        wrapper = IAGlobalAgentWrapper(agent_instance=None, vault_path=vault_tmp)
        prompt = wrapper.preparar_prompt_com_intuicao(
            prompt_original_usuario="corrigir erro de parsing no config",
            tags_da_tarefa=["#parsing"],
        )
        assert "CAMADA SUBCONSCIENTE" in prompt
        assert "CAMADA CONSCIENTE" in prompt
        assert "corrigir erro de parsing" in prompt

        mind.desregistrar_agente("ciclo_agent")

    def test_ciclo_com_omnimind_e_subconscious(self, vault_tmp):
        from iaglobal.obsidian.omnimind import OmniMind
        from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

        mind = OmniMind()
        sub = SubconsciousAPI(vault_tmp)

        mind.registrar_agente("full_agent", "agente_completo", 2, "marker_full")
        o = mind.consultar("full_agent", "como lidar com erro de memoria?")

        sub.escrever_curto_prazo(
            "orientacao_recebida",
            o.guidance,
            tags=["#omnimind", "#orientacao"],
        )
        assert (vault_tmp / "02_Short_Term" / "orientacao_recebida.md").exists()

        sub.escrever_instinto(
            "InstintoPreservacao",
            "Nunca ignore um erro de memória. Documente e consulte a OmniMind.",
        )
        assert (vault_tmp / "01_Instincts" / "InstintoPreservacao.md").exists()

        estado = mind.estado()
        assert estado["total_consultas"] >= 1
        assert estado["agentes_registrados"] >= 1

        sabedoria = mind.sabedoria_coletiva()
        assert "erro de memoria" in sabedoria

        mind.desregistrar_agente("full_agent")

    @pytest.mark.asyncio
    async def test_ciclo_evo_agent_completo(self, vault_tmp, db_tmp):
        from iaglobal.evolution.evo_agent import EvoAgent
        from iaglobal.obsidian.omnimind import omni_mind
        from iaglobal.obsidian.error_capture import ErrorCapture
        from iaglobal.obsidian.consolidation import REMSleepEngine
        from iaglobal.memory.term_short import ShortTermMemory
        from iaglobal.memory.term_long import LongTermMemory

        agent = await EvoAgent.genesis(
            task_hint="teste ciclo completo",
            name="evo-full-cycle",
            nadph_reserve=0.9,
        )

        estado_inicial = omni_mind.estado()
        nomes = [a["nome"] for a in estado_inicial["agentes"]]
        assert agent.name in nomes

        expr1 = await agent.handle("analisar falha no modulo de cache")
        assert expr1 is not None
        assert expr1.urgency in ("normal", "high", "critical")

        expr2 = await agent.handle("ERRO CRITICO: memoria insuficiente no pool")
        assert expr2 is not None

        estado_meio = omni_mind.estado()
        assert estado_meio["total_consultas"] >= 2

        capture = ErrorCapture(vault_path=vault_tmp, agente=agent.name)
        try:
            raise RuntimeError("falha simulada no pipeline evolutivo")
        except RuntimeError as e:
            nome_erro = capture.capturar("pipeline_evo", e, tags=["#evo"])
        assert nome_erro is not None

        stm = ShortTermMemory(max_size=10, db_path=db_tmp / "stm_full.db")
        stm.add(expr1.synthesis, {"source": "evo_agent", "type": "expression"})
        stm.add(expr2.synthesis, {"source": "evo_agent", "type": "expression"})
        recent = stm.get_recent(5)
        assert len(recent) >= 2

        ltm = LongTermMemory(max_size=100, db_path=db_tmp / "ltm_full.db")
        ltm.store(expr1.synthesis, source="evo_agent")
        ltm.store(expr2.synthesis, source="evo_agent")
        ltm.store("memoria: falha no modulo de cache identificada", source="evo_agent")
        results = ltm.retrieve("memoria", top_k=3)
        assert len(results) >= 1

        child = await agent.replicate(mutation_hint="filho-evo-obsidian")
        assert child.running

        estado_final = omni_mind.estado()
        nomes_finais = [a["nome"] for a in estado_final["agentes"]]
        assert child.name in nomes_finais

        rem = REMSleepEngine(vault_path=vault_tmp)
        resultado_rem = rem.iniciar_fase_rem()
        assert resultado_rem["status"] in ("concluido", "sem_memorias")

        await child.apoptose("test_cleanup")
        await agent.apoptose("test_cleanup")

        estado_pos = omni_mind.estado()
        nomes_pos = [a["nome"] for a in estado_pos["agentes"]]
        assert agent.name not in nomes_pos
        assert child.name not in nomes_pos
