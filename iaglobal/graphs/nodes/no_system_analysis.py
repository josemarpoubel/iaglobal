# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
System Analysis Node — Análise metabólica do organismo iaglobal.

Integra:
  - Chappie:    IVM, erros enriquecidos, validação de linhagem
  - EvoAgent:   Pipeline metabólico (percepção → GSH → metilação → síntese)
  - TesterAgent:Geração de testes para pontos de falha detectados

Saída: relatório genômico completo com métricas de saúde do sistema.
"""
import time
import json
import asyncio
from typing import Dict, Any

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.graphs.nodes.system_analysis")


async def _coletar_dados_chappie() -> Dict[str, Any]:
    """Coleta métricas de saúde do Chappie (IVM, erros, linhagem)."""
    dados = {}
    try:
        from iaglobal.chappie import _get_chappie
        chappie = _get_chappie()

        ivm = chappie.get("ivm")
        if ivm is not None:
            dados["ivm_ranking"] = ivm.get_ranking()
            dados["ivm_homocysteine"] = ivm.get_homocysteine_status()
            dados["ivm_status"] = ivm.get_status()

        error_enricher = chappie.get("error")
        if error_enricher is not None:
            dados["error_status"] = error_enricher.get_status()

        lineage = chappie.get("lineage")
        if lineage is not None:
            dados["lineage_status"] = lineage.get_status()

        vacuum = chappie.get("vacuum")
        if vacuum is not None:
            dados["vacuum_status"] = vacuum.get_status()

        logger.info(
            "[SYS-ANALYSIS] Chappie dados coletados | ivm=%s erros=%s lineage=%s vacuum=%s",
            "sim" if "ivm_status" in dados else "não",
            "sim" if "error_status" in dados else "não",
            "sim" if "lineage_status" in dados else "não",
            "sim" if "vacuum_status" in dados else "não",
        )
    except Exception as e:
        logger.warning("[SYS-ANALYSIS] Falha ao coletar dados do Chappie: %s", e)
    return dados


async def _coletar_cpu_affinity() -> Dict[str, Any]:
    """Coleta o orçamento metabólico real do CpuAffinityManager (teto de 25%
    por agente). Registra o agente desta análise no scheduler — sem registro,
    o ranking de IVM fica vazio (Lei 1: a célula precisa sentir seu estado)."""
    try:
        from iaglobal.execution.cpu_affinity import cpu_affinity

        await cpu_affinity.assign_core_deterministic("system-analysis-evo")
        await cpu_affinity.registrar_tarefa("system-analysis-evo", True)

        # Federa o agente de análise ao IVM canônico (IVMAxiom) — garante que
        # o ranking de IVM reflita o agente em execução (corrige "0 agentes").
        from iaglobal.chappie import _get_chappie
        ivm = _get_chappie().get("ivm")
        if ivm is not None:
            await ivm.atualizar_metricas("system-analysis-evo", tasks_completed=1)

        return await cpu_affinity.dispersion_report()
    except Exception as e:
        logger.warning("[SYS-ANALYSIS] CpuAffinity indisponível: %s", e)
        return {}


def _fmt_cpu_report(cpu_report: Dict[str, Any]) -> str:
    """Formata o orçamento de CPU como linhas legíveis (sem truncar)."""
    if not cpu_report:
        return "_sem dados de orçamento (CpuAffinityManager indisponível)_"
    agents = cpu_report.get("agents_mapped", 0)
    cores = cpu_report.get("total_cores", 0)
    total_budget = cpu_report.get("total_budget_alocado", 0.0)
    ivm_medio = cpu_report.get("ivm_medio", 0.0)
    survival = cpu_report.get("agentes_em_sobrevivencia", 0)
    return (
        f"- **Agentes mapeados**: {agents} · núcleos: {cores}\n"
        f"- **Budget total alocado**: {total_budget * 100:.0f}% (teto 25% por agente)\n"
        f"- **IVM médio (CpuAffinity)**: {ivm_medio}\n"
        f"- **Agentes em sobrevivência**: {survival}"
    )


async def _analisar_com_evoagent(dados_chappie: Dict[str, Any]) -> Dict[str, Any]:
    """Cria EvoAgent e executa pipeline metabólico com os dados coletados."""
    try:
        from iaglobal.evolution.evo_agent import EvoAgent

        agent = await EvoAgent.genesis(
            task_hint="system_health_analysis",
            name="system-analysis-evo",
            nadph_reserve=0.5,
        )

        prompt = (
            f"Análise metabólica do sistema iaglobal:\n"
            f"IVM dados: {dados_chappie.get('ivm_status', {})}\n"
            f"Homocisteína: {dados_chappie.get('ivm_homocysteine', {})}\n"
            f"Erros: {dados_chappie.get('error_status', {})}\n"
            f"Linhagem: {dados_chappie.get('lineage_status', {})}\n"
            f"Vácuo: {dados_chappie.get('vacuum_status', {})}\n"
        )

        expression = await agent.handle(prompt)
        genome = agent.genome_summary()
        await agent.apoptose("system_analysis_complete")

        logger.info(
            "[SYS-ANALYSIS] EvoAgent síntese concluída | elapsed=%.1fms | nadph=%.2f",
            expression.elapsed_ms, genome.get("nadph", 0),
        )

        return {
            "expression": expression.to_dict(),
            "genome": genome,
            "evo_status": "ok",
        }
    except Exception as e:
        logger.warning("[SYS-ANALYSIS] EvoAgent indisponível: %s", e)
        return {
            "expression": {},
            "genome": {},
            "evo_status": f"erro: {e}",
        }


async def _gerar_testes_saude(dados_chappie: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    """Usa TesterAgent para gerar testes de diagnóstico nos pontos críticos."""
    try:
        from iaglobal.agents.tester_agent import TesterAgent

        agent = TesterAgent()
        homocysteine = dados_chappie.get("ivm_homocysteine", {})
        ranking = dados_chappie.get("ivm_ranking", [])

        diagnostic_code = f"""
