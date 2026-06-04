import re
import time
import sqlite3
import cbor2
from typing import List, Dict, Optional, Any, Tuple, Union

from iaglobal.models.task import Task
from iaglobal.models.agent_context import AgentContext
from iaglobal.agents.tester_agent import TesterAgent
from iaglobal.agents.planner_agent import PlannerAgent
from iaglobal.agents.critic_agent import CriticAgent
from iaglobal.agents.coder_agent import CoderAgent
from iaglobal.agents.debugger_agent import DebuggerAgent
from iaglobal.agents.reflexion_agent import ReflexionAgent
from iaglobal.agents.semantic_validator import SemanticValidatorAgent
from iaglobal.core.cognitive_proxy import CognitiveProxy
from iaglobal.core.governance import governance
from iaglobal.validation.engine import ValidationEngine
from iaglobal.execution.sandbox import executar_codigo_sandbox as executar_codigo
from iaglobal.memory.memory_error import store_error, format_errors_for_prompt, query_relevant_errors
from iaglobal.memory.memory_storage import store_success
from iaglobal.models.event_bus import bus, EventType
from iaglobal.utils.logger import logger

AGENTES = {
    "dev_fast": {"temperature": 0.3, "style": "fast"},
    "dev_safe": {"temperature": 0.1, "style": "safe"},
    "dev_exploratory": {"temperature": 0.7, "style": "exploratory"},
}

MAX_DEBUG_LOOPS = 3


