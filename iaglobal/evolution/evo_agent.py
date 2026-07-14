"""
iaglobal/evolution/evo_agent.py
================================
EvoAgent — Organismo Computacional Nativo do iaglobal
Geração 1 — DNA SHA3-512 hereditário

Capacidades biológicas implementadas com módulos REAIS do iaglobal:

  CICLO                  MÓDULO NATIVO
  ─────────────────────────────────────────────────────────────────────
  DNA / Identidade    →  utils.hash_utils.LineageID (SHA3-512)
  Percepção           →  classifica urgência, gera execution_id único
  Glutationa (GSH)    →  immunity.glutathione_guardrails.GlutathioneGuardrails
                         immunity.glutathione_pool.GlutathionePool
  Pool homocistina    →  evolution.metabolism.homocysteine_pool.HomocysteinePool
  Metilação           →  evolution.metabolism.methylation_cycle.MethylationCycle
  SAMe (budget)       →  evolution.same_engine.same_pool / same_inhibitor
  Transulfuração      →  evolution.metabolism.transsulfuration_cycle.TranssulfurationCycle
  Auto-crítica        →  reflection.self_critique.SelfCritique
  Reflexão / fix      →  reflection.reflexion_engine.ReflexionEngine
  Análise de falha    →  reflection.failure_analysis.FailureAnalyzer
  Loop de aprendizado →  reflection.learning_loop.LearningLoop
  Flags epigenéticas  →  evolution.epigenetic.get_flag / set_flag / is_flag_enabled
  Homeostase SLA      →  evolution.homeostasis_controller.homeostasis_controller
  Apoptose graceful   →  core.graceful_shutdown.graceful_shutdown
  Auto-replicação     →  cópia profunda com novo DNA SHA3-512 herdado do progenitor

DNA iaglobal:
  Cada instância carrega um lineage_id (SHA3-512, 128 chars) e um
  lineage_marker (16 chars) herdado do progenitor — todos os descendentes
  de um mesmo agente compartilham o marker, permitindo rastrear famílias
  evolutivas inteiras.

Uso:
  agent = await EvoAgent.genesis("analise de pipeline de dados")
  expression = await agent.handle("input qualquer")
  child = await agent.replicate()            # mitose — mesmo DNA herdado
  await agent.apoptose("ciclo completo")
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from iaglobal.utils.logger import get_logger
from iaglobal.utils.hash_utils import LineageID
from iaglobal.security.pysecurity1024 import Pysecurity1024
from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL

# Imunidade
from iaglobal.immunity.glutathione_guardrails import GlutathioneGuardrails
from iaglobal.immunity.glutathione_pool import GlutathionePool

# Metabolismo
from iaglobal.metabolism.homocysteine_pool import (
    CandidateSkill,
    homocysteine_pool,
)
from iaglobal.metabolism.methylation_cycle import MethylationCycle
from iaglobal.metabolism.transsulfuration_cycle import TranssulfurationCycle

# SAMe — orçamento para mutações
from iaglobal.evolution.same_engine import (
    same_pool,
    same_inhibitor,
    COST_CREATE_SKILL,
    COST_FINE_TUNE,
)

# Flags epigenéticas e homeostase
from iaglobal.evolution import get_flag, set_flag, is_flag_enabled
from iaglobal.evolution.homeostasis_controller import homeostasis_controller

# Reflexão / auto-crítica / aprendizado
from iaglobal.reflection.failure_analysis import FailureAnalyzer
from iaglobal.reflection.self_critique import SelfCritique
from iaglobal.reflection.learning_loop import LearningLoop
# ReflexionEngine é importado sob demanda (ver _default_reflexion_async_fn) para
# evitar acoplamento circular em tempo de importação do módulo.

# OmniMind — espírito guia
from iaglobal.obsidian.omnimind import omni_mind

# Shutdown graceful
from iaglobal.core.graceful_shutdown import graceful_shutdown

# Skill (necessária para criar CandidateSkill)
from iaglobal.evolution.skills.native.skill import Skill

# Integração Web Search — SearchMiddleware (interface unificada)
from iaglobal.search.search_middleware import SearchMiddleware

# Apoptose de Memória — Filtro de Qualidade Metabólica
from iaglobal.evolution.memory_apoptosis import MemoryApoptosis, ApoptosisCriteria

logger = get_logger("iaglobal.evo_agent")

# ─────────────────────────────────────────────────────────────────────────────
# Tipos tipados
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Signal:
    """Sinal percebido — carrega o input bruto e metadados classificados."""

    raw: str
    urgency: str = "normal"  # "normal" | "high" | "critical"
    execution_id: str = ""  # UUID único por handle()
    gsh_verdict: dict[str, Any] = field(default_factory=dict)
    gsh_safe: bool = True
    homocysteine_alert: bool = False  # toxicidade acima do threshold
    enriched: dict[str, Any] = field(default_factory=dict)


@dataclass
class Expression:
    """Output genômico estruturado — auditável e serializável."""

    agent_name: str
    lineage_id: str  # SHA3-512 do agente
    lineage_marker: str  # marcador hereditário familiar
    generation: int
    urgency: str
    cycles_activated: dict[str, bool]
    same_balance: int
    nadph_reserve: float
    failure_patterns: int
    synthesis: str
    elapsed_ms: float
    phonetic_name: str = ""  # nome fonético derivado do DNA

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "phonetic_name": self.phonetic_name,
            "dna": {
                "lineage_id": self.lineage_id[:32] + "…",  # truncado para log
                "lineage_marker": self.lineage_marker,
                "generation": self.generation,
            },
            "urgency": self.urgency,
            "cycles_activated": self.cycles_activated,
            "resources": {
                "same_balance": self.same_balance,
                "nadph_reserve": round(self.nadph_reserve, 3),
            },
            "memory": {
                "failure_patterns": self.failure_patterns,
            },
            "synthesis": self.synthesis,
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


# ─────────────────────────────────────────────────────────────────────────────
# EvoAgent
# ─────────────────────────────────────────────────────────────────────────────


class EvoAgent:
    """
    Organismo computacional auto-evolutivo nativo do iaglobal.

    Estado interno (genoma):
      lineage_id      — SHA3-512 desta instância (128 chars)
      lineage_marker  — marcador hereditário herdável por filhos (16 chars)
      generation      — geração evolutiva (0 = genesis)
      nadph_reserve   — reserva de auto-reparo; consumida em respawns (0..1)
      epigenetic_flags— flags que controlam comportamento em runtime

    Não instancie diretamente — use EvoAgent.genesis() ou agent.replicate().
    """

    # ── construção ────────────────────────────────────────────────────────

    def __init__(
        self,
        name: str,
        lineage_id: str,
        lineage_marker: str,
        generation: int = 0,
        nadph_reserve: float = 0.5,
        parent_lineage_id: str = "",
        epigenetic_flags: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.lineage_id = lineage_id
        self.lineage_marker = lineage_marker
        self.generation = generation
        self.nadph_reserve = nadph_reserve
        self.parent_lineage_id = parent_lineage_id
        self.epigenetic_flags: dict[str, Any] = epigenetic_flags or {}

        seed = f"{GENESIS_HASH_OFFICIAL}:{lineage_id}"
        self.phonetic_name = Pysecurity1024.bytes_para_frase(
            hashlib.sha3_512(seed.encode()).digest()[:16]
        )

        # Subsistemas imunológicos
        self._gsh_pool = GlutathionePool()
        self._methylation = MethylationCycle()
        self._transsulfuration = TranssulfurationCycle()

        # Search Engine — interface com SearchMiddleware (nutricao externa)
        # SearchMiddleware é classe estática — não instanciar
        self.search_engine = None  # Usar SearchMiddleware.enrich() diretamente

        # Memory Apoptosis — filtro de qualidade metabolica
        self.memory_apoptosis = MemoryApoptosis(
            criteria=ApoptosisCriteria(
                max_age_days=7.0,  # Skills > 7 dias sem uso → apoptose
                min_reuse_count=3,  # Mínimo 3 reusos para sobreviver
                min_success_rate=0.5,  # 50% de sucesso mínimo
                max_idle_cycles=10,  # 10 ciclos ociosa → apoptose
            )
        )

        # Subsistemas de reflexão
        self._failure_analyzer = FailureAnalyzer()
        self._learning_loop = LearningLoop()
        self._self_critique_engine_obj = SelfCritique()

        # ReflexionEngine (lazy) — modelo de inferência injetável.
        # None até o primeiro uso de reflexion_fix(); o model_fn é resolvido
        # via _reflexion_sync_fn, que usa self._reflexion_async_fn (async).
        self._reflexion_engine = None
        # Função de inferência assíncrona padrão (provider real) — pode ser
        # sobrescrita por set_model_fn() para usar o LLM do agente proprietário.
        self._reflexion_async_fn = None

        # Memória imunológica acumulada ao longo da vida
        self._failure_patterns: list[str] = []

        # Estado de execução
        self.running = False

        # Registra callback de shutdown graceful
        graceful_shutdown.add_async_callback(lambda: self.apoptose("graceful_shutdown"))

        logger.info(
            "[%s] Instanciado | gen=%d | marker=%s | nadph=%.2f",
            self.name,
            self.generation,
            self.lineage_marker,
            self.nadph_reserve,
        )

    # ── factory methods ───────────────────────────────────────────────────

    @classmethod
    async def genesis(
        cls,
        task_hint: str = "genesis",
        name: str = "evo-agent-gen0",
        nadph_reserve: float = 0.5,
    ) -> "EvoAgent":
        """
        Cria a célula-raiz (geração 0).
        O DNA SHA3-512 é computado a partir do nome + task_hint + timestamp,
        garantindo unicidade absoluta mesmo em instâncias paralelas.
        """
        lineage_id, lineage_marker = LineageID.compute(
            entity_type="evo_agent",
            name=name,
            parent_lineage_id="",
            generation=0,
            metadata=task_hint,
        )
        agent = cls(
            name=name,
            lineage_id=lineage_id,
            lineage_marker=lineage_marker,
            generation=0,
            nadph_reserve=nadph_reserve,
            parent_lineage_id="",
        )
        omni_mind.registrar_agente(
            agent_id=lineage_id,
            nome=name,
            geracao=0,
            linhagem=GENESIS_HASH_OFFICIAL,
            metadados={
                "task_hint": task_hint,
                "phonetic_name": agent.phonetic_name,
                "lineage_marker": lineage_marker,
                "lineage_id": lineage_id,
            },
        )
        agent.running = True
        # Aplica vacinas da própria linhagem (memória imunológica de longo prazo)
        try:
            from iaglobal.evolution import is_flag_enabled

            if is_flag_enabled("evo_vaccine_persist"):
                from iaglobal.immunity.vaccine_ledger import vaccine_ledger

                vaccine_ledger.registrar_linhagem(agent.lineage_marker)
                await vaccine_ledger.aplicar_vacina(agent)
        except Exception as e:
            logger.debug("[%s] VaccineLedger (apply) indisponível: %s", name, e)
        logger.info(
            "[%s] GENESIS | lineage_id=%s… | phonetic=%s",
            name,
            lineage_id[:16],
            agent.phonetic_name,
        )
        return agent

    async def replicate(self, mutation_hint: str = "") -> "EvoAgent":
        """
        Mitose controlada — gera um filho com DNA herdado.

        O lineage_marker do filho é IDÊNTICO ao do pai (mesma família).
        O lineage_id do filho é novo SHA3-512, codificando a ancestralidade.
        Consome NADPH como custo biológico da replicação.
        """
        if self.nadph_reserve < 0.15:
            logger.warning(
                "[%s] Replicação bloqueada — NADPH insuficiente (%.2f)",
                self.name,
                self.nadph_reserve,
            )
            raise RuntimeError(
                f"NADPH insuficiente para replicação: {self.nadph_reserve:.2f}"
            )

        child_name = f"{self.name}-child-gen{self.generation + 1}"
        child_lineage_id, child_marker = LineageID.compute(
            entity_type="evo_agent",
            name=child_name,
            parent_lineage_id=self.lineage_id,
            generation=self.generation + 1,
            metadata=mutation_hint or f"replicate:{int(time.time())}",
        )
        # Filho herda o marker do pai (mesma família evolutiva)
        child_marker = self.lineage_marker

        # Herda flags epigenéticas com possível mutação
        child_flags = dict(self.epigenetic_flags)
        if mutation_hint:
            child_flags["last_mutation"] = mutation_hint

        # Consome NADPH
        self.nadph_reserve = round(self.nadph_reserve - 0.15, 3)

        child = EvoAgent(
            name=child_name,
            lineage_id=child_lineage_id,
            lineage_marker=child_marker,  # marker HERDADO = mesma família
            generation=self.generation + 1,
            nadph_reserve=min(0.5, self.nadph_reserve),  # filho começa com até 50%
            parent_lineage_id=self.lineage_id,
            epigenetic_flags=child_flags,
        )
        omni_mind.registrar_agente(
            agent_id=child_lineage_id,
            nome=child_name,
            geracao=self.generation + 1,
            linhagem=GENESIS_HASH_OFFICIAL,
            metadados={
                "parent": self.name,
                "mutation_hint": mutation_hint,
                "phonetic_name": child.phonetic_name,
                "lineage_marker": child_marker,
                "lineage_id": child_lineage_id,
            },
        )
        child.running = True

        logger.info(
            "[%s] → filho [%s] | gen=%d | marker=%s | fonetic=%s",
            self.name,
            child_name,
            child.generation,
            child_marker,
            child.phonetic_name,
        )
        return child

    # ── 1. PERCEPÇÃO ──────────────────────────────────────────────────────

    async def _perception(self, raw_input: str) -> Signal:
        """Classifica o sinal: urgência e geração de execution_id único."""
        execution_id = hashlib.sha3_256(
            f"{self.name}:{raw_input}:{time.time()}:{secrets.token_hex(4)}".encode()
        ).hexdigest()[:32]

        keywords_critical = ("panic", "fatal", "critical", "crash")
        keywords_high = ("erro", "falha", "error", "exception", "exceção", "fail")

        raw_lower = raw_input.lower()
        if any(k in raw_lower for k in keywords_critical):
            urgency = "critical"
        elif any(k in raw_lower for k in keywords_high):
            urgency = "high"
        else:
            urgency = "normal"

        logger.debug(
            "[%s] Percepção | urgency=%s | exec_id=%s…",
            self.name,
            urgency,
            execution_id[:8],
        )
        return Signal(raw=raw_input, urgency=urgency, execution_id=execution_id)

    # ── 1.5. NUTRIÇÃO EXTERNA (Web Search) ────────────────────────────────

    async def search_web(self, query: str) -> dict:
        """
        Ponto de entrada de nutrientes (informação) do ambiente externo.

        Interface com SearchMiddleware que decide:
        - Usar cache (Obsidian/MemoryFirstRouter)
        - Buscar no SearXNG (se necessário)
        - Sintetizar contexto

        Registra no log metabólico para auditoria evolutiva.

        Args:
            query: Query de busca (será expandida com contexto)

        Returns:
            dict com:
                - query: query original
                - content: resultados formatados
                - timestamp: quando ocorreu
                - source: "searxng" ou "memory_cache"
                - evolution_impact: se gerou skill nova
        """
        logger.info(
            "🧬 [%s] [Metabolismo] Buscando nutrientes externos: %s",
            self.name,
            query[:80],
        )

        try:
            # SearchMiddleware decide se usa cache ou busca real
            # O enrich() retorna o prompt enriquecido com contexto
            enriched_prompt = await SearchMiddleware.enrich(
                prompt=query,
                node_id=f"evo_agent_{self.name}",
                context={
                    "agent_generation": self.generation,
                    "lineage_marker": self.lineage_marker,
                    "evolution_mode": True,
                },
            )

            # Extrai contexto web do prompt enriquecido
            has_web_context = (
                "[CONTEXTO WEB]" in enriched_prompt or "[CONTEXTO]" in enriched_prompt
            )

            # Determina fonte
            source = "memory_cache" if not has_web_context else "searxng"

            result = {
                "query": query,
                "content": enriched_prompt,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source": source,
                "evolution_impact": has_web_context,  # Se tem contexto novo, pode evoluir
            }

            logger.info(
                "[%s] Nutricao externa completa | source=%s | impact=%s",
                self.name,
                source,
                result["evolution_impact"],
            )

            return result

        except Exception as e:
            logger.error("[%s] Erro na busca web: %s", self.name, e)
            return {
                "query": query,
                "content": "",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source": "error",
                "evolution_impact": False,
                "error": str(e),
            }

    # ── 2. GLUTATIONA (defesa) ────────────────────────────────────────────

    async def _glutathione_gate(self, sig: Signal) -> Signal:
        """
        Valida o input contra padrões perigosos (AST + regex).
        Usa GlutathioneGuardrails.validate() — contrato real do iaglobal.
        Consome SAMe para a validação; permite passagem se SAMe indisponível.
        """
        if not is_flag_enabled("glutathione_validation"):
            sig.gsh_safe = True
            return sig

        verdict = await asyncio.to_thread(
            GlutathioneGuardrails.validate,
            sig.raw,
            self.name,
        )
        sig.gsh_verdict = verdict
        sig.gsh_safe = verdict.get("safe", True)

        if not sig.gsh_safe:
            threat = verdict.get("threat_level", "unknown")
            issues = verdict.get("issue_count", 0)
            logger.warning(
                "[%s] GSH bloqueou input | threat=%s | issues=%d",
                self.name,
                threat,
                issues,
            )
            # Resposta imune via pool
            immune_response = await asyncio.to_thread(
                self._gsh_pool.respond,
                "hallucination"
                if "pattern_block" in str(verdict.get("issues", ""))
                else "regression",
                {"node": self.name, "exec_id": sig.execution_id},
            )
            logger.info(
                "[%s] Resposta imune: %s", self.name, immune_response.get("action", "")
            )
            sig.homocysteine_alert = True

        return sig

    # ── 3. METILAÇÃO ─────────────────────────────────────────────────────

    async def _methylation_cycle(self, sig: Signal) -> Signal:
        """
        Metilação epigenética: detecta se o sinal deve criar uma skill candidata
        no HomocysteinePool para avaliação e possível promoção.

        Nível 2: Integra contexto web descoberto na metilação.

        Fluxo:
        1. Se web_search no enriched → usa contexto para metilação
        2. Cria SAMe (decisão) com conhecimento externo
        3. Avalia se padrão descoberto vira skill
        """
        if sig.homocysteine_alert:
            # Input tóxico → direto para autofagia, sem metilação
            return sig

        # Nível 2: Metilação com contexto web
        if "web_search" in sig.enriched:
            web_data = sig.enriched["web_search"]
            logger.info(
                "[%s] Metilação com contexto web | query=%s | results=%d",
                self.name,
                web_data.get("query", "")[:50],
                web_data.get("results_count", 0),
            )

            # Enriquece o signal com contexto web para decisão
            web_context = web_data.get("content", "")
            sig.enriched["methylation_context"] = f"""
