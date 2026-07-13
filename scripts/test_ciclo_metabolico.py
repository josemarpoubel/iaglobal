"""
test_ciclo_metabolico.py — Validação do ciclo metabólico completo.
"""
import time
import asyncio
from iaglobal.evolution.skills.native.skill import Skill
from iaglobal.metabolism.homocysteine_pool import homocysteine_pool, CandidateSkill
from iaglobal.obsidian.epigenetic_registry import epigenetic_registry
from iaglobal.immunity.vaccine_ledger import vaccine_ledger


async def main():
    print("🧬 Ciclo Metabólico — Validação\n")

    # ── 1. Criar skills e adicionar ao pool ──
    print("1️⃣  Criando skills no HomocysteinePool...")
    skills_data = [
        ("oauth_pkce_nextjs", "Implementa OAuth 2.1 com PKCE code challenge S256 em Next.js App Router com middleware de sessão", 0.85,
         "Gap identificado: falta implementação de PKCE com code challenge S256 para proteger fluxo OAuth público contra ataques de interceptação"),
        ("middleware_auth", "Autenticação stateless via middleware FastAPI com JWT assinado e verificação de claims de usuário e permissões", 0.72,
         "Gap identificado: middleware de autenticação atual não suporta JWT com verificação de claims e renovação silenciosa de tokens expirados"),
        ("pkce_flow", "Geração de code_challenge SHA256 e code_verifier aleatório com 128 bytes de entropia para fluxo OAuth2 público seguro", 0.65,
         "Gap identificado: fluxo atual não implementa PKCE; code_verifier não é gerado com entropia suficiente conforme RFC 7636"),
    ]
    for nome, desc, score, gap in skills_data:
        skill = Skill(name=nome, version="1.0.0", description=desc)
        candidate = CandidateSkill(skill=skill, score=score, source_gap=gap, created_at=time.time())
        homocysteine_pool.add(candidate)
    print(f"   Skills no pool: {homocysteine_pool.count()}\n")

    # ── 2. Promover skills do pool (route_to_production) ──
    print("2️⃣  Promovendo skills com score >= 0.7...")
    promovidas = []
    for cand in homocysteine_pool.get_candidates_for_methylation():
        if cand.score >= 0.7:
            if homocysteine_pool.route_to_production(cand):
                promovidas.append(cand.skill.name)
    print(f"   Skills promovidas: {len(promovidas)} → {promovidas}\n")

    # ── 3. EpigeneticRegistry — registrar sucesso das skills promovidas ──
    print("3️⃣  Registrando marcas epigenéticas de sucesso...")
    for nome in promovidas:
        eid = await epigenetic_registry.record_success(
            agent_id="evo_demo",
            task_hash=f"skill_{nome}",
            ivm_score=0.85,
            reward_value=1.0,
        )
        print(f"   ✓ {nome} → epigenetic_id={eid[:16]}...")
    profile = await epigenetic_registry.get_agent_epigenetic_profile("evo_demo")
    print(f"   Perfil: {profile['total_markers']} marcadores, "
          f"{profile['successes']} sucessos, IVM médio={profile['avg_ivm']:.2f}\n")

    # ── 4. VaccineLedger — registrar linhagem e patterns ──
    print("4️⃣  Registrando vacinas no VaccineLedger...")
    demo_marker = "cc7017b56557586095e8dc6dae27b3e6"
    vaccine_ledger.registrar_linhagem(demo_marker)

    # Simular um EvoAgent para registrar falhas/vacinas
    class EvoMock:
        name = "evo_demo"
        lineage_marker = demo_marker
        _failure_patterns = []

    evo = EvoMock()
    for nome in promovidas:
        await vaccine_ledger.registrar_falha(
            evo=evo,
            pattern=f"missing_{nome}_implementation",
            context={"skill": nome, "score": 0.85},
        )
    padroes = await vaccine_ledger.vacinas(demo_marker)
    print(f"   Vacinas registradas: {len(padroes)} → {padroes}\n")

    # ── Resultado final ──
    print("=" * 60)
    print("✅ CICLO METABÓLICO COMPLETO")
    print("=" * 60)
    print(f"  • Homocysteine Pool: {homocysteine_pool.count()} skills")
    print(f"  • Promovidas: {len(promovidas)}")
    print(f"  • Marcadores epigenéticos: {profile['total_markers']}")
    print(f"  • Vacinas registradas: {len(padroes)}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