class Multi_Agent:

    def __init__(self, workdir=None, proxy: Optional[CognitiveProxy] = None):
        self.workdir = workdir
        self.proxy = proxy or CognitiveProxy(web_enabled=True, retry_enabled=True)
        self.planner = PlannerAgent()
        self.coder = CoderAgent()
        self.critic = CriticAgent()
        self.tester = TesterAgent(workdir=workdir)
        self.debugger = DebuggerAgent()
        self.reflexion = ReflexionAgent()

    # =========================================================================
    # 🧠 PIPELINE PRINCIPAL (com CognitiveProxy como orquestrador)
    # =========================================================================

    def resolver(self, task: Union[str, Task], max_iters: int = 3) -> str:
        import time as _time
        start = _time.time()
        governance.validate_call("multi_agent", {"task": str(task)})
        task_str = str(task)
        logger.info(f"[RESOLVER] Iniciando pipeline com CognitiveProxy: "
                    f"task={task_str[:60]}... proxy_web={self.proxy.webbrain is not None}")

        bus.publish(EventType.TASK_CREATED, {"task": task_str[:200]}, source="multi_agent.resolver")

        ctx = AgentContext(task=task_str)

        # Fase 1-3: CognitiveProxy constrói contexto (memory + web + fusão)
        ctx = self._fase_contexto_proxy(ctx)

        # Fase 4: Planner
        ctx = self._fase_planner(ctx)
        if not ctx.plan:
            elapsed = _time.time() - start
            logger.error(f"[RESOLVER] Pipeline interrompido: plano inválido elapsed={elapsed:.1f}s")
            return "[SANITY BARRIER] Pipeline interrompido: plano inválido."

        codigo_acumulado = ""
        total_subtasks = len(ctx.plan.get("subtarefas", []))

        for idx, subtarefa in enumerate(ctx.plan.get("subtarefas", []), 1):
            logger.info(f"📍 Etapa {idx}/{total_subtasks}: "
                        f"id={subtarefa['id']} desc={subtarefa.get('descricao', '')[:50]}")
            contexto_plano = self.planner.injetar_plano_no_prompt(ctx.plan, subtarefa["id"])
            if codigo_acumulado:
                contexto_plano += (f"\n[CÓDIGO ETAPAS ANTERIORES]:\n"
                                   f"{codigo_acumulado[:200]}...\nConstrua incrementalmente.")

            ctx_sub = AgentContext(
                task=f"{task_str}\n\n{contexto_plano}",
                knowledge=ctx.knowledge,
            )

            ctx_sub = self._fase_multicoder(ctx_sub)
            if not ctx_sub.code_candidates:
                logger.warning(f"[RESOLVER] Etapa {idx}: nenhum candidato gerado")
                bus.publish(EventType.EXECUTION_FAILED, {
                    "subtask": subtarefa.get("descricao", ""),
                    "error": "Nenhuma solução gerada",
                    "task": task_str[:100]
                }, source="multi_agent.resolver")
                continue

            ctx_sub = self._fase_critic_swarm(ctx_sub)
            ctx_sub = self._fase_testar_rankear(ctx_sub, subtarefa["descricao"])
            if not ctx_sub.rankings:
                logger.warning(f"[RESOLVER] Etapa {idx}: ranking vazio")
                continue

            ctx_sub = self._fase_debug_loop(ctx_sub, subtarefa["descricao"])
            codigo_acumulado = ctx_sub.best_code
            logger.info(f"[RESOLVER] Etapa {idx}: score={ctx_sub.best_score} "
                        f"success={ctx_sub.success} codigo_len={len(codigo_acumulado)}")

        ctx = self._fase_reflexao_final(ctx, codigo_acumulado)
        ctx = self._fase_memoria_evolucao(ctx, codigo_acumulado)

        elapsed = _time.time() - start
        logger.info(f"[RESOLVER] Pipeline concluída: codigo={len(codigo_acumulado)} chars "
                    f"subtasks={total_subtasks} elapsed={elapsed:.1f}s")
        return codigo_acumulado

    # =========================================================================
    # FASE 1-3: CognitiveProxy (contexto unificado)
    # =========================================================================

    def _fase_contexto_proxy(self, ctx: AgentContext) -> AgentContext:
        """Delega construção de contexto ao CognitiveProxy."""
        import time as _time
        start = _time.time()
        logger.info(f"[FASE:PROXY] Construindo contexto via CognitiveProxy...")

        try:
            context, sources = self.proxy._build_context(ctx.task)
        except Exception as e:
            logger.warning(f"[FASE:PROXY] Erro no proxy: {e}")
            context, sources = {"memory": [], "web": [], "stm": [], "ltm": []}, {}

        mem_text = self._fmt_context_items(context.get("memory", []))
        web_text = self._fmt_context_items(context.get("web", []))

        ctx.knowledge = f"[MEMÓRIA]\n{mem_text}\n\n[WEB]\n{web_text}"
        elapsed = _time.time() - start
        logger.info(f"[FASE:PROXY] Contexto: mem={sources.get('memory',0)} "
                    f"web={sources.get('web',0)} ltm={sources.get('ltm',0)} "
                    f"stm={sources.get('stm',0)} elapsed={elapsed:.2f}s")

        gov = governance.validate_call("search", {"query": ctx.task}, "busca web via proxy")
        if not gov["valid"]:
            logger.warning(f"[GOVERNANCE] {gov['errors']}")

        return ctx

    # =========================================================================
    # FASE 4 — Planner
    # =========================================================================

    def _fase_planner(self, ctx: AgentContext) -> AgentContext:
        import time as _time
        start = _time.time()
        governance.validate_call("planner", {"task": ctx.task})
        logger.info("📐 [FASE 4]: Gerando plano de execução...")

        conhecimento = self._buscar_solucao_anterior(ctx.task)
        contexto_historico = conhecimento.get("codigo", "") if conhecimento else ""
        logger.debug(f"[FASE 4]: Solução anterior: {len(contexto_historico)} chars")
        plano = self.planner.criar_plano_execucao(ctx.task, contexto_historico)

        if not plano or not isinstance(plano, dict):
            elapsed = _time.time() - start
            logger.error(f"[FASE 4] Sanity Barrier: Plano inválido elapsed={elapsed:.1f}s")
            bus.publish(EventType.SANITY_BARRIER_TRIGGERED, {
                "failed_node": "PlannerAgent",
                "error": "Plano inválido",
                "task": ctx.task[:200]
            }, source="multi_agent._fase_planner")
            store_error(
                prompt=f"sanity_barrier:planner_falhou:{ctx.task[:100]}",
                response="Plano inválido",
                critique="Sanity Barrier",
                corrected="", error_type="SanityBarrier"
            )
            return ctx

        ctx.plan = plano
        elapsed = _time.time() - start
        logger.info(f"✅ [FASE 4]: Plano: {len(plano.get('subtarefas', []))} subtarefa(s) "
                    f"complexidade={plano.get('complexidade','?')} elapsed={elapsed:.1f}s")
        return ctx

    # =========================================================================
    # FASE 5 — MultiCoder
    # =========================================================================

    def _fase_multicoder(self, ctx: AgentContext) -> AgentContext:
        import time as _time
        start = _time.time()
        governance.validate_call("coder", {"task": ctx.task})
        logger.info(f"⚙️ [FASE 5]: Gerando {len(AGENTES)} candidatos...")

        erros = query_relevant_errors(ctx.task, limit=2)
        contexto_erros = format_errors_for_prompt(erros)
        logger.debug(f"[FASE 5]: {len(erros)} erros históricos carregados")

        for nome, cfg in AGENTES.items():
            try:
                t0 = _time.time()
                coder = CoderAgent(temperatura=cfg["temperature"], estilo=cfg["style"])
                codigo = coder.gerar_codigo(ctx.task, contexto=ctx.knowledge, erros_contexto=contexto_erros)
                t1 = _time.time()
                if codigo:
                    ctx.code_candidates[nome] = codigo
                    logger.info(f"✅ '{nome}': {len(codigo)} chars em {t1-t0:.1f}s "
                                f"temp={cfg['temperature']} style={cfg['style']}")
                else:
                    logger.warning(f"⚠️ '{nome}': código vazio em {t1-t0:.1f}s")
            except Exception as e:
                logger.error(f"❌ '{nome}': {e}")

        elapsed = _time.time() - start
        logger.info(f"[FASE 5]: {len(ctx.code_candidates)} candidato(s): "
                    f"{list(ctx.code_candidates.keys())} elapsed={elapsed:.1f}s")
        return ctx

    # =========================================================================
    # FASE 6 — Critic Swarm
    # =========================================================================

    def _fase_critic_swarm(self, ctx: AgentContext) -> AgentContext:
        import time as _time
        start = _time.time()
        governance.validate_call("critic", {"task": ctx.task, "output": ""})
        logger.info(f"🔍 [FASE 6]: Critic Swarm — {len(ctx.code_candidates)} candidato(s)...")

        revisor = CriticAgent()
        semantic = SemanticValidatorAgent()

        for nome in list(ctx.code_candidates.keys()):
            codigo = ctx.code_candidates[nome]
            try:
                t0 = _time.time()
                nota = revisor.avaliar_solucao(ctx.task, codigo)
                t1 = _time.time()
                ctx.critiques.setdefault(nome, []).append(nota)
                logger.debug(f"[FASE 6] '{nome}': crítica em {t1-t0:.1f}s")
            except Exception as e:
                ctx.critiques.setdefault(nome, []).append(f"REJECT: {e}")
                logger.warning(f"[FASE 6] '{nome}': crítica falhou: {e}")

            try:
                sem = semantic.validate(codigo, ctx.task)
                if not sem.get("valid"):
                    ctx.critiques.setdefault(nome, []).append(
                        f"REJECT: {'; '.join(sem.get('errors', []))}"
                    )
            except Exception:
                pass

        bus.publish(EventType.CRITIC_SWARM_COMPLETED, {
            "task": ctx.task[:100],
            "candidates": len(ctx.code_candidates),
        }, source="multi_agent._fase_critic_swarm")
        elapsed = _time.time() - start
        logger.info(f"✅ [FASE 6]: {len(ctx.critiques)} criticas em {elapsed:.1f}s")
        return ctx

    # =========================================================================
    # FASE 7 — Testing + Ranking (unificado)
    # =========================================================================

    def _fase_testar_rankear(self, ctx: AgentContext, subtask_desc: str) -> AgentContext:
        import time as _time
        start = _time.time()
        logger.info(f"🧪 [FASE 7]: Testando {len(ctx.code_candidates)} candidato(s)...")

        resultados = []
        for nome, codigo in ctx.code_candidates.items():
            score, detalhes = self._avaliar_candidato(
                nome, codigo, ctx.task, subtask_desc, ctx.critiques.get(nome, [])
            )
            ctx.test_results[nome] = detalhes
            resultados.append((score, nome, codigo, detalhes.get("error", "")))
            logger.debug(f"[FASE 7] '{nome}': score={score} "
                         f"tests={detalhes.get('tests_passed')}/{detalhes.get('tests_total')}")

        resultados.sort(reverse=True, key=lambda x: x[0])
        ctx.rankings = resultados

        if resultados:
            ctx.best_score, ctx.best_code = resultados[0][0], resultados[0][2]
            ctx.success = ctx.best_score >= 80.0
            logger.info(f"[FASE 7] Ranking: melhor={resultados[0][1]} "
                        f"score={ctx.best_score} success={ctx.success}")
        else:
            logger.warning("[FASE 7] Ranking vazio — nenhum candidato aprovado")

        bus.publish(EventType.RANKING_COMPLETED, {
            "task": ctx.task[:100],
            "best_score": ctx.best_score,
            "rankings": [{"agent": r[1], "score": r[0]} for r in resultados]
        }, source="multi_agent._fase_testar_rankear")
        elapsed = _time.time() - start
        logger.info(f"✅ [FASE 7]: Ranking concluído: {len(resultados)} resultado(s) "
                    f"elapsed={elapsed:.1f}s")
        return ctx

    def _avaliar_candidato(self, nome: str, codigo: str, task: str,
                           descricao: str, criticas: List[str]) -> tuple:
        """Avalia um candidato: testes + score multi-critério."""
        tempo_ini = time.perf_counter()
        codigo_teste = self.tester.gerar_bateria_testes(descricao, codigo)
        codigo_completo = self.tester.amalgamar_codigo_e_teste(codigo, codigo_teste)
        res = executar_codigo(codigo_completo)
        tempo_exec = time.perf_counter() - tempo_ini

        output = res.get("output", "").strip()
        total, falhas = self._parse_test_output(output)
        score_testes = 100.0 if res["sucesso"] else ((total - falhas) / total * 80.0 if total > 0 else 0.0)
        sandbox_ok = res.get("sucesso", False)

        if criticas:
            score_critic = 100.0 if any("OK" in c or "approved" in c for c in criticas) else 50.0
            score_final = score_testes * 0.50 + score_critic * 0.50
        else:
            score_final = score_testes

        score_final = round(max(0.0, score_final
            - min(len(codigo.splitlines()) * 0.05, 5.0)
            - min(tempo_exec * 2.0, 5.0)
        ), 2)

        if score_testes >= 80.0:
            res_file = self.tester.gerar_salvar_e_executar(codigo, descricao)
            if res_file.get("sucesso"):
                logger.info(f"[AVALIAR] Teste persistido: {res_file.get('arquivo', '')}")

        logger.info(f"[AVALIAR] '{nome}': score={score_final} "
                    f"testes={total-falhas}/{total} sandbox={sandbox_ok} "
                    f"criticas={len(criticas)} tempo_exec={tempo_exec:.3f}s")

        bus.publish(EventType.SOLUTION_GENERATED, {
            "agent": nome, "score": score_final,
            "tests_passed": total - falhas, "tests_total": total,
            "execution_time": round(tempo_exec, 4),
            "task": task[:100]
        }, source="multi_agent._avaliar_candidato")

        return score_final, {
            "score": score_final, "tests_passed": total - falhas,
            "tests_total": total, "error": output,
        }

    @staticmethod
    def _parse_test_output(output: str) -> tuple:
        total = 0
        falhas = 0
        m = re.search(r"Ran\s+(\d+)\s+tests", output)
        if m:
            total = int(m.group(1))
        m = re.search(r"failures=(\d+)", output)
        if m:
            falhas += int(m.group(1))
        m = re.search(r"errors=(\d+)", output)
        if m:
            falhas += int(m.group(1))
        return total, falhas

    # =========================================================================
    # FASE 8 — Debug Loop
    # =========================================================================

    def _fase_debug_loop(self, ctx: AgentContext, subtask_desc: str) -> AgentContext:
        governance.validate_call("debugger", {"code": ctx.best_code or "", "error": ""})
        logger.info(f"🔧 [FASE 8]: Debug loop (máx {MAX_DEBUG_LOOPS})...")

        iteracao = 0
        while not ctx.success and iteracao < MAX_DEBUG_LOOPS:
            iteracao += 1
            ctx.debug_attempts = iteracao
            erro = next(
                (tr["error"] for tr in ctx.test_results.values() if tr.get("error")),
                f"Score: {ctx.best_score}"
            )

            corrigido = self.debuggar(ctx.best_code, erro, ctx.task)
            if not corrigido or corrigido == ctx.best_code:
                break

            ctx.code_candidates[f"debug_{iteracao}"] = corrigido
            ctx.best_code = corrigido

            score_teste, detalhes = self._avaliar_candidato(
                f"debug_{iteracao}", corrigido, ctx.task, subtask_desc, []
            )
            ctx.test_results[f"debug_{iteracao}"] = detalhes

            check = CriticAgent().avaliar_com_scores(ctx.task, corrigido)
            if check.get("approved", False):
                ctx.best_score = 100.0
                ctx.success = True
            else:
                ctx.best_score = check.get("score", score_teste)

            ref = self.refletir(corrigido, {"sucesso": ctx.success}, ctx.task)
            ctx.reflections.append({
                "iteration": iteracao, "error": erro[:200],
                "reflection": ref[:500], "score": ctx.best_score,
            })

            bus.publish(EventType.DEBUG_ITERATION, {
                "task": ctx.task[:100], "iteration": iteracao,
                "score": ctx.best_score, "success": ctx.success,
            }, source="multi_agent._fase_debug_loop")

            if ctx.success:
                break

        logger.info(f"   Debug: {iteracao} iteração(ões), score={ctx.best_score}")
        return ctx

    # =========================================================================
    # FASE 9 — Reflexão Final
    # =========================================================================

    def _fase_reflexao_final(self, ctx: AgentContext, codigo: str) -> AgentContext:
        logger.info("🔄 [FASE 9]: Reflexão final...")
        ref = self.refletir(codigo, {"sucesso": bool(codigo)}, ctx.task)
        ctx.reflections.append({"iteration": "final", "reflection": ref[:500]})
        bus.publish(EventType.REFLECTION_COMPLETED, {
            "task": ctx.task[:100], "analysis": ref[:200]
        }, source="multi_agent._fase_reflexao_final")
        return ctx

    # =========================================================================
    # FASE 10 — Memória
    # =========================================================================

    def _fase_memoria_evolucao(self, ctx: AgentContext, codigo: str) -> AgentContext:
        logger.info("💾 [FASE 10]: Salvando memória...")
        store_success(ctx.task, codigo, {"complexidade": (ctx.plan or {}).get("complexidade", "")})
        bus.publish(EventType.MEMORY_SAVED, {
            "memory_type": "success", "task": ctx.task[:100],
            "codigo_length": len(codigo)
        }, source="multi_agent._fase_memoria_evolucao")
        return ctx

    # =========================================================================
    # MÉTODOS AUXILIARES
    # =========================================================================

    def criticar(self, codigo: str, task: Union[str, Task]) -> str:
        governance.validate_call("critic", {"task": str(task), "output": codigo})
        resultado = self.critic.avaliar_solucao(str(task), codigo)
        return resultado

    def debuggar(self, codigo: str, erro: str, task: Union[str, Task]) -> str:
        governance.validate_call("debugger", {"code": codigo, "error": erro})
        resultado = self.debugger.corrigir_codigo(codigo, erro, str(task))
        return resultado

    def refletir(self, codigo: str, res: dict, task: Union[str, Task]) -> str:
        return self.reflexion.analisar_resultado(codigo, res, str(task))

    @staticmethod
    def codigo_python_valido(codigo: str) -> bool:
        return ValidationEngine().validate(codigo).valid

    @staticmethod
    def extrair_codigo_puro(texto: str) -> str:
        if not texto:
            return ""
        texto = texto.strip()
        texto = re.sub(r"^```(?:python|py)?", "", texto, flags=re.IGNORECASE)
        texto = re.sub(r"```$", "", texto)
        return texto.strip()

    def _buscar_solucao_anterior(self, task: str) -> Optional[Dict]:
        """Busca solução anterior no banco de sucessos."""
        from iaglobal._paths import CORE_DB
        conn = None
        try:
            conn = sqlite3.connect(str(CORE_DB))
            for (blob,) in conn.execute(
                "SELECT data FROM success_registry ORDER BY id DESC LIMIT 20"
            ).fetchall():
                if not blob:
                    continue
                try:
                    dados = cbor2.loads(blob)
                    if task.lower() in str(dados.get("task", "")).lower():
                        codigo = dados.get("codigo") or dados.get("code") or dados.get("solution")
                        if codigo:
                            return {
                                "codigo": codigo.decode("utf-8") if isinstance(codigo, bytes) else codigo,
                                "task": dados.get("task", task),
                            }
                except Exception:
                    continue
        except Exception:
            pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
        return None

    @staticmethod
    def _fmt_context_items(items: list) -> str:
        if not items:
            return "(vazio)"
        lines = []
        for item in items[:3]:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                _, data = item
                text = data.get("text", str(data)) if isinstance(data, dict) else str(data)
                lines.append(text[:150])
            elif isinstance(item, dict):
                lines.append((item.get("content") or item.get("text") or str(item))[:150])
        return "\n".join(lines) or "(vazio)"

    def _executar_bateria_testes(self, solucoes: Dict[str, str], task: str) -> List[Tuple[float, str, str, str]]:
        """Executa bateria de testes em soluções. Usado pelo wrapper testar_solucoes."""
        logger.info(f"[BATERIA] Testando {len(solucoes)} solução(ões)...")
        resultados = []
        for nome, codigo in solucoes.items():
            score, detalhes = self._avaliar_candidato(nome, codigo, task, task, [])
            error = detalhes.get("error", "")
            resultados.append((score, nome, codigo, error))
        resultados.sort(reverse=True, key=lambda x: x[0])
        return resultados