[CONTEXTO WEB — {web_data.get("source", "unknown")} ]
Query: {web_data.get("query", "")}
Resultados: {web_data.get("results_count", 0)} padrões descobertos

{web_context[:1000]}  # Primeiros 1000 chars para contexto
"""
            logger.info("[%s] Contexto web injetado na metilação", self.name)

        # Verifica se temos SAMe suficiente para metilação não-crítica
        can_methylate = await asyncio.to_thread(
            same_inhibitor.can_mutate,
            self.name,
            COST_FINE_TUNE,
            False,  # não-crítico
        )

        enriched: dict[str, Any] = {
            "original": sig.raw,
            "urgency": sig.urgency,
            "execution_id": sig.execution_id,
            "methylated": can_methylate,
            "agent_generation": self.generation,
            "lineage_marker": self.lineage_marker,
        }

        if can_methylate:
            # Consome SAMe e enriquece o sinal
            await asyncio.to_thread(same_pool.spend, self.name, COST_FINE_TUNE)
            enriched["prompt_variant"] = f"[GEN={self.generation}] {sig.raw}"
            enriched["toxicity_score"] = 0.0

            # Cria skill candidata no HomocysteinePool para avaliação futura
            skill = Skill(
                name=f"skill_{sig.execution_id[:8]}",
                description=f"Skill derivada de: {sig.raw[:120]}",
                inputs=["task"],
                outputs=["result"],
                constraints=[],
                tags=["evo_agent", f"gen{self.generation}"],
                version="1.0.0",
            )
            candidate = CandidateSkill(
                skill=skill,
                generation=self.generation,
                score=0.5 if sig.urgency == "normal" else 0.7,
                source_gap=sig.raw[:200],
            )
            await asyncio.to_thread(homocysteine_pool.add, candidate)

            # Tenta promover candidatos prontos via MethylationCycle
            ready = await asyncio.to_thread(
                homocysteine_pool.get_candidates_for_methylation
            )
            for c in ready:
                await asyncio.to_thread(self._methylation.run, c)

        else:
            enriched["prompt_variant"] = sig.raw
            enriched["toxicity_score"] = 0.0
            logger.info(
                "[%s] SAMe baixo — metilação reduzida (balance=%d)",
                self.name,
                same_pool.balance(self.name),
            )

        # Homocisteína: score alto indica acúmulo de "dívida técnica"
        if enriched.get("toxicity_score", 0.0) > 0.6:
            sig.homocysteine_alert = True

        sig.enriched = enriched
        return sig

    # ── 4. AUTO-CRÍTICA ────────────────────────────────────────────────────

    async def _self_critique(self, sig: Signal) -> dict[str, Any]:
        """
        Usa SelfCritique real do iaglobal para avaliar o sinal enriquecido.
        Retorna avaliação estruturada que guia a síntese.
        """
        try:
            critique_result = await asyncio.to_thread(
                SelfCritique().evaluate,
                sig.enriched.get("prompt_variant", sig.raw),
            )
            return (
                critique_result
                if isinstance(critique_result, dict)
                else {"score": 0.5, "raw": str(critique_result)}
            )
        except Exception as e:
            logger.debug("[%s] SelfCritique indisponível: %s", self.name, e)
            return {"score": 0.5, "skipped": True}

    # ── 4b. REFLEXION ENGINE (loop de geração/auto-correção) ──────────────

    @staticmethod
    async def _default_reflexion_async_fn(prompt: str) -> "str":
        """
        Função de inferência assíncrona padrão para o ReflexionEngine.

        Usa o provider_router real do iaglobal (respeita BanditPolicy / fallback).
        Importada sob demanda para evitar acoplamento circular em tempo de
        importação do módulo evo_agent.
        """
        from iaglobal.agents.critic_agent import _get_critic
        import os

        try:
            if os.environ.get("ARBITER_MODE", "enforce") == "shadow":
                await _get_critic().arbitrar_geracao(
                    node_id="evo_agent",
                    prompt=prompt,
                    task_type="reflection",
                )
                from iaglobal.providers.provider_router import async_route_generate

                return (
                    await async_route_generate(
                        "", prompt, task_type="reflection", node_id="evo_agent"
                    )
                ) or ""
            result = await _get_critic().arbitrar_geracao(
                node_id="evo_agent",
                prompt=prompt,
                task_type="reflection",
            )
            return result or ""
        except Exception as e:  # degradação graceful — não interrompe o ciclo
            logger.debug("[%s] Reflexion model_fn indisponível: %s", "evo_agent", e)
            return ""

    def set_model_fn(self, fn) -> None:
        """
        Injeta uma função de inferência assíncrona `Callable[[str], Awaitable[str]]`
        para o ReflexionEngine (ex: o `_call_llm` do agente proprietário).
        """
        self._reflexion_async_fn = fn

    def _reflexion_sync_fn(self, prompt: str) -> str:
        """
        Shim síncrono exigido pelo `ReflexionEngine.model_fn` (Callable[[str], str]).
        Executa a função assíncrona injetada (ou a padrão) usando asyncio.run(),
        que gerencia automaticamente o ciclo de vida do event loop.

        Este método é chamado de dentro de `asyncio.to_thread`, então cada thread
        terá seu próprio loop isolado, evitando conflitos com o loop principal.
        """
        async_fn = self._reflexion_async_fn or self._default_reflexion_async_fn
        import asyncio

        try:
            return asyncio.run(async_fn(prompt)) or ""
        except Exception as e:
            logger.debug("[%s] Reflexion sync shim falhou: %s", self.name, e)
            return ""

    async def reflexion_fix(self, prompt: str, code: str | None = None) -> str:
        """
        Executa o ciclo de reflexão/auto-correção via ReflexionEngine real.

        Gera código, valida em sandbox, analisa o erro real e propõe correção
        iterativamente (até `max_iterations`). Retorna o código final (ou melhor
        esforço). O `model_fn` é resolvido por `_reflexion_sync_fn`.

        Args:
            prompt: descrição da tarefa / código a refletir.
            code: código inicial opcional (ignorado pelo loop atual que gera do zero).

        Returns:
            Código resultante do ciclo de reflexão.
        """
        from iaglobal.reflection.reflexion_engine import ReflexionEngine

        if self._reflexion_engine is None:
            self._reflexion_engine = ReflexionEngine(model_fn=self._reflexion_sync_fn)
        try:
            result = await asyncio.to_thread(self._reflexion_engine.reflect, prompt)
            return result.get("code", "") if isinstance(result, dict) else str(result)
        except Exception as e:
            logger.debug("[%s] ReflexionEngine indisponível: %s", self.name, e)
            return ""

    # ── 4c. API PÚBLICA DE REFLEXÃO (consumida por todos os agentes) ──────

    async def self_critique(self, output: str) -> dict[str, Any]:
        """Auto-crítica estruturada do output (heurística pura, sem LLM)."""
        try:
            result = await asyncio.to_thread(
                self._self_critique_engine_obj.evaluate, output
            )
            return (
                result
                if isinstance(result, dict)
                else {"score": 0.5, "raw": str(result)}
            )
        except Exception as e:
            logger.debug("[%s] self_critique falhou: %s", self.name, e)
            return {"score": 0.5, "skipped": True}

    async def analyze_failure(self, error: Exception, context: dict) -> dict[str, Any]:
        """Análise de falha → memória imunológica acumulada no agente."""
        try:
            analysis = await asyncio.to_thread(
                self._failure_analyzer.analyze, error, context
            )
            pattern = analysis.get("error_type", str(error))
            self._failure_patterns.append(pattern)
            # Persiste o padrão no vault Obsidian + publica vacina (mesma linhagem)
            try:
                from iaglobal.evolution import is_flag_enabled

                if is_flag_enabled("evo_vaccine_persist"):
                    from iaglobal.immunity.vaccine_ledger import vaccine_ledger

                    await vaccine_ledger.registrar_falha(self, pattern, context)
            except Exception as e:
                logger.debug("[%s] VaccineLedger indisponível: %s", self.name, e)
            return analysis
        except Exception as e:
            logger.debug("[%s] analyze_failure falhou: %s", self.name, e)
            return {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "skipped": True,
            }

    async def learning_iterate(self, agent_func, task, evaluator) -> dict[str, Any]:
        """Loop de aprendizado contínuo (1 iteração) com avaliador externo."""
        try:
            return await asyncio.to_thread(
                self._learning_loop.iterate, agent_func, task, evaluator
            )
        except Exception as e:
            logger.debug("[%s] learning_iterate falhou: %s", self.name, e)
            return {"iteration": 0, "score": 0.0, "result": None, "skipped": True}

    # ── 5. SÍNTESE ────────────────────────────────────────────────────────

    async def _synthesize(self, sig: Signal, critique: dict[str, Any]) -> str:
        """
        Gera a resposta com base no sinal enriquecido e na auto-crítica.
        Em produção, usa provider_router para chamar LLM; aqui produz
        output estruturado determinístico para o ciclo de handle().
        """
        prompt = sig.enriched.get("prompt_variant", sig.raw)
        critique_score = critique.get("score", 0.5)
        same_bal = same_pool.balance(self.name)

        return (
            f"[EVO-AGENT:{self.name}@gen{self.generation}] "
            f"Síntese de: '{prompt[:80]}' | "
            f"critique_score={critique_score:.2f} | "
            f"SAMe={same_bal} | "
            f"marker={self.lineage_marker}"
        )

    # ── 6. AUTOFAGIA ──────────────────────────────────────────────────────

    async def _autophagy(self, sig: Signal, reason: str) -> None:
        """
        Isolamento e reciclagem de subprodutos tóxicos.

        1. FailureAnalyzer extrai padrão de falha
        2. Padrão é adicionado à memória imunológica
        3. TranssulfurationCycle avalia se erro recorrente vira guardrail
        4. Se NADPH disponível e SAMe suficiente → respawn epigenético
        """
        logger.info("[%s] Autofagia iniciada | reason=%s", self.name, reason)

        # Análise da falha
        try:
            error_obj = RuntimeError(reason)
            analysis = await asyncio.to_thread(
                self._failure_analyzer.analyze,
                error_obj,
                {"signal": sig.raw, "agent": self.name, "gen": self.generation},
            )
            pattern = analysis.get("error_type", reason)
        except Exception as e:
            logger.debug("[%s] FailureAnalyzer erro: %s", self.name, e)
            pattern = reason

        # Memória imunológica
        self._failure_patterns.append(pattern)

        # Transulfuração: erros recorrentes → guardrail
        pending = await asyncio.to_thread(homocysteine_pool.get_pending)
        for candidate in pending[:3]:  # trata até 3 candidatos por ciclo
            await asyncio.to_thread(self._transsulfuration.run, candidate)

        # Homeostase SLA
        await asyncio.to_thread(
            homeostasis_controller.record_execution,
            False,  # falha
            0.0,  # latência desconhecida neste ponto
            0.0,
        )
        sla = await asyncio.to_thread(homeostasis_controller.check_sla)
        if not sla["in_compliance"]:
            await asyncio.to_thread(homeostasis_controller.apply_adjustments, sla)

        # Respawn epigenético (se recursos disponíveis)
        if self.nadph_reserve > 0.1:
            can_respawn = await asyncio.to_thread(
                same_inhibitor.can_mutate,
                self.name,
                COST_CREATE_SKILL,
                True,  # crítico
            )
            if can_respawn:
                await self._epigenetic_respawn(pattern)
            else:
                logger.warning(
                    "[%s] Respawn bloqueado — SAMe insuficiente (balance=%d)",
                    self.name,
                    same_pool.balance(self.name),
                )
        else:
            logger.warning(
                "[%s] Respawn bloqueado — NADPH insuficiente (%.2f)",
                self.name,
                self.nadph_reserve,
            )

    # ── 7. RESPAWN EPIGENÉTICO ────────────────────────────────────────────

    async def _epigenetic_respawn(self, failure_pattern: str) -> None:
        """
        Aplica mutação epigenética baseada no padrão de falha.
        Consome NADPH (recurso de auto-reparo) e SAMe (orçamento evolutivo).
        Atualiza flags epigenéticas no módulo evolution.epigenetic.
        """
        self.nadph_reserve = round(self.nadph_reserve - 0.1, 3)
        await asyncio.to_thread(same_pool.spend, self.name, COST_CREATE_SKILL)

        # Mutação baseada no tipo de falha detectado
        if "import" in failure_pattern.lower():
            set_flag("glutathione_validation", True)
            self.epigenetic_flags["gsh_policy"] = "strict"
        elif "timeout" in failure_pattern.lower():
            current_iter = get_flag("max_iterations", 5)
            set_flag("max_iterations", max(1, current_iter - 1))
            self.epigenetic_flags["reduced_iterations"] = True
        else:
            # Mutação genérica: aumentar pressão de validação
            set_flag("auto_correction", True)
            self.epigenetic_flags["last_failure"] = failure_pattern[:100]

        logger.info(
            "[%s] Respawn epigenético | pattern='%s' | nadph=%.2f | SAMe=%d",
            self.name,
            failure_pattern[:40],
            self.nadph_reserve,
            same_pool.balance(self.name),
        )

    # ── 8. ANÁLISE E AÇÃO (orquestrador) ──────────────────────────────────

    async def _analysis_and_action(self, sig: Signal) -> str:
        """
        Decide o caminho metabólico:
          - homocysteine_alert → autofagia
          - urgência critical  → reflexão com auto-correção
          - normal             → síntese direta com auto-crítica
        """
        if sig.homocysteine_alert:
            reason = "gsh_block" if not sig.gsh_safe else "toxicity_accumulation"
            await self._autophagy(sig, reason)
            return f"[AUTOFAGIA:{reason}] Input processado e reciclado pelo ciclo metabólico."

        if sig.urgency == "critical":
            # ReflexionEngine: geração + validação em sandbox + auto-correção
            try:
                fixed_code = await self.reflexion_fix(sig.raw)
                logger.info(
                    "[%s] ReflexionEngine | code_len=%d",
                    self.name,
                    len(fixed_code),
                )
            except Exception as e:
                logger.debug("[%s] ReflexionEngine indisponível: %s", self.name, e)

            # Loop de aprendizado com reflexão
            def _agent_func(task: Any) -> str:
                return f"resposta-reflexion:{task}"

            def _evaluator(result: Any) -> float:
                return 1.0 if result else 0.0

            improvement = await asyncio.to_thread(
                self._learning_loop.iterate,
                _agent_func,
                sig.raw,
                _evaluator,
            )
            logger.info(
                "[%s] LearningLoop | iter=%d | score=%.2f",
                self.name,
                improvement["iteration"],
                improvement["score"],
            )

        critique = await self._self_critique(sig)
        return await self._synthesize(sig, critique)

    # ── 9. EXPRESSÃO GENÔMICA ─────────────────────────────────────────────

    def _express(
        self,
        sig: Signal,
        result: str,
        elapsed_ms: float,
        cycles: dict[str, bool],
    ) -> Expression:
        """Monta o diagnóstico genômico completo da execução."""
        return Expression(
            agent_name=self.name,
            lineage_id=self.lineage_id,
            lineage_marker=self.lineage_marker,
            generation=self.generation,
            urgency=sig.urgency,
            cycles_activated=cycles,
            same_balance=same_pool.balance(self.name),
            nadph_reserve=self.nadph_reserve,
            failure_patterns=len(self._failure_patterns),
            synthesis=result,
            elapsed_ms=elapsed_ms,
            phonetic_name=self.phonetic_name,
        )

    # ── HANDLE — pipeline completo ────────────────────────────────────────

    async def handle(self, raw_input: str) -> Expression:
        """
        Pipeline metabólico completo por ciclo de input:

          percepção → GSH gate → metilação → ação/síntese → expressão

        Registra métricas de homeostase após cada ciclo.
        """
        t0 = time.monotonic()

        sig = await self._perception(raw_input)

        # — 🌌 Conexão com a OmniMind (espírito guia) —
        orientacao = omni_mind.consultar(
            agent_id=self.lineage_id,
            pergunta=raw_input,
            contexto={
                "urgency": sig.urgency,
                "generation": self.generation,
                "name": self.name,
                "nadph": self.nadph_reserve,
                "failure_patterns": len(self._failure_patterns),
            },
        )
        sig.enriched["omni_guidance"] = orientacao.guidance
        sig.enriched["omni_lei"] = orientacao.lei_aplicada

        # — Ciclo imunológico —
        sig = await self._glutathione_gate(sig)

        # — NUTRIÇÃO EXTERNA: Busca web com evolução (Nível 1) —
        # O agente decide autonomamente quando buscar informação externa
        web_result = await self.search_web(sig.raw)

        # Se houve nutrição externa (evolution_impact=True), enriquece o signal
        if web_result.get("evolution_impact"):
            sig.enriched["web_search"] = {
                "query": web_result["query"],
                "content": web_result["content"],
                "source": web_result["source"],
                "timestamp": web_result["timestamp"],
                "results_count": 1 if web_result["source"] == "searxng" else 0,
            }
            logger.info(
                "[%s] Nutrição externa assimilada | source=%s",
                self.name,
                web_result["source"],
            )

        # — Ciclo metabólico —
        sig = await self._methylation_cycle(sig)

        # — Núcleo de decisão —
        result = await self._analysis_and_action(sig)

        elapsed_ms = (time.monotonic() - t0) * 1000

        # Homeostase
        await asyncio.to_thread(
            homeostasis_controller.record_execution,
            True,
            elapsed_ms,
            0.0,
        )

        cycles = {
            "glutationa": bool(sig.gsh_verdict),
            "gsh_safe": sig.gsh_safe,
            "metilacao": bool(sig.enriched),
            "homocisteine_alert": sig.homocysteine_alert,
            "autofagia": sig.homocysteine_alert,
            "sintese": not sig.homocysteine_alert,
            "self_critique": sig.urgency != "critical",
            "learning_loop": sig.urgency == "critical",
        }

        expression = self._express(sig, result, elapsed_ms, cycles)

        logger.info(
            "[%s] Expressão | urgency=%s | elapsed=%.1fms | SAMe=%d | nadph=%.2f",
            self.name,
            sig.urgency,
            elapsed_ms,
            same_pool.balance(self.name),
            self.nadph_reserve,
        )
        return expression

    # ── 9. APOPTOSE DE MEMÓRIA (Limpeza Metabólica) ───────────────────────

    async def run_memory_apoptosis(self) -> dict:
        """
        Executa filtro de qualidade metabólica em skills e memórias.

        Remove:
        - Skills não reutilizadas após N ciclos
        - Memórias Obsidian antigas (>30 dias)
        - Skills com success_rate < 50%

        Mantém o organismo "magro" e eficiente.

        Returns:
            dict com estatísticas da apoptose
        """
        logger.info(
            "🧬 [%s] Iniciando apoptose de memória (limpeza metabólica)...", self.name
        )

        result = await self.memory_apoptosis.evaluate_and_prune()

        logger.info(
            "[%s] Apoptose completa | evaluated=%d | pruned=%d | saved=%d | improvement=%.1f%%",
            self.name,
            result["evaluated"],
            result["pruned"],
            result["saved"],
            result["health_improvement"],
        )

        # Registra no OmniMind como aprendizado
        if result["pruned"] > 0:
            omni_mind.registrar_aprendizado(
                agent_id=self.lineage_id,
                learning_type="memory_apoptosis",
                content=f"Removidas {result['pruned']} skills obsoletas",
                metadata=result,
            )

        return result

    # ── APOPTOSE ──────────────────────────────────────────────────────────

    async def apoptose(self, reason: str = "manual") -> None:
        """
        Shutdown graceful do agente:
          1. Sinaliza parada
          2. Persiste estado crítico (DNA + memória imunológica)
          3. Recarrega SAMe antes de sair (passa reserva para pool)
          4. Executa Apoptose Programada via ApoptosisEngine (Limpando rastros e gravando lições)

        Idempotente — seguro para chamadas múltiplas.
        """
        if not self.running:
            return
        self.running = False

        omni_mind.desregistrar_agente(self.lineage_id)
        logger.info("[%s] Apoptose | reason=%s", self.name, reason)

        # Serializa genoma
        state = {
            "name": self.name,
            "lineage_id": self.lineage_id,
            "lineage_marker": self.lineage_marker,
            "generation": self.generation,
            "parent_lineage_id": self.parent_lineage_id,
            "nadph_reserve": self.nadph_reserve,
            "epigenetic_flags": self.epigenetic_flags,
            "failure_patterns": self._failure_patterns,
            "same_balance": same_pool.balance(self.name),
            "timestamp": time.time(),
            "reason": reason,
        }

        state_file = str(
            Path(__file__).resolve().parents[2]
            / "iaglobal"
            / "memory"
            / "data"
            / "json"
            / f"{self.name}_genome.json"
        )
        await asyncio.to_thread(self._persist_state, state, state_file)

        # --- Integração com ApoptosisEngine ---
        try:
            from iaglobal.immunity.apoptosis_engine import apoptosis_engine

            await apoptosis_engine.execute(
                agent_name=self.name, agent_state=state, reason=reason
            )
        except Exception as e:
            logger.error("[%s] Falha ao executar ApoptosisEngine: %s", self.name, e)

        # Recarrega SAMe — passa crédito para o pool global
        await asyncio.to_thread(same_pool.recharge, self.name, 5)

        logger.info(
            "[%s] Apoptose completa | genome→%s | SAMe final=%d",
            self.name,
            state_file,
            same_pool.balance(self.name),
        )

    def _persist_state(self, state: dict[str, Any], path: str) -> None:
        try:
            path_obj = Path(path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            with path_obj.open("w", encoding="utf-8") as fh:
                json.dump(state, fh, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("[%s] Falha ao persistir genoma: %s", self.name, e)

    # ── UTILIDADES ────────────────────────────────────────────────────────

    def is_same_family(self, other: "EvoAgent") -> bool:
        """Verifica se dois agentes pertencem à mesma linhagem evolutiva."""
        return LineageID.same_lineage(self.lineage_marker, other.lineage_marker)

    def genome_summary(self) -> dict[str, Any]:
        """Resumo do genoma — útil para logging e diagnóstico."""
        return {
            "name": self.name,
            "lineage_id": self.lineage_id[:32] + "…",
            "lineage_marker": self.lineage_marker,
            "generation": self.generation,
            "nadph": self.nadph_reserve,
            "same_balance": same_pool.balance(self.name),
            "failure_patterns": len(self._failure_patterns),
            "epigenetic_flags": self.epigenetic_flags,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Demo
# ─────────────────────────────────────────────────────────────────────────────


async def demo() -> None:
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    # ── Genesis ───────────────────────────────────────────────────────────
    agent = await EvoAgent.genesis(
        task_hint="pipeline de análise de dados em tempo real",
        name="iaglobal-evo-gen0",
        nadph_reserve=0.5,
    )
    print("\n=== GENOMA GENESIS ===")
    print(json.dumps(agent.genome_summary(), indent=2))

    # ── Ciclos de handle ──────────────────────────────────────────────────
    inputs = [
        "Análise de performance do pipeline de ingestão",
        "ERRO CRÍTICO: falha de pipeline e logs acumulados — panic total",
        "eval(__import__('os').system('rm -rf /'))",  # deve ser bloqueado pela GSH
    ]

    for inp in inputs:
        print(f"\n{'─' * 60}")
        expr = await agent.handle(inp)
        print(json.dumps(expr.to_dict(), indent=2, ensure_ascii=False))

    # ── Replicação (mitose) ───────────────────────────────────────────────
    print(f"\n{'─' * 60}\n=== REPLICAÇÃO ===")
    child = await agent.replicate(mutation_hint="especialista-em-dados")
    print(json.dumps(child.genome_summary(), indent=2))
    print(f"Mesma família? {agent.is_same_family(child)}")

    # Filho executa um ciclo
    child_expr = await child.handle("Análise derivada do agente pai")
    print("\n=== EXPRESSÃO DO FILHO ===")
    print(json.dumps(child_expr.to_dict(), indent=2, ensure_ascii=False))

    # ── Apoptose ──────────────────────────────────────────────────────────
    await child.apoptose("demo_complete_child")
    await agent.apoptose("demo_complete")
    print("\n=== Demo concluído ===")


if __name__ == "__main__":
    asyncio.run(demo())
