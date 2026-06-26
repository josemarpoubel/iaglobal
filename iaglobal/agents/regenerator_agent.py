# iaglobal/agents/regenerator_agent.py
"""
RegeneratorAgent — Agente de auto-regeneração guiado pelas Leis Universais.

Inspiração biológica:
- Regeneração celular (stem cells)
- Cicatrização de tecidos
- Autofagia controlada
- Homeostase restaurativa

Este agente é acionado pelo ImmuneOrchestrator quando danos são detectados,
e usa as Leis Universais de Holliwell como guia para regeneração ética.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from iaglobal.core.law_engine import law_compliance_engine, LawComplianceEngine
from iaglobal.immunity.apoptosis_engine import apoptosis_engine
from iaglobal.evolution.skills.dynamic_registry import dynamic_registry
from iaglobal.utils.logger import logger

logger = logging.getLogger(__name__)


@dataclass
class RegenerationPlan:
    """Plano de regeneração estruturado."""
    target_skill: str
    damage_type: str
    severity: int  # 1-10
    regeneration_strategy: str
    law_constraints: List[str]
    estimated_recovery_time: int  # em ciclos
    steps: List[Dict[str, Any]]
    success_probability: float


class RegeneratorAgent:
    """
    Agente especializado em regenerar components danificados do sistema.
    
    Operação:
    1. Recebe relatório de dano do ImmuneOrchestrator
    2. Analisa tipo e severidade do dano
    3. Cria plano de regeneração conforme Leis Universais
    4. Executa regeneração em etapas validadas
    5. Monitora recuperação e homeostase
    """

    def __init__(self):
        self._law_engine = law_compliance_engine
        self._regeneration_history: List[Dict[str, Any]] = []
        self._active_regenerations: Dict[str, RegenerationPlan] = {}
        
        # Mapeamento de tipos de dano para estratégias
        self._damage_strategies = {
            "loop_infinity": "circuit_breaker",
            "regression": "rollback_with_learning",
            "hallucination": "grounding_reinforcement",
            "behavior_anomaly": "retraining_with_constraints",
            "oxidative_stress": "simplification_pruning",
            "law_violation": "ethical_realignment",
            "apoptosis_pending": "controlled_replacement",
        }

    def assess_damage(
        self,
        skill_name: str,
        immune_report: Any,
        context: Dict[str, Any]
    ) -> Optional[RegenerationPlan]:
        """
        Avalia dano reportado pelo sistema imunológico e cria plano de regeneração.
        """
        threats = immune_report.threats if hasattr(immune_report, 'threats') else {}
        law_violations = immune_report.law_violations if hasattr(immune_report, 'law_violations') else None
        
        if not threats and not law_violations:
            logger.info(f"[REGENERATOR] No damage detected for {skill_name}")
            return None

        # Determinar tipo principal de dano
        damage_type = self._identify_primary_damage(threats, law_violations)
        severity = self._calculate_severity(threats, law_violations, immune_report)
        
        # Selecionar estratégia baseada no dano
        strategy = self._damage_strategies.get(damage_type, "generic_healing")
        
        # Extrair constraints das Leis Universais
        law_constraints = []
        if law_violations:
            for violation in law_violations:
                law_constraints.append(f"Evitar violação: {violation.get('law', 'Unknown')}")
        
        # Adicionar constraints preventivas
        law_constraints.extend([
            "Manter Lei da Homeostase durante regeneração",
            "Respeitar Lei da Autofagia (remover apenas necessário)",
            "Seguir Lei da Epigenética (adaptar sem alterar núcleo)"
        ])
        
        # Criar passos de regeneração
        steps = self._generate_regeneration_steps(damage_type, skill_name, context)
        
        plan = RegenerationPlan(
            target_skill=skill_name,
            damage_type=damage_type,
            severity=severity,
            regeneration_strategy=strategy,
            law_constraints=law_constraints,
            estimated_recovery_time=self._estimate_recovery_time(severity, damage_type),
            steps=steps,
            success_probability=self._calculate_success_probability(severity, damage_type)
        )
        
        self._active_regenerations[skill_name] = plan
        logger.info(f"[REGENERATOR] Plan created for {skill_name}: {damage_type} (severity={severity})")
        
        return plan

    def _identify_primary_damage(
        self,
        threats: Dict[str, Any],
        law_violations: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Identifica o tipo primário de dano."""
        if law_violations and len(law_violations) > 0:
            return "law_violation"
        
        if "loop" in str(threats).lower():
            return "loop_infinity"
        if "regression" in str(threats).lower():
            return "regression"
        if "hallucination" in str(threats).lower():
            return "hallucination"
        if "anomaly" in str(threats).lower():
            return "behavior_anomaly"
        if "stress" in str(threats).lower():
            return "oxidative_stress"
        
        return "unknown"

    def _calculate_severity(
        self,
        threats: Dict[str, Any],
        law_violations: Optional[List[Dict[str, Any]]],
        immune_report: Any
    ) -> int:
        """Calcula severidade do dano (1-10)."""
        severity = 1
        
        # Baseado no número de ameaças
        severity += min(len(threats), 3)
        
        # Baseado em violações das Leis
        if law_violations:
            severity += len(law_violations) * 2
            
        # Baseado no score de conformidade
        if hasattr(immune_report, 'law_compliance_score'):
            score = immune_report.law_compliance_score
            if score < 0.5:
                severity += 3
            elif score < 0.7:
                severity += 2
            elif score < 0.9:
                severity += 1
        
        return min(severity, 10)

    def _generate_regeneration_steps(
        self,
        damage_type: str,
        skill_name: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Gera passos específicos para regeneração."""
        steps = []
        
        # Passo 1: Isolamento (se necessário)
        if damage_type in ["law_violation", "behavior_anomaly", "loop_infinity"]:
            steps.append({
                "step": 1,
                "action": "isolate",
                "description": f"Isolar {skill_name} para prevenir propagação",
                "law_check": True
            })
        
        # Passo 2: Diagnóstico profundo
        steps.append({
            "step": len(steps) + 1,
            "action": "diagnose",
            "description": f"Analisar causa raiz do dano em {skill_name}",
            "tools": ["root_cause_analysis", "pattern_matching"]
        })
        
        # Passo 3: Aplicar estratégia específica
        strategy_desc = {
            "circuit_breaker": "Implementar limitador de execuções",
            "rollback_with_learning": "Reverter para versão estável + aprender com erro",
            "grounding_reinforcement": "Adicionar verificações de realidade",
            "retraining_with_constraints": "Retrinar com constraints éticos",
            "simplification_pruning": "Remover complexidade desnecessária",
            "ethical_realignment": "Realinhar com Leis Universais",
            "controlled_replacement": "Substituir por nova versão validada",
            "generic_healing": "Aplicar correções genéricas de estabilidade"
        }
        
        steps.append({
            "step": len(steps) + 1,
            "action": "apply_strategy",
            "strategy": self._damage_strategies.get(damage_type, "generic_healing"),
            "description": strategy_desc.get(self._damage_strategies.get(damage_type, "generic_healing")),
            "law_check": True
        })
        
        # Passo 4: Validação pós-regeneração
        steps.append({
            "step": len(steps) + 1,
            "action": "validate",
            "description": f"Validar {skill_name} contra Leis Universais e métricas de saúde",
            "validation_criteria": [
                "law_compliance_score >= 0.9",
                "no_threats_detected",
                "performance_within_bounds"
            ]
        })
        
        # Passo 5: Reintegração gradual
        steps.append({
            "step": len(steps) + 1,
            "action": "reintegrate",
            "description": f"Reintegrar {skill_name} gradualmente ao sistema",
            "method": "canary_deployment"
        })
        
        return steps

    def _estimate_recovery_time(self, severity: int, damage_type: str) -> int:
        """Estima tempo de recuperação em ciclos."""
        base_time = severity * 2
        
        modifiers = {
            "law_violation": 2.0,  # Requer cuidado extra
            "apoptosis_pending": 3.0,  # Substituição completa
            "regression": 1.5,
            "loop_infinity": 1.2,
        }
        
        return int(base_time * modifiers.get(damage_type, 1.0))

    def _calculate_success_probability(self, severity: int, damage_type: str) -> float:
        """Calcula probabilidade estimada de sucesso."""
        base_prob = 0.95
        
        # Reduz baseado na severidade
        severity_penalty = (severity / 10) * 0.3
        
        # Reduz baseado no tipo de dano
        difficult_types = ["law_violation", "apoptosis_pending"]
        type_penalty = 0.15 if damage_type in difficult_types else 0.05
        
        return max(0.5, base_prob - severity_penalty - type_penalty)

    async def execute_regeneration(
        self,
        plan: RegenerationPlan,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executa plano de regeneração passo a passo.
        """
        logger.info(f"[REGENERATOR] Starting regeneration for {plan.target_skill}")
        
        results = []
        critical_failure = False
        
        for step in plan.steps:
            logger.info(f"[REGENERATOR] Executing step {step['step']}: {step['action']}")
            
            # Validar leis antes de cada passo crítico
            if step.get("law_check", False):
                law_validation = self._law_engine.evaluate_action({
                    "action": f"regeneration_step_{step['step']}",
                    "context": {"plan": plan.__dict__, "step": step},
                    "output": "",
                    "metrics": {"target": plan.target_skill}
                })
                
                if not law_validation.get("compliant", True):
                    logger.error(f"[REGENERATOR] Step {step['step']} violated Laws: {law_validation.get('violations')}")
                    critical_failure = True
                    break
            
            # Executar passo (simulado - seria expandido com lógica real)
            step_result = await self._execute_step(step, plan, context)
            results.append(step_result)
            
            if not step_result.get("success", False):
                logger.warning(f"[REGENERATOR] Step {step['step']} failed")
                if step_result.get("critical", False):
                    critical_failure = True
                    break
        
        # Registrar histórico
        regeneration_record = {
            "skill": plan.target_skill,
            "damage_type": plan.damage_type,
            "severity": plan.severity,
            "steps_executed": len(results),
            "success": not critical_failure,
            "results": results
        }
        self._regeneration_history.append(regeneration_record)
        
        if plan.target_skill in self._active_regenerations:
            del self._active_regenerations[plan.target_skill]
        
        return regeneration_record

    async def _execute_step(
        self,
        step: Dict[str, Any],
        plan: RegenerationPlan,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Executa um passo individual de regeneração."""
        action = step.get("action")
        
        try:
            if action == "isolate":
                # Isolar skill do registry
                logger.info(f"[REGENERATOR] Isolating {plan.target_skill}")
                return {"success": True, "action": "isolated"}
            
            elif action == "diagnose":
                # Análise de causa raiz
                logger.info(f"[REGENERATOR] Diagnosing {plan.target_skill}")
                return {"success": True, "action": "diagnosed", "findings": []}
            
            elif action == "apply_strategy":
                # Aplicar estratégia de regeneração
                strategy = step.get("strategy")
                logger.info(f"[REGENERATOR] Applying strategy: {strategy}")
                return {"success": True, "action": "strategy_applied", "strategy": strategy}
            
            elif action == "validate":
                # Validação pós-regeneração
                logger.info(f"[REGENERATOR] Validating {plan.target_skill}")
                return {"success": True, "action": "validated", "metrics": {"health": 0.95}}
            
            elif action == "reintegrate":
                # Reintegração gradual
                logger.info(f"[REGENERATOR] Reintegrating {plan.target_skill}")
                return {"success": True, "action": "reintegrated"}
            
            else:
                logger.warning(f"[REGENERATOR] Unknown action: {action}")
                return {"success": False, "error": f"Unknown action: {action}"}
                
        except Exception as e:
            logger.error(f"[REGENERATOR] Step execution failed: {e}")
            return {"success": False, "error": str(e), "critical": True}

    def get_regeneration_status(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Retorna status de regeneração ativa."""
        if skill_name in self._active_regenerations:
            plan = self._active_regenerations[skill_name]
            return {
                "skill": skill_name,
                "status": "regenerating",
                "damage_type": plan.damage_type,
                "severity": plan.severity,
                "strategy": plan.regeneration_strategy,
                "estimated_completion": plan.estimated_recovery_time,
                "success_probability": plan.success_probability
            }
        return None

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retorna histórico de regenerações."""
        return self._regeneration_history[-limit:]


# Singleton global
regenerator_agent = RegeneratorAgent()