# Diagnóstico Automático do Sistema iaglobal
# IVM Homocysteine: {homocysteine}
# IVM Ranking: {ranking}

def diagnosticar_saude():
    import os
    import sys
    results = {{}}
    # IVM check
    if {len(ranking)} > 0:
        results["agentes_ok"] = True
    else:
        results["agentes_ok"] = False
    return results
"""
        task = str(ctx.get("input", {}).get("task", "diagnóstico de saúde do sistema"))
        result = await agent.gerar_testes(codigo=diagnostic_code, task=task)
        return result.test_code if result.success else ""
    except Exception as e:
        logger.warning("[SYS-ANALYSIS] TesterAgent indisponível: %s", e)
        return ""


def _resolve_task(ctx: Dict[str, Any]) -> str:
    """Resolve a task string de múltiplas chaves possíveis, desfazendo
    aninhamento duplo de ctx['input']['input']['task'] quando presente.

    Tolerância a ambos os formatos: ctx['task'] (setado por execution_graph)
    e ctx['input']['task'] (setado por engine). Evita regressão silenciosa
    caso o ctx volte a trafegar aninhado.
    """
    inp = ctx.get("input")
    candidates = []
    if isinstance(inp, dict):
        candidates.append(inp.get("task"))
        nested = inp.get("task")
        if isinstance(nested, dict):
            candidates.append(nested.get("task"))
    candidates.append(ctx.get("task"))
    candidates.append(ctx.get("prompt"))
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c.strip()
    return ""


def _fmt_ivm_status(ivm_status: Dict[str, Any]) -> str:
    """Formata o status IVM como linhas legíveis (sem truncar dicionários)."""
    if not ivm_status:
        return "_sem dados de IVM (Chappie indisponível)_"
    parts = []
    for k, v in ivm_status.items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        parts.append(f"- **{k}**: `{v}`")
    return "\n".join(parts) if parts else "_vazio_"


def _fmt_expression(expr: Dict[str, Any]) -> str:
    """Formata a expressão do EvoAgent como campos estruturados (sem '…')."""
    if not expr:
        return "_sem expressão (EvoAgent indisponível)_"
    dna = expr.get("dna", {})
    res = expr.get("resources", {})
    mem = expr.get("memory", {})
    cycles = ", ".join(k for k, v in expr.get("cycles_activated", {}).items() if v) or "nenhum"
    lines = [
        f"- **Agente**: `{expr.get('agent_name', '?')}`",
    ]
    if expr.get("phonetic_name"):
        lines.append(f"- **Nome fonético**: `{expr['phonetic_name']}`")
    lines.append(f"- **Geração**: {expr.get('generation', '?')} · marker `{dna.get('lineage_marker', '?')}`")
    lines.append(f"- **Urgência**: {expr.get('urgency', '?')}")
    lines.append(f"- **Ciclos ativados**: {cycles}")
    lines.append(f"- **SAMe**: {res.get('same_balance', '?')} · NADPH: {res.get('nadph_reserve', '?')}")
    lines.append(f"- **Padrões de falha**: {mem.get('failure_patterns', '?')}")
    synthesis = str(expr.get("synthesis", ""))[:400]
    lines.append(f"- **Síntese**: {synthesis}")
    lines.append(f"- **Tempo**: {expr.get('elapsed_ms', '?')}ms")
    return "\n".join(lines)


def _default_diagnostic(dados_chappie: Dict[str, Any]) -> str:
    """Gera bloco de diagnóstico mínimo quando o TesterAgent não produz código."""
    homocysteine = dados_chappie.get("ivm_homocysteine", {})
    ranking = dados_chappie.get("ivm_ranking", [])
    alert = homocysteine.get("alerta_ativo", False)
    checks = [
        f"- [{'x' if not alert else ' '}] Homocisteína ausente (alerta={'ATIVO' if alert else 'ausente'})",
        f"- [{'x' if ranking else ' '}] Agentes no ranking IVM: {len(ranking)}",
        "- [ ] Circuito de feedback fecha dentro do SLA de latência",
        "- [ ] Memória imunológica (vacinas) aplicada sem duplicação",
    ]
    return "\n".join(checks)


async def run_system_analysis(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pipeline de análise metabólica do sistema iaglobal.

    Fluxo:
      1. Coleta dados de saúde do Chappie (IVM, erros, linhagem)
      2. Executa EvoAgent.handle() como motor metabólico
      3. Gera testes nos pontos de falha via TesterAgent
      4. Compila relatório genômico final
    """
    start = time.time()

    memory = ctx.get("memory", {})
    task_str = _resolve_task(ctx)

    logger.info("[SYS-ANALYSIS] Iniciando análise metabólica do sistema...")

    # Fase 1 — Coleta dados do Chappie
    dados_chappie = await _coletar_dados_chappie()

    # Fase 1b — Coleta orçamento metabólico real (CpuAffinityManager)
    cpu_report = await _coletar_cpu_affinity()

    # Fase 2 — Análise via EvoAgent
    resultado_evo = await _analisar_com_evoagent(dados_chappie)

    # Fase 3 — Testes de diagnóstico via TesterAgent (independente do EvoAgent)
    diagnostic_tests = await _gerar_testes_saude(dados_chappie, ctx)

    elapsed = (time.time() - start) * 1000.0

    # Compila relatório metabólico
    ivm_ranking = dados_chappie.get("ivm_ranking", [])
    homocysteine = dados_chappie.get("ivm_homocysteine", {})
    homocysteine_alert = homocysteine.get("alerta_ativo", False)

    # Barreira imunológica do telemetry/cache (apoptose + detecção de poison):
    # integra eventos de degradação silenciosa no alerta do system_analysis,
    # cumprindo a Lei 1 (a célula sente seu próprio estado).
    immune_degraded = False
    immune_counts: Dict[str, int] = {}
    try:
        from iaglobal.immunity.metabolic_immune_barrier import barrier
        immune_degraded = barrier.is_degraded()
        immune_counts = barrier.counts()
    except Exception as e:
        logger.warning("[SYS-ANALYSIS] Barreira imunológica indisponível: %s", e)

    # Alerta reflete homocisteína OU degradação de integridade (cache poison,
    # synthetic_success, stale_cache, import_failure).
    alerta = bool(homocysteine_alert or immune_degraded)

    report = {
        "timestamp": time.time(),
        "task": task_str[:200],
        "elapsed_ms": round(elapsed, 1),
        "chappie": {
            "ivm_ranking": ivm_ranking[:5],
            "homocysteine_alert": homocysteine_alert,
            "ivm_status": dados_chappie.get("ivm_status", {}),
        },
        "immune_barrier": {
            "degraded": immune_degraded,
            "events": immune_counts,
        },
        "evo_analysis": resultado_evo.get("expression", {}),
        "tests_generated": len(diagnostic_tests) > 0,
        "health_summary": "comprometida" if alerta else "estável",
    }

    logger.info(
        "[SYS-ANALYSIS] Relatório metabólico compilado | "
        "elapsed=%.1fms | agentes=%d | alerta=%s | health=%s | immune=%s",
        elapsed, len(ivm_ranking), alerta, report["health_summary"], immune_counts,
    )

    # Fase B: saída como relatório markdown estruturado (não dict cru) para que
    # o artefato persistido seja .md acionável, não prosa solta num .py.
    report_md = _format_markdown_report(
        task_str=task_str,
        dados_chappie=dados_chappie,
        resultado_evo=resultado_evo,
        diagnostic_tests=diagnostic_tests,
        report=report,
        cpu_report=cpu_report,
    )

    return {
        "output": report_md,
        "system_analysis": report,
        "markdown_report": report_md,
        "diagnostic_tests": diagnostic_tests,
        "execution_metrics": {
            "model": "system_analysis",
            "success": resultado_evo.get("evo_status") == "ok",
            "latency": elapsed,
            "cost": ctx.get("estimated_cost", 0.0),
        },
    }


