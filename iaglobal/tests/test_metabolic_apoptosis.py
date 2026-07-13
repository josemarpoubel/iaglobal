# -*- coding: utf-8 -*-
"""Teste de Apoptose de Memoria com Critic.

Valida ciclo completo de evolucao e purificacao de skills.
"""

import asyncio
import time
import pytest

from iaglobal.evolution.evo_agent import EvoAgent
from iaglobal.evolution.memory_apoptosis import MemoryApoptosis, ApoptosisCriteria
from iaglobal.metabolism.homocysteine_pool import homocysteine_pool, CandidateSkill
from iaglobal.evolution.skills.native.skill import Skill


@pytest.fixture
def clean_pool():
    """Limpa homocysteine_pool antes e depois do teste."""
    backup = list(homocysteine_pool.candidates)
    homocysteine_pool.candidates.clear()
    yield
    homocysteine_pool.candidates.clear()
    homocysteine_pool.candidates.extend(backup)


def create_test_skill(
    name: str,
    description: str = "Test skill",
    code: str = "print('hello')",
    age_days: float = 1.0,
    reuse_count: int = 1,
    success_rate: float = 0.7,
    critic_score: float = 0.7,
):
    """Cria skill de teste com parametros customizados."""
    created_at = time.time() - (age_days * 86400)

    skill = CandidateSkill(
        skill=Skill(
            name=name,
            description=description,
            inputs=["task"],
            outputs=["result"],
            version="1.0.0",
        ),
        generation=0,
        score=critic_score,
        source_gap="test",
    )
    skill.created_at = created_at
    skill.metadata = {
        "reuse_count": reuse_count,
        "success_rate": success_rate,
        "last_used": time.time() - 3600,
        "avg_ivm": 0.5,
        "critic_score": critic_score,
    }
    return skill


@pytest.mark.asyncio
async def test_healthy_skill_survives(clean_pool):
    """Skill saudavel (critic alto, muito reuso) deve sobreviver."""
    skill_good = create_test_skill(
        name="skill_good_oauth",
        code="async def oauth_pkce(): ...",
        age_days=2.0,
        reuse_count=15,
        success_rate=0.92,
        critic_score=0.88,
    )
    homocysteine_pool.add(skill_good)

    apoptosis = MemoryApoptosis(
        criteria=ApoptosisCriteria(
            max_age_days=7.0,
            min_reuse_count=3,
            min_success_rate=0.5,
            min_critic_score=0.4,
        )
    )
    result = await apoptosis.evaluate_and_prune()

    assert result["evaluated"] == 1
    assert result["pruned"] == 0
    assert result["saved"] == 1

    remaining = homocysteine_pool.get_pending()
    assert any(s.skill.name == "skill_good_oauth" for s in remaining)


@pytest.mark.asyncio
async def test_pathogenic_skill_removed(clean_pool):
    """Skill patogenica (critic baixo) deve ser removida."""
    skill_bad = create_test_skill(
        name="skill_bad_hardcoded_creds",
        code='PASSWORD = "admin123"',
        age_days=1.0,
        reuse_count=5,
        success_rate=0.60,
        critic_score=0.25,
    )
    homocysteine_pool.add(skill_bad)

    apoptosis = MemoryApoptosis()
    result = await apoptosis.evaluate_and_prune()

    assert result["evaluated"] == 1
    assert result["pruned"] == 1
    assert result["saved"] == 0

    remaining = homocysteine_pool.get_pending()
    assert not any(s.skill.name == "skill_bad_hardcoded_creds" for s in remaining)
    assert any(
        s["name"] == "skill_bad_hardcoded_creds" and s.get("is_pathogenic")
        for s in result["apoptosed_skills"]
    )