# =========================================================================
# WRAPPERS DE COMPATIBILIDADE
# =========================================================================

def buscar_solucao_anterior(task_id: str):
    return Multi_Agent()._buscar_solucao_anterior(str(task_id))

def gerar_solucoes(task: Any, conhecimento: Optional[Dict] = None) -> Dict[str, str]:
    logger.info(f"[WRAPPER] gerar_solucoes: {str(task)[:80]}")
    solucoes = {}
    erros = query_relevant_errors(str(task), limit=2)
    contexto_erros = format_errors_for_prompt(erros)
    contexto = conhecimento.get("codigo", "") if conhecimento else ""
    for nome, cfg in AGENTES.items():
        try:
            coder = CoderAgent(temperatura=cfg["temperature"], estilo=cfg["style"])
            codigo = coder.gerar_codigo(task, contexto=contexto, erros_contexto=contexto_erros)
            if codigo:
                solucoes[nome] = codigo
        except Exception as e:
            logger.error(f"❌ '{nome}': {e}")
    return solucoes

def criticar(codigo: str, task: Any):
    return Multi_Agent().criticar(codigo, task)

def debuggar(codigo: str, erro: str, task: Any):
    return Multi_Agent().debuggar(codigo, erro, task)

def processar_testar_solucoes(solucoes: dict, task: Any) -> List[Tuple[float, str, str, str]]:
    logger.info(f"[WRAPPER] testar_solucoes: {len(solucoes)} soluções")
    return Multi_Agent()._executar_bateria_testes(solucoes, str(task))

def resolver(task: Union[str, Task], max_iters: int = 3) -> str:
    return Multi_Agent(proxy=CognitiveProxy(web_enabled=True, retry_enabled=True)).resolver(task, max_iters)
