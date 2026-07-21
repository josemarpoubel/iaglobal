# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes E2E da cadeia crítica: PM → ToolLibrary → Bandit → select_model.

Valida que as correções de Julho 2026 impedem regressão do cenário:
prompt = "crie um app de vendas para um restaurante com tema escuro..."
→ PM extrai requisitos, ToolLibrary escolhe tool dev, select_model não quebra.
"""

import pytest
from typing import Dict, Any
from unittest.mock import MagicMock


# ============================================================
# HELPERS
# ============================================================

_PROMPT_ORIGINAL = (
    "crie um app de vendas para um restaurante "
    "com tema escuro elegante e responsivo "
    "com controle de estoque "
    "controle de vendas "
    "controle de funcionarios"
)


def _pm_agent():
    from iaglobal.agents.pm_agent import PMAgent

    return PMAgent()


def _register_tools(tl):
    """Registra tools de exemplo para teste de matching."""
    tl.register(
        "generate_dark_pdf",
        lambda x: x,
        tags=["pdf", "dark", "escuro", "elegante", "documento", "gerar pdf"],
        description="Gera PDF com tema escuro e elegante para documentos",
    )
    tl.register(
        "generate_web_app",
        lambda x: x,
        tags=["html", "app", "web", "frontend", "aplicacao", "site", "responsivo"],
        description="Gera aplicacao web responsiva completa com HTML e CSS",
    )
    tl.register(
        "generate_backend_api",
        lambda x: x,
        tags=["api", "backend", "python", "server", "sql", "rest"],
        description="Gera backend REST API com banco de dados",
    )
    return tl


# ============================================================
# TEST 1 — PM Agent extrai requisitos do prompt realista
# ============================================================


def test_pm_agent_extrai_requisitos_do_prompt_realista():
    """
    Garante que o PM Agent extrai "estoque", "vendas" e "funcionarios"
    do prompt que causou falha em produção.

    Bug corrigido: context_search.finditer() usava prompt cru (com acentos).
    Bug corrigido: patterns não incluíam verbos comuns ("criar", "controlar").
    Bug corrigido: regex não aceitava conjugações ("crie" → "criar").
    """
    agent = _pm_agent()
    result = agent.extract_requirements(
        _PROMPT_ORIGINAL, {"intents_detected": ["web_app"]}
    )

    assert len(result["functional"]) >= 3, (
        f"Deveria extrair ao menos 3 requisitos, obteve {len(result['functional'])}: "
        f"{result['functional']}"
    )

    reqs_text = "\n".join(result["functional"]).lower()
    assert "estoque" in reqs_text, (
        f"'estoque' não encontrado nos requisitos extraídos: {result['functional']}"
    )
    assert "vendas" in reqs_text, (
        f"'vendas' não encontrado nos requisitos extraídos: {result['functional']}"
    )
    assert "funcionarios" in reqs_text, (
        f"'funcionarios' não encontrado nos requisitos extraídos: {result['functional']}"
    )

    assert result["priority"] == "high", (
        f"Prioridade deveria ser high (5 func), obteve: {result['priority']}"
    )


# ============================================================
# TEST 2 — PM Agent retorna 0 requisitos com prompt vazio
# ============================================================


def test_pm_agent_requisitos_com_prompt_vazio():
    agent = _pm_agent()
    result = agent.extract_requirements("")
    assert len(result["functional"]) == 0
    assert len(result["non_functional"]) == 0
    assert result["priority"] == "low"


# ============================================================
# TEST 3 — PM Agent com prompt que tinha acentos antes da normalização
# ============================================================


def test_pm_agent_lida_com_acentos():
    """
    Verifica que acentos não quebram extração.
    Bug corrigido: context_search.finditer(prompt) → finditer(clean_prompt).
    """
    agent = _pm_agent()
    prompt_com_acento = (
        "criar um sistema de gestão de funcionários "
        "com cadastro de usuários e controle de vendas"
    )
    result = agent.extract_requirements(prompt_com_acento)
    reqs_text = "\n".join(result["functional"]).lower()
    assert len(result["functional"]) >= 2, (
        f"Deveria extrair ao menos 2 requisitos, obteve {len(result['functional'])}: "
        f"{result['functional']}"
    )


# ============================================================
# TEST 4 — ToolLibrary rejeita generate_dark_pdf para task dev
# ============================================================


def test_tool_library_rejeita_pdf_para_task_dev():
    """
    Garante que a ToolLibrary escolhe generate_web_app em vez de
    generate_dark_pdf para o prompt de falha.

    Bug corrigido: penalidade de domínio (-0.35) para task dev vs tool não-dev.
    """
    import tempfile, importlib

    tlib_mod = importlib.import_module("iaglobal.tools.tool_library")
    db_path = tempfile.mktemp(suffix=".pkl")
    old = tlib_mod._TOOLS_DB
    tlib_mod._TOOLS_DB = db_path
    try:
        tl = tlib_mod.ToolLibrary()
        _register_tools(tl)
        tool, score = tl.match(_PROMPT_ORIGINAL)
        assert tool is not None, "Nenhuma tool foi selecionada"
        assert tool.name != "generate_dark_pdf", (
            f"generate_dark_pdf foi selecionado (score={score:.3f}) — "
            f"penalidade de domínio não funcionou"
        )
        assert "web" in tool.name.lower() or "api" in tool.name.lower(), (
            f"Tool selecionada '{tool.name}' não é uma tool de desenvolvimento"
        )
        assert score >= 0.5, f"Score da tool dev ({score:.3f}) abaixo do limiar 0.5"
    finally:
        tlib_mod._TOOLS_DB = old


# ============================================================
# TEST 5 — ToolLibrary ainda aceita PDF quando task é de documento
# ============================================================


def test_tool_library_aceita_pdf_para_task_documento():
    """
    A penalidade de domínio NÃO deve ser aplicada quando a task é
    genuinamente de geração de documento.
    """
    import tempfile, importlib

    tlib_mod = importlib.import_module("iaglobal.tools.tool_library")
    db_path = tempfile.mktemp(suffix=".pkl")
    old = tlib_mod._TOOLS_DB
    tlib_mod._TOOLS_DB = db_path
    try:
        tl = tlib_mod.ToolLibrary()
        _register_tools(tl)
        pdf_prompt = "gere um relatorio financeiro em pdf com tema escuro elegante"
        tool, score = tl.match(pdf_prompt)
        assert tool is not None
        assert "pdf" in tool.name.lower(), (
            f"Para prompt de documento, esperava PDF, obteve: {tool.name}"
        )
    finally:
        tlib_mod._TOOLS_DB = old


# ============================================================
# TEST 6 — BanditPolicy.select_model com kwargs corretos
# ============================================================


def test_bandit_select_model_kwargs_corretos():
    """
    Garante que select_model() aceita node_id e task_type como kwargs.
    Bug corrigido: pipeline/engine.py passava node= e strategy=.
    """
    from iaglobal.graphs.bandit import BanditPolicy

    bp = BanditPolicy()

    candidates = ["ollama/qwen2.5:0.5b", "groq/llama3-70b-8192"]
    chosen = bp.select_model(
        node_id="cognitive_dag_root",
        task_type="dev_fast",
        candidates=candidates,
    )
    assert chosen is not None
    assert chosen in candidates, (
        f"Modelo escolhido '{chosen}' não está entre candidatos {candidates}"
    )


# ============================================================
# TEST 7 — select_model com kwargs errados levanta TypeError
# ============================================================


def test_bandit_select_model_kwargs_errados_levanta_type_error():
    """
    Verifica que a assinatura antiga (node=, strategy=) levanta TypeError,
    prevenindo regressão.
    """
    from iaglobal.graphs.bandit import BanditPolicy

    bp = BanditPolicy()
    candidates = ["ollama/qwen2.5:0.5b"]

    with pytest.raises(TypeError):
        bp.select_model(
            node="cognitive_dag_root",
            strategy="dev_fast",
            candidates=candidates,
        )


# ============================================================
# TEST 8 — PipelineEngine chama select_model com kwargs corretos
# ============================================================


@pytest.mark.asyncio
async def test_pipeline_engine_chama_select_model_corretamente(monkeypatch):
    """
    Verifica que PipelineEngine executa select_model sem erro.
    """
    selected = {}

    class FakeBandit:
        def select_model(self, node_id, task_type, candidates, context=None):
            selected["node_id"] = node_id
            selected["task_type"] = task_type
            return candidates[0] if candidates else None

    class FakeOrchestrator:
        bandit = FakeBandit()

    from iaglobal.pipeline.engine import PipelineEngine

    engine = PipelineEngine(orchestrator=FakeOrchestrator())

    monkeypatch.setattr(
        "iaglobal.providers.provider_router.CREDIT_CANDIDATES",
        lambda: [("ollama", "ollama/qwen2.5:0.5b")],
    )

    result = await engine.async_execute(
        prompt=_PROMPT_ORIGINAL,
        force=True,
    )

    assert selected.get("node_id") == "cognitive_dag_root", (
        f"select_model recebeu node_id={selected.get('node_id')}, esperava 'cognitive_dag_root'"
    )
    assert selected.get("task_type") == "dev_fast", (
        f"select_model recebeu task_type={selected.get('task_type')}, esperava 'dev_fast'"
    )


# ============================================================
# TEST 9 — Cadeia completa: PM → ToolLibrary → classificação
# ============================================================

# ============================================================
# TEST 9 — MissionAnalyzer classifica domínio e entidades
# ============================================================


def test_mission_analyzer_classifica_prompt_realista():
    """
    Mission Cortex é executado antes de qualquer nó do grafo.
    Deve extrair domínio, entidades e restrições sem LLM.
    """
    from iaglobal.pipeline.mission import MissionAnalyzer

    analyzer = MissionAnalyzer()
    m = analyzer.analyze(_PROMPT_ORIGINAL)

    assert m.domain == "restaurant", (
        f"Deveria detectar domínio 'restaurant', obteve '{m.domain}'"
    )
    assert m.project_type == "web_application", (
        f"Deveria detectar 'web_application', obteve '{m.project_type}'"
    )
    assert "estoque" in m.entities, (
        f"'estoque' não encontrado em entities: {m.entities}"
    )
    assert "vendas" in m.entities, f"'vendas' não encontrado em entities: {m.entities}"
    assert "funcionarios" in m.entities, (
        f"'funcionarios' não encontrado em entities: {m.entities}"
    )
    assert "tema escuro" in m.constraints, (
        f"'tema escuro' não encontrado em constraints: {m.constraints}"
    )
    assert "design responsivo" in m.constraints, (
        f"'design responsivo' não encontrado em constraints: {m.constraints}"
    )
    assert m.confidence >= 0.8, (
        f"Confiança ({m.confidence}) abaixo de 0.8 para prompt com múltiplos matches"
    )


def test_mission_analyzer_nao_confunde_pagamento_com_game():
    """
    Word boundary matching: "game" dentro de "pagamento" não deve
    classificar projeto como jogo.
    """
    from iaglobal.pipeline.mission import MissionAnalyzer

    m = MissionAnalyzer().analyze(
        "construa um ecommerce com carrinho de compras e pagamento"
    )
    assert m.domain == "ecommerce", f"Deveria ser ecommerce, obteve '{m.domain}'"
    assert m.project_type != "game", (
        f"'game' dentro de 'pagamento' causou falso positivo"
    )


def test_mission_analyzer_classifica_api():
    from iaglobal.pipeline.mission import MissionAnalyzer

    m = MissionAnalyzer().analyze("crie uma api rest em python para gerenciar produtos")
    assert m.domain == "api"
    assert m.project_type == "api_service"


def test_mission_analyzer_classifica_jogo():
    from iaglobal.pipeline.mission import MissionAnalyzer

    m = MissionAnalyzer().analyze("desenvolva um jogo de plataforma em javascript")
    assert m.domain == "game"
    assert m.project_type == "game"


def test_mission_analyzer_classifica_documento():
    from iaglobal.pipeline.mission import MissionAnalyzer

    m = MissionAnalyzer().analyze("gere um relatorio financeiro em pdf com graficos")
    assert m.project_type == "document"


def test_cadeia_completa_classificacao():
    """
    Testa a cadeia de classificação inteira sem LLM:
    PM extrai requisitos → ToolLibrary rejeita PDF → resultado correto.
    """
    # 1. PM
    agent = _pm_agent()
    pm_result = agent.extract_requirements(
        _PROMPT_ORIGINAL, {"intents_detected": ["web_app"]}
    )
    reqs_text = "\n".join(pm_result["functional"]).lower()
    assert "estoque" in reqs_text
    assert "vendas" in reqs_text
    assert "funcionarios" in reqs_text

    # 2. ToolLibrary
    import tempfile, importlib

    tlib_mod = importlib.import_module("iaglobal.tools.tool_library")
    db_path = tempfile.mktemp(suffix=".pkl")
    old = tlib_mod._TOOLS_DB
    tlib_mod._TOOLS_DB = db_path
    try:
        tl = tlib_mod.ToolLibrary()
        _register_tools(tl)

        tool, score = tl.match(_PROMPT_ORIGINAL)
        assert tool is not None
        assert tool.name != "generate_dark_pdf", (
            f"PM extraiu {len(pm_result['functional'])} requisitos, "
            f"mas ToolLibrary escolheu '{tool.name}' (score={score:.3f})"
        )
        assert "web" in tool.name.lower()

        # 3. Priority deve ser high (>=5 funcional)
        assert pm_result["priority"] == "high"

        # 4. NF deve incluir responsivo
        assert any("responsivo" in nf.lower() for nf in pm_result["non_functional"]), (
            f"'responsivo' não encontrado em non_functional: {pm_result['non_functional']}"
        )
    finally:
        tlib_mod._TOOLS_DB = old
