# iaglobal/cli/learn.py

import asyncio
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.cli.learn")


async def run_learn(args, orch) -> None:
    prompt = args.prompt if isinstance(args.prompt, list) else []
    subcommand = prompt[0] if prompt else "status"
    subargs = prompt[1:]

    if subcommand in ("consolidate", "rem"):
        await _cmd_consolidate()
    elif subcommand == "search":
        query = " ".join(subargs) if subargs else ""
        await _cmd_search(query)
    elif subcommand == "write":
        if len(subargs) < 2:
            print("Uso: iaglobal learn write <tag> <conteudo>")
            return
        tag = subargs[0]
        content = " ".join(subargs[1:])
        await _cmd_write(tag, content)
    elif subcommand in ("insights", "suggestions"):
        await _cmd_insights()
    elif subcommand == "suggest":
        await _cmd_suggest()
    elif subcommand == "map":
        await _cmd_map()
    elif subcommand == "auto-tune":
        await _cmd_autotune()
    else:
        await _cmd_status()


async def _cmd_status() -> None:
    from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

    sub = SubconsciousAPI()

    def _count_vault():
        return (
            len(list(sub.instincts_dir.glob("*.md"))),
            len(list(sub.short_term_dir.glob("*.md"))),
            len(list(sub.long_term_dir.glob("*.md"))),
            len(list(sub.synapses_dir.glob("*.md"))),
        )

    instincts, short, long_, synapses = await asyncio.to_thread(_count_vault)

    from iaglobal.meta.meta_learner import get_meta_learner

    learner = get_meta_learner()

    print("\n APRENDIZADO DO CHAPPIE")
    print("=" * 50)
    print(f"  Vault Obsidian:")
    print(f"    Instintos (01):    {instincts}")
    print(f"    Curto Prazo (02):  {short}")
    print(f"    Longo Prazo (03):  {long_}")
    print(f"    Sinapses (04):     {synapses}")
    print(f"  Meta-Learner:")
    print(f"    Sugestoes:         {len(learner.suggestions)}")
    print(f"    Backlog:           {len(learner.evolution_backlog)}")
    print(f"    Padroes Sucesso:   {len(learner.success_patterns)}")
    print(f"    Padroes Falha:     {len(learner.failure_patterns)}")
    epsilon = learner.auto_tuned_configs.get("bandit_epsilon", "N/A")
    print(f"  Epsilon Bandit:      {epsilon}")

    try:
        from iaglobal.chappie.bandit_evolution import get_bandit_evolution

        bandit_evo = get_bandit_evolution()
        evo_status = bandit_evo.get_status_evolution()
        print(f"  BanditEvolution:")
        print(f"    Ciclos:            {evo_status.get('ciclos_completados', 0)}")
        print(f"    Providers:         {evo_status.get('total_providers', 0)}")
        print(f"    Banidos:           {evo_status.get('providers_banidos', 0)}")
        print(f"    Fitness Medio:     {evo_status.get('fitness_medio', 0):.3f}")
        ultimo = evo_status.get("ultimo_web_learn")
        print(f"    Ultima Busca:      {ultimo or 'nunca'}")
    except Exception:
        pass

    print("=" * 50)


async def _cmd_consolidate() -> None:
    from iaglobal.obsidian.consolidation import REMSleepEngine

    engine = REMSleepEngine()
    result = await engine.iniciar_fase_rem()
    print("\n CICLO REM DE CONSOLIDACAO")
    print("=" * 50)
    print(f"  Status:              {result.get('status', 'N/A')}")
    print(f"  Memorias Processadas: {result.get('memorias_processadas', 0)}")
    print(f"  Memorias Consolidadas: {result.get('memorias_consolidadas', 0)}")
    erros = result.get("erros", [])
    if erros:
        print(f"  Erros: {len(erros)}")
        for err in erros[:5]:
            print(f"    - {err}")
    print("=" * 50)


async def _cmd_search(query: str) -> None:
    if not query:
        print("Uso: iaglobal learn search <consulta>")
        return
    from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

    sub = SubconsciousAPI()
    notes = await sub.buscar_notas(query)
    print(f'\n Busca por "{query}": {len(notes)} resultados')
    print("=" * 50)
    for note in notes[:10]:
        print(f"  [{note.get('tipo', '?')}] {note.get('id', '?')}")
        print(f"    Tags: {note.get('metadados', {}).get('tags', 'N/A')}")
        print()
    if len(notes) > 10:
        print(f"  ... e mais {len(notes) - 10} resultados")
    print("=" * 50)


async def _cmd_write(tag: str, content: str) -> None:
    from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

    sub = SubconsciousAPI()
    path = await sub.escrever_curto_prazo(
        nome=f"insight_{tag}",
        conteudo=content,
        tags=[f"#{tag}"],
    )
    print(f" Nota salva em: {path}")


async def _cmd_insights() -> None:
    from iaglobal.meta.meta_learner import get_meta_learner

    learner = get_meta_learner()
    suggestions = learner.get_suggestions(min_confidence=0.3)
    print(f"\n SUGESTOES ARQUITETURAIS ({len(suggestions)})")
    print("=" * 50)
    if not suggestions:
        print("  Nenhuma sugestao ainda. Execute tarefas para gerar.")
    for s in suggestions[:10]:
        print(f"  [{s.priority.upper()}] {s.category}")
        print(f"  {s.description}")
        print(f"  Confianca: {s.confidence:.0%} | Impacto: {s.expected_improvement}")
        print()
    print("=" * 50)


async def _cmd_suggest() -> None:
    from iaglobal.meta.meta_learner import get_meta_learner

    learner = get_meta_learner()
    backlog = learner.get_backlog(priority_min=0.3)
    print(f"\n BACKLOG EVOLUTIVO ({len(backlog)})")
    print("=" * 50)
    if not backlog:
        print("  Nenhum item no backlog. Execute tarefas para gerar.")
    for item in backlog[:10]:
        print(f"  [{item.item_type}] {item.description}")
        print(f"  Prioridade: {item.priority_score:.2f} | Status: {item.status}")
        print()
    print("=" * 50)


async def _cmd_map() -> None:
    from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

    sub = SubconsciousAPI()
    print(" Reconstruindo mapa sinaptico...")
    await sub.atualizar_mapa_conexoes()
    print(" Mapa sinaptico reconstruido.")


async def _cmd_autotune() -> None:
    from iaglobal.meta.meta_learner import get_meta_learner

    learner = get_meta_learner()
    configs = learner.auto_tuned_configs
    print("\n CONFIGURACOES AUTO-AJUSTADAS")
    print("=" * 50)
    if not configs:
        print("  Nenhum auto-ajuste ainda. Execute tarefas para gerar.")
    for key, val in configs.items():
        print(f"  {key}: {val}")
    print("=" * 50)