@pytest.mark.asyncio
async def test_zombie_skill_removed(clean_pool):
    """Skill zumbi (antiga + sem uso) deve ser removida."""
    skill_old = create_test_skill(
        name="skill_old_unused",
        code="legacy_code()",
        age_days=15.0,
        reuse_count=0,
        success_rate=0.0,
        critic_score=0.50,
    )
    homocysteine_pool.add(skill_old)

    apoptosis = MemoryApoptosis()
    result = await apoptosis.evaluate_and_prune()

    assert result["evaluated"] == 1
    assert result["pruned"] == 1
    assert result["saved"] == 0

    assert any(
        s["name"] == "skill_old_unused" and s.get("is_zombie")
        for s in result["apoptosed_skills"]
    )


@pytest.mark.asyncio
async def test_mixed_skills_apoptosis(clean_pool):
    """Teste com multiplas skills (boas, ruins, zumbis)."""
    skills = [
        create_test_skill("good_1", critic_score=0.85, reuse_count=10, age_days=2),
        create_test_skill("good_2", critic_score=0.78, reuse_count=5, age_days=3),
        create_test_skill(
            "bad_pathogenic", critic_score=0.25, reuse_count=3, age_days=1
        ),
        create_test_skill("bad_zombie", critic_score=0.50, reuse_count=0, age_days=20),
    ]
    for skill in skills:
        homocysteine_pool.add(skill)

    apoptosis = MemoryApoptosis()
    result = await apoptosis.evaluate_and_prune()

    assert result["evaluated"] == 4
    assert result["pruned"] == 2
    assert result["saved"] == 2
    assert result["health_improvement"] > 0

    apoptosed = result["apoptosed_skills"]
    assert any(s.get("is_pathogenic") for s in apoptosed)
    assert any(s.get("is_zombie") for s in apoptosed)

    remaining = homocysteine_pool.get_pending()
    assert any(s.skill.name == "good_1" for s in remaining)
    assert any(s.skill.name == "good_2" for s in remaining)


@pytest.mark.asyncio
async def test_evoagent_creates_skill_from_web(clean_pool):
    """EvoAgent cria skill a partir de busca web."""
    agent = await EvoAgent.genesis(
        task_hint="metabolic_test", name="evo-metabolic-tester"
    )
    try:
        result = await agent.handle("crie API Flask com autenticacao JWT 2026")
        assert result is not None
        assert result.cycles_activated.get("metilacao") == True

        skills = homocysteine_pool.get_pending()
        assert len(skills) >= 1
    finally:
        await agent.apoptose("test")


@pytest.mark.asyncio
async def test_evoagent_run_memory_apoptosis(clean_pool):
    """EvoAgent executa apoptose de memoria."""
    agent = await EvoAgent.genesis(
        task_hint="apoptosis_test", name="evo-apoptosis-tester"
    )
    try:
        skill_good = create_test_skill("good", critic_score=0.85)
        skill_bad = create_test_skill("bad", critic_score=0.25)
        homocysteine_pool.add(skill_good)
        homocysteine_pool.add(skill_bad)

        result = await agent.run_memory_apoptosis()

        assert result["evaluated"] >= 2
        assert result["pruned"] >= 1
        assert result["health_improvement"] > 0
    finally:
        await agent.apoptose("test")


@pytest.mark.asyncio
async def test_metabolic_apoptosis_full_integration(clean_pool):
    """Teste de integracao completo."""
    agent = await EvoAgent.genesis(
        task_hint="integration_test", name="evo-integration-tester"
    )
    try:
        result1 = await agent.handle("Como implementar OAuth 2.1 PKCE em Next.js 2026?")
        assert result1 is not None

        skill_pathogenic = create_test_skill(
            "pathogenic_test", code="PASSWORD = '123456'", critic_score=0.15
        )
        homocysteine_pool.add(skill_pathogenic)

        skill_zombie = create_test_skill("zombie_test", age_days=25, reuse_count=0)
        homocysteine_pool.add(skill_zombie)

        apoptosis_result = await agent.run_memory_apoptosis()

        assert apoptosis_result["evaluated"] >= 2
        assert apoptosis_result["pruned"] >= 2
        assert any(s.get("is_pathogenic") for s in apoptosis_result["apoptosed_skills"])
        assert any(s.get("is_zombie") for s in apoptosis_result["apoptosed_skills"])
    finally:
        await agent.apoptose("test")
