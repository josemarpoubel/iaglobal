# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do roteador de modelos (Fase C do ROADMAP.md).

Cobertura:
  - Tarefa crítica → nuvem
  - Tarefa de análise com IVM baixo → nuvem (REASONING_KEYWORDS)
  - Tarefa de análise com IVM alto → local
  - Tarefa genérica → local (ATP preservation)
"""

import pytest

from iaglobal.evolution.skills.native.skill_model_router import (
    run_model_router,
    CRITICAL_KEYWORDS,
    REASONING_KEYWORDS,
    IVM_REASONING_THRESHOLD,
)


@pytest.mark.asyncio
async def test_critical_task_elevates_to_cloud():
    """Tarefa com keyword crítica vai para nuvem independente de IVM."""
    result = await run_model_router(
        {"task": "detect mhc vulnerability in code", "ivm": 0.9}
    )
    assert result["model_decision"]["reason"] == "critical_task_elevation"
    assert result["model_decision"]["provider"] == "groq"


@pytest.mark.asyncio
async def test_analysis_low_ivm_elevates_to_cloud():
    """Tarefa de análise com IVM baixo vai para nuvem."""
    result = await run_model_router(
        {"task": "faça uma analise tecnica do sistema", "ivm": 0.3}
    )
    assert result["model_decision"]["reason"] == "reasoning_low_ivm_elevation"
    assert result["model_decision"]["provider"] == "groq"


@pytest.mark.asyncio
async def test_analysis_high_ivm_enters_evaluation():
    """Tarefa de análise com IVM alto entra na avaliação de score (não cai em ATP preservation)."""
    result = await run_model_router(
        {"task": "faça uma analise tecnica do sistema", "ivm": 0.9}
    )
    # Entra na avaliação de score, não no atalho ATP
    assert result["model_decision"]["reason"] in (
        "reasoning_high_ivm",
        "local_sufficient",
    )
    # score_cloud foi computado (não é 0.0 como no ATP preservation)
    assert result["model_decision"]["score_cloud"] > 0.0


@pytest.mark.asyncio
async def test_architecture_low_ivm_elevates():
    """Tarefa de arquitetura com IVM baixo vai para nuvem."""
    result = await run_model_router(
        {"task": "revise a arquitetura do sistema", "ivm": 0.4}
    )
    assert result["model_decision"]["reason"] == "reasoning_low_ivm_elevation"


@pytest.mark.asyncio
async def test_refactoring_low_ivm_elevates():
    """Tarefa de refatoração com IVM baixo vai para nuvem."""
    result = await run_model_router(
        {"task": "refatore o codigo do modulo X", "ivm": 0.2}
    )
    assert result["model_decision"]["reason"] == "reasoning_low_ivm_elevation"


@pytest.mark.asyncio
async def test_generic_task_stays_local():
    """Tarefa genérica sem keywords fica local (ATP preservation)."""
    result = await run_model_router({"task": "crie uma API Flask", "ivm": 0.5})
    assert result["model_decision"]["reason"] == "default_local_atp_preservation"
    assert result["model_decision"]["provider"] == "ollama"


@pytest.mark.asyncio
async def test_threats_detected_flag_elevates():
    """Flag de ameaça detectada eleva para nuvem."""
    result = await run_model_router(
        {"task": "codigo normal", "ivm": 0.9, "threats_detected": True}
    )
    assert result["model_decision"]["reason"] == "critical_flag_elevation"
    assert result["model_decision"]["provider"] == "groq"


class TestKeywords:
    def test_critical_keywords_present(self):
        assert "mhc" in CRITICAL_KEYWORDS
        assert "security" in CRITICAL_KEYWORDS
        assert "pathogen" in CRITICAL_KEYWORDS

    def test_reasoning_keywords_present(self):
        assert "analise" in REASONING_KEYWORDS
        assert "arquitetura" in REASONING_KEYWORDS
        assert "refator" in REASONING_KEYWORDS
        assert "design" in REASONING_KEYWORDS
        assert "diagnóstico" in REASONING_KEYWORDS

    def test_ivm_threshold_reasonable(self):
        assert 0.0 < IVM_REASONING_THRESHOLD < 1.0