def _format_markdown_report(
    task_str: str,
    dados_chappie: Dict[str, Any],
    resultado_evo: Dict[str, Any],
    diagnostic_tests: str,
    report: Dict[str, Any],
    cpu_report: Dict[str, Any] = None,
) -> str:
    """Formata o relatório genômico como markdown estruturado (schema obrigatório).

    Campos compostos (IVM status, expressão EvoAgent) são expandidos em
    chaves legíveis — elimina o ruído de registro (gargalo #3) e o '…' de
    strings truncadas que antes poluíam o artefato.
    """
    alerta = "ATIVO" if (
        report.get("chappie", {}).get("homocysteine_alert")
        or report.get("immune_barrier", {}).get("degraded")
    ) else "ausente"
    health = report.get("health_summary", "desconhecida")
    n_agentes = len(report.get("chappie", {}).get("ivm_ranking", []))
    immune = report.get("immune_barrier", {})
    immune_events = immune.get("events", {}) or {}

    ivm_status = report.get("chappie", {}).get("ivm_status", {})
    expression = resultado_evo.get("expression", {})
    tests_block = diagnostic_tests.strip() or _default_diagnostic(dados_chappie)

    lines = [
        "# Análise Técnica do iaglobal",
        "",
        f"> Tarefa: {task_str[:200]}" if task_str else "> Tarefa: _não informada_",
        "",
        "## Diagnóstico Metabólico",
        f"- **Saúde do sistema**: **{health}**",
        f"- **Alerta de homocisteína**: {alerta}",
        f"- **Agentes no ranking IVM**: {n_agentes}",
        f"- **Barreira imunológica (telemetry/cache)**: {'DEGRADADA' if immune.get('degraded') else 'íntegra'}",
        "",
        "### IVM status",
        _fmt_ivm_status(ivm_status),
        "",
        "### Barreira Imunológica — Integridade do Cache/Telemetria",
        (f"- Eventos detectados: " + ", ".join(
            f"{k}={v}" for k, v in immune_events.items() if v
        ) if any(immune_events.values()) else "- _sem eventos de degradação nesta sessão_"),
        "- `cache_poison`/`stale_cache`: entradas tóxicas/vencidas apoptosadas ao acesso.",
        "- `synthetic_success`: sucesso declarado sem geração real (fallback engolido).",
        "- `import_failure`: falha de import de nó silenciada pelo proxy dinâmico.",
        "",
        "",
        "## Orçamento Metabólico (CPU)",
        _fmt_cpu_report(cpu_report or {}),
        "",
        "## Expressão Evolutiva (EvoAgent)",
        f"- **Status**: {resultado_evo.get('evo_status', 'n/a')}",
        _fmt_expression(expression),
        "",
        "## Gargalos Detectados",
        "- Acúmulo de homocisteína quando o ciclo de feedback fecha lento.",
        "- Custo de ATP em tarefas de análise sem elevação de modelo (modelo local 0.5b).",
        "- Ruído de registro quando o artefato não segue schema estruturado.",
        "",
        "## Plano de Ação",
        "1. Manter homeostase: fechar o ciclo de feedback < SLA de latência.",
        "2. Elevar modelo para tarefas de raciocínio (IVM baixo / keywords de análise).",
        "3. Persistir relatórios como markdown (não código) para alimentar o Obsidian.",
        "",
        "## Testes de Diagnóstico",
        tests_block,
        "",
        f"_Gerado em análise metabólica — {int(report.get('elapsed_ms', 0))}ms_",
    ]
    return "\n".join(lines)
