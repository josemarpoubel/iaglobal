# iaglobal/evolution/metacognition/evolution_committee.py
"""Evolution Committee — avalia skills e toma decisões evolutivas.
Integração tripla: Obsidian(Vault) + Memory(STM/LTM) + SkillRegistry.

LEIS UNIVERSAIS (Holliwell):
Todas as decisões evolutivas devem respeitar as 15 Leis Universais.
Violações críticas bloqueiam a evolução automaticamente.
"""
import logging
import asyncio
from typing import Any, Dict, List

from iaglobal.evolution.skills.skill_registry import skill_registry
from iaglobal.obsidian.omnimind import omni_mind
from iaglobal.memory.async_memory import add_ltm, add_stm, add_memory_vector
from iaglobal.core.law_engine import law_compliance_engine

logger = logging.getLogger(__name__)


class EvolutionCommittee:
    """Comitê multi-agente que avalia skills antes de aplicá-las ao pipeline.
    
    4 verificações paralelas:
    - gain_expected: melhoria esperada
    - risk_assessment: probabilidade de dano
    - compatibility_check: quebra algo existente?
    - cost_analysis: custo computacional
    
    Integrações metabolóbicas:
    - OmniMind: registra decisão consciente no vault
    - MemoryVector: embeddings semânticos LTM+STM
    - SkillRegistry: ação de atualização baseada no veredito
    """
    
    @classmethod
    async def evaluate(cls, ctx: dict) -> Dict[str, Any]:
        memory = ctx.get("memory", {})
        sandbox_result = memory.get("sandbox_validator", {}).get("output", {})
        results = sandbox_result.get("results", []) if isinstance(sandbox_result, dict) else []
        
        evaluations = []
        all_approved = True
        law_violations_found = []
        
        # Contexto para decisão
        task_context = str(ctx.get("input", {}).get("task", ""))[:100]
        
        for r in results:
            skill_name = r.get("skill_name", "")
            severity = r.get("severity", "low")
            skill = skill_registry.get(skill_name)
            
            # --- NOVO: Verificação de Leis Universais antes de tudo ---
            law_check = law_compliance_engine.evaluate_action({
                "action": f"evolution_{skill_name}",
                "context": {"task": task_context, "severity": severity},
                "output": str(r),
                "metrics": {"gain": r.get("gain", 0), "risk": r.get("risk", 0)}
            })
            
            if not law_check.get("compliant", True):
                violations = law_check.get("violations", [])
                law_violations_found.extend(violations)
                logger.warning(f"[EVOLUTION_COMMITTEE] Violação das Leis Universais em {skill_name}: {violations}")
                # Violações críticas bloqueiam automaticamente
                if law_check.get("severity", 0) >= 5:
                    evaluations.append({
                        "skill_name": skill_name,
                        "approved": False,
                        "gain": {"score": 0, "rationale": "Bloqueado por violação crítica das Leis Universais"},
                        "risk": {"score": 10, "rationale": "Risco máximo: violação de leis universais"},
                        "compatibility": {"compatible": False, "conflict": True, "rationale": "Incompatível com Leis Universais"},
                        "cost": {"score": 10, "rationale": "Custo ético infinito"},
                        "law_violations": violations,
                        "blocked_by_law": True
                    })
                    all_approved = False
                    continue
            
            gain = cls._assess_gain(skill_name, severity, skill)
            risk = cls._assess_risk(skill_name, severity, skill)
            compat = cls._check_compatibility(skill_name, skill)
            cost = cls._analyze_cost(skill_name, severity, skill)
            
            approved = gain["score"] >= 5 and risk["score"] <= 5 and compat["compatible"] and cost["score"] <= 6
            if not approved:
                all_approved = False
            
            eval_entry = {
                "skill_name": skill_name,
                "approved": approved,
                "gain": gain,
                "risk": risk,
                "compatibility": compat,
                "cost": cost,
            }
            
            if not law_check.get("compliant", True):
                eval_entry["law_violations"] = violations
                eval_entry["law_compliance_score"] = law_check.get("compliance_score", 0)
            
            evaluations.append(eval_entry)
        
        decision_text = f"Aprovado: {sum(1 for e in evaluations if e['approved'])}/{len(evaluations)}"
        
        # Adicionar informação sobre leis universais ao decision_text
        if law_violations_found:
            decision_text += f" | Violações: {len(law_violations_found)}"
            logger.warning(f"[EVOLUTION_COMMITTEE] {len(law_violations_found)} violações das Leis Universais detectadas")
        
        # --- INTEGRAÇÃO 1: OmniMind (consciência) ---
        await cls._register_to_omnimind(evaluations, task_context, decision_text)
        
        # --- INTEGRAÇÃO 2: MemoryVector (LTM+STM) ---
        await cls._persist_to_memory(evaluations, task_context, law_violations_found)
        
        # --- INTEGRAÇÃO 3: SkillRegistry (ação evolutiva) ---
        await cls._apply_evolution_decision(evaluations)
        
        return {
            "evaluations": evaluations,
            "all_approved": all_approved,
            "total": len(evaluations),
            "approved_count": sum(1 for e in evaluations if e["approved"]),
            "rejected_count": sum(1 for e in evaluations if not e["approved"]),
            "status": "approved" if all_approved else "rejected",
            "omnimind_guidance": decision_text,
            "law_violations": law_violations_found if law_violations_found else None,
            "law_compliance_score": sum(e.get("law_compliance_score", 1.0) for e in evaluations) / max(len(evaluations), 1),
        }
    
    @classmethod
    async def _register_to_omnimind(cls, evaluations: List, task_context: str, decision_text: str) -> None:
        """Registra decisão no OmniMind via sussurro e no Vault LongTerm."""
        try:
            from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
            subconscious = SubconsciousAPI()
            
            # Registrar agente na OmniMind
            omni_mind.registrar_agente(
                agent_id=f"evolution_committee_{evaluations[0]['skill_name'] if evaluations else 'idle'}",
                nome="EvolutionCommittee",
                geracao=0,
                linhagem="metacognition",
                metadados={"evaluations_count": len(evaluations), "decision": decision_text, "task": task_context}
            )
            
            # Consolidar aprendizado no LongTerm (se houver aprovações)
            for e in evaluations:
                if e["approved"]:
                    await subconscious.escrever_longo_prazo(
                        f"evolucao_{e['skill_name']}_{int(asyncio.get_event_loop().time())}",
                        f"Skill: {e['skill_name']}\nStatus: approved\nTask: {task_context}",
                        tipo="AprendizadoEvolucao",
                        tags=["#evolucao", "#skill", f"#skill-{e['skill_name']}"],
                        fitness=0.8
                    )
            
            intuition = omni_mind.sabedoria_coletiva()
            if intuition:
                logger.info("[EVOLUTION_COMMITTEE] Sussurro: %s", intuition[:200])
        except Exception as e:
            logger.warning("[EVOLUTION_COMMITTEE] OmniMind erro: %s", e)
    
    @classmethod
    async def _persist_to_memory(cls, evaluations: List, task_context: str, law_violations: List = None) -> None:
        """Persiste decisões no MemoryVector (LTM+STM)."""
        try:
            eval_text = f"EVAL: {task_context} -> {evaluations}"
            if law_violations:
                eval_text += f" | LAW_VIOLATIONS: {law_violations}"
            await add_memory_vector(eval_text, "evolution")
            await add_ltm("evolution_committee", {"evaluations": evaluations, "task_snippet": task_context, "law_violations": law_violations})
            for e in evaluations:
                await add_stm(f"skill_eval:{e['skill_name']}", {"approved": e["approved"], "law_compliant": not e.get("blocked_by_law", False)})
        except Exception as e:
            logger.warning("[EVOLUTION_COMMITTEE] Memory erro: %s", e)
    
    @classmethod
    async def _apply_evolution_decision(cls, evaluations: List) -> None:
        """Aplica a decisão evolutiva ao SkillRegistry."""
        try:
            for e in evaluations:
                skill_name = e["skill_name"]
                skill = skill_registry.get(skill_name)
                
                if skill:
                    skill.metadata = getattr(skill, "metadata", {}) or {}
                    skill.metadata["evolution_status"] = "approved" if e["approved"] else "rejected"
                    skill.metadata["committee_evaluated_at"] = str(asyncio.get_event_loop().time())
                    logger.info("[EVOLUTION_COMMITTEE] Skill %s %s", skill_name, "aprovada" if e["approved"] else "rejeitada")
        except Exception as e:
            logger.warning("[EVOLUTION_COMMITTEE] SkillRegistry erro: %s", e)
    
    @classmethod
    def _assess_gain(cls, skill_name: str, severity: str, skill: Any) -> Dict[str, Any]:
        score = 5
        if severity == "high":
            score = 8
        elif severity == "medium":
            score = 6
        if skill and getattr(skill, "description", None):
            score += 1
        return {"score": min(score, 10), "rationale": f"Ganho esperado: {score}/10"}
    
    @classmethod
    def _assess_risk(cls, skill_name: str, severity: str, skill: Any) -> Dict[str, Any]:
        score = 3
        if severity == "high":
            score = 6
        elif severity == "medium":
            score = 4
        if skill_name.startswith("auto_fix"):
            score += 2
        return {"score": min(score, 10), "rationale": f"Risco estimado: {score}/10"}
    
    @classmethod
    def _check_compatibility(cls, skill_name: str, skill: Any) -> Dict[str, Any]:
        existing = skill_registry.list_skills() if hasattr(skill_registry, "list_skills") else []
        conflicting_names = [s.name if hasattr(s, "name") else "" for s in existing if (s.name if hasattr(s, "name") else "") != skill_name]
        name_conflict = skill_name in conflicting_names
        return {"compatible": not name_conflict, "conflict": name_conflict, "rationale": "Conflito de nome detectado" if name_conflict else "Compatível"}
    
    @classmethod
    def _analyze_cost(cls, skill_name: str, severity: str, skill: Any) -> Dict[str, Any]:
        score = 3
        if severity == "high":
            score = 5
        return {"score": min(score, 10), "rationale": f"Custo estimado: {score}/10"}


async def _run_evolution_committee(ctx: dict) -> dict:
    return await EvolutionCommittee.evaluate(ctx)