#!/usr/bin/env python3
"""
Teste de Apoptose de Memória — Valida filtro de qualidade metabólica.

Cria skills artificiais (algumas boas, outras ruins) e executa apoptose
para ver quais são removidas.
"""

import asyncio
import time
from pathlib import Path

from iaglobal.evolution.memory_apoptosis import (
    MemoryApoptosis,
    ApoptosisCriteria,
    MetabolicHealth
)
from iaglobal.evolution.skills.skill import Skill
from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry
from iaglobal.metabolism.homocysteine_pool import CandidateSkill


async def test_memory_apoptosis():
    print('🧬 Testing Memory Apoptosis — Metabolic Quality Filter...')
    print('=' * 70)
    
    # Configura critérios de apoptose
    criteria = ApoptosisCriteria(
        max_age_days=0.001,    # ~1.4 minutos para teste rápido
        min_reuse_count=2,     # Mínimo 2 reusos
        min_success_rate=0.5,  # 50% sucesso mínimo
        max_idle_cycles=2      # 2 ciclos ociosa
    )
    
    apoptosis = MemoryApoptosis(criteria=criteria)
    
    # Usa HomocysteinePool para armazenar skills
    from iaglobal.metabolism.homocysteine_pool import homocysteine_pool
    
    print('\n1️⃣  Criando skills artificiais (boas e ruins)...')
    
    # Skill 1: Boa (recente, muito reuso, alto sucesso)
    skill_good = CandidateSkill(
        skill=Skill(
            name="skill_good_oauth",
            description="OAuth implementation — muito usada",
            inputs=["task"],
            outputs=["code"],
            version="1.0.0"
        ),
        generation=0,
        score=0.85,
        source_gap="OAuth 2.1 PKCE"
    )
    skill_good.created_at = time.time() - 3600  # 1 hora atrás
    skill_good.metadata = {
        "reuse_count": 15,      # Muito reuso
        "success_rate": 0.92,   # Alto sucesso
        "last_used": time.time() - 60,  # Usada há 1 min
        "avg_ivm": 0.78
    }
    homocysteine_pool.add(skill_good)
    print('   ✅ skill_good_oauth criada (boa)')
    
    # Skill 2: Ruim (antiga, sem reuso, baixo sucesso)
    skill_bad = CandidateSkill(
        skill=Skill(
            name="skill_bad_deprecated",
            description="Old pattern — não usada",
            inputs=["task"],
            outputs=["code"],
            version="1.0.0"
        ),
        generation=0,
        score=0.30,
        source_gap="Deprecated API"
    )
    skill_bad.created_at = time.time() - 86400 * 10  # 10 dias atrás
    skill_bad.metadata = {
        "reuse_count": 0,       # Zero reuso
        "success_rate": 0.20,   # Baixo sucesso
        "last_used": time.time() - 86400 * 5,  # 5 dias atrás
        "avg_ivm": 0.25
    }
    homocysteine_pool.add(skill_bad)
    print('   ❌ skill_bad_deprecated criada (ruim)')
    
    # Skill 3: Média (pouco reuso, sucesso ok)
    skill_medium = CandidateSkill(
        skill=Skill(
            name="skill_medium_react",
            description="React pattern — uso moderado",
            inputs=["task"],
            outputs=["component"],
            version="1.0.0"
        ),
        generation=0,
        score=0.60,
        source_gap="React dark mode"
    )
    skill_medium.created_at = time.time() - 86400 * 2  # 2 dias atrás
    skill_medium.metadata = {
        "reuse_count": 2,       # Pouco reuso
        "success_rate": 0.65,   # Sucesso razoável
        "last_used": time.time() - 3600 * 5,  # 5 horas atrás
        "avg_ivm": 0.55
    }
    homocysteine_pool.add(skill_medium)
    print('   ⚠️  skill_medium_react criada (média)')
    
    # Skill 4: Antiga sem uso (candidata a apoptose)
    skill_old = CandidateSkill(
        skill=Skill(
            name="skill_old_unused",
            description="Very old pattern — abandonada",
            inputs=["task"],
            outputs=["result"],
            version="1.0.0"
        ),
        generation=0,
        score=0.40,
        source_gap="Legacy code"
    )
    skill_old.created_at = time.time() - 86400 * 15  # 15 dias atrás
    skill_old.metadata = {
        "reuse_count": 1,       # Apenas 1 reuso
        "success_rate": 0.40,   # Sucesso baixo
        "last_used": time.time() - 86400 * 10,  # 10 dias atrás
        "avg_ivm": 0.35
    }
    homocysteine_pool.add(skill_old)
    print('   ❌ skill_old_unused criada (antiga sem uso)')
    
    print(f'\n   Total skills criadas: 4')
    
    # Lista skills antes da apoptose
    print('\n2️⃣  Skills antes da apoptose:')
    skills_before = homocysteine_pool.get_pending()
    for skill in skills_before:
        metadata = getattr(skill, 'metadata', {})
        print(f'   - {skill.skill.name}: reuses={metadata.get("reuse_count", 0)}, '
              f'success={metadata.get("success_rate", 0):.2f}')
    
    # Executa apoptose
    print('\n3️⃣  Executando apoptose de memória...')
    result = await apoptosis.evaluate_and_prune()
    
    print(f'\n4️⃣  Resultados da apoptose:')
    print(f'   ✅ Evaluated: {result["evaluated"]}')
    print(f'   ❌ Pruned: {result["pruned"]}')
    print(f'   💾 Saved: {result["saved"]}')
    print(f'   📈 Health improvement: {result["health_improvement"]:.1f}%')
    
    if result["apoptosed_skills"]:
        print(f'\n   Skills removidas:')
        for skill in result["apoptosed_skills"]:
            print(f'      - {skill["name"]}: {skill["reason"]}')
    
    # Lista skills depois da apoptose
    print('\n5️⃣  Skills depois da apoptose:')
    skills_after = homocysteine_pool.get_pending()
    for skill in skills_after:
        metadata = getattr(skill, 'metadata', {})
        print(f'   - {skill.skill.name}: reuses={metadata.get("reuse_count", 0)}, '
              f'success={metadata.get("success_rate", 0):.2f}')
    
    # Valida resultados
    print('\n6️⃣  Validação:')
    expected_pruned = 2  # skill_bad_deprecated e skill_old_unused
    if result["pruned"] == expected_pruned:
        print(f'   ✅ Correto: {expected_pruned} skills ruins removidas')
    else:
        print(f'   ⚠️  Esperado {expected_pruned} removidas, mas {result["pruned"]} foram removidas')
    
    # Verifica se skill_good foi mantida
    good_survived = any(s.skill.name == "skill_good_oauth" for s in skills_after)
    if good_survived:
        print('   ✅ skill_good_oauth mantida (como esperado)')
    else:
        print('   ❌ skill_good_oauth removida (erro!)')
    
    print('\n✅ Memory Apoptosis Test Completed!')
    print('=' * 70)
    
    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    asyncio.run(test_memory_apoptosis())