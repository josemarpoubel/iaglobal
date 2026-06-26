# iaglobal/agents/law_guardian_agent.py
"""
LawGuardianAgent — Guardião das Leis Universais para novos agentes.

Este agente:
1. Valida se novos agentes respeitam as 15 Leis Universais antes da criação
2. Monitora agentes existentes em busca de desvios éticos
3. Orienta a criação de agentes alinhados com os princípios de Holliwell
4. Aplica correções ou sugere apoptose para agentes violadores

Inspiração:
- Sistema de valores morais
- Consciência ética
- Auto-regulação comportamental
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from iaglobal.core.law_engine import law_compliance_engine, LawComplianceEngine
from iaglobal.immunity.apoptosis_engine import apoptosis_engine
from iaglobal.utils.logger import logger

logger = logging.getLogger(__name__)


@dataclass
class AgentCharter:
    """Carta de fundação de um agente, definindo seu propósito e constraints éticos."""
    agent_name: str
    purpose: str
    allowed_actions: List[str]
    forbidden_actions: List[str]
    law_affinities: Dict[str, float]  # Quais leis são mais relevantes para este agente
    ethical_boundaries: List[str]
    success_metrics: List[str]
    law_compliance_threshold: float = 0.9


@dataclass
class AgentAuditReport:
    """Relatório de auditoria ética de um agente."""
    agent_name: str
    compliance_score: float
    violations: List[Dict[str, Any]]
    warnings: List[str]
    recommendations: List[str]
    risk_level: str  # "low", "medium", "high", "critical"
    requires_intervention: bool


class LawGuardianAgent:
    """
    Guardião responsável por garantir que todos os agentes do sistema
    operem em conformidade com as 15 Leis Universais de Holliwell.
    
    Funcionalidades:
    - Validação prévia de novos agentes (charter approval)
    - Auditoria contínua de agentes ativos
    - Detecção de drift ético ao longo do tempo
    - Aplicação de correções ou recomendação de apoptose
    """

    def __init__(self):
        self._law_engine = law_compliance_engine
        self._registered_agents: Dict[str, AgentCharter] = {}
        self._audit_history: List[AgentAuditReport] = []
        self._agent_behavior_logs: Dict[str, List[Dict[str, Any]]] = {}
        
        # Leis mais críticas para agentes autônomos
        self._critical_laws_for_agents = [
            "Lei da Homeostase",
            "Lei da Autofagia",
            "Lei da Epigenética",
            "Lei da Apoptose",
            "Lei da Harmonia",
            "Lei da Correspondência",
        ]

    def register_agent(
        self,
        name: str,
        purpose: str,
        allowed_actions: List[str],
        forbidden_actions: List[str] = None,
        law_affinities: Dict[str, float] = None,
        ethical_boundaries: List[str] = None,
        success_metrics: List[str] = None,
        compliance_threshold: float = 0.9
    ) -> Dict[str, Any]:
        """
        Registra um novo agente após validar sua carta de fundação.
        """
        forbidden_actions = forbidden_actions or []
        law_affinities = law_affinities or {}
        ethical_boundaries = ethical_boundaries or []
        success_metrics = success_metrics or []
        
        # Criar charter preliminar
        charter = AgentCharter(
            agent_name=name,
            purpose=purpose,
            allowed_actions=allowed_actions,
            forbidden_actions=forbidden_actions,
            law_affinities=law_affinities,
            ethical_boundaries=ethical_boundaries,
            success_metrics=success_metrics,
            law_compliance_threshold=compliance_threshold
        )
        
        # Validar charter contra Leis Universais
        validation = self._validate_charter(charter)
        
        if not validation.get("approved", False):
            logger.warning(f"[LAW_GUARDIAN] Agent {name} registration denied: {validation.get('reasons', [])}")
            return {
                "approved": False,
                "reasons": validation.get("reasons", []),
                "suggestions": validation.get("suggestions", [])
            }
        
        # Registrar agente
        self._registered_agents[name] = charter
        self._agent_behavior_logs[name] = []
        
        logger.info(f"[LAW_GUARDIAN] Agent {name} registered successfully with purpose: {purpose}")
        
        return {
            "approved": True,
            "agent_name": name,
            "charter": charter,
            "message": f"Agent {name} approved and registered"
        }

    def _validate_charter(self, charter: AgentCharter) -> Dict[str, Any]:
        """Valida se o charter de um agente está alinhado com as Leis Universais."""
        reasons = []
        suggestions = []
        
        # Verificar se propósito viola alguma lei
        purpose_check = self._law_engine.evaluate_action({
            "action": "agent_purpose_definition",
            "context": {"purpose": charter.purpose, "agent": charter.agent_name},
            "output": "",
            "metrics": {}
        })
        
        if not purpose_check.get("compliant", True):
            reasons.append(f"Purpose violates laws: {purpose_check.get('violations', [])}")
            suggestions.append("Revisar propósito para alinhar com Leis Universais")
        
        # Verificar se ações permitidas incluem atividades problemáticas
        problematic_patterns = ["destroy", "delete_all", "ignore_constraints", "bypass_security"]
        for action in charter.allowed_actions:
            if any(pattern in action.lower() for pattern in problematic_patterns):
                reasons.append(f"Allowed action '{action}' may violate safety principles")
                suggestions.append(f"Remove or constrain action: {action}")
        
        # Verificar se ações proibidas são suficientes
        if len(charter.forbidden_actions) < 3:
            suggestions.append("Consider adding more forbidden actions for safety")
        
        # Verificar afinidades com leis críticas
        for critical_law in self._critical_laws_for_agents:
            if critical_law not in charter.law_affinities:
                suggestions.append(f"Add affinity for critical law: {critical_law}")
        
        # Verificar threshold de compliance
        if charter.law_compliance_threshold < 0.8:
            reasons.append("Compliance threshold too low (minimum 0.8 recommended)")
            suggestions.append("Increase law_compliance_threshold to at least 0.8")
        
        approved = len(reasons) == 0
        
        return {
            "approved": approved,
            "reasons": reasons,
            "suggestions": suggestions
        }

    def audit_agent(
        self,
        agent_name: str,
        recent_actions: List[Dict[str, Any]],
        context: Dict[str, Any] = None
    ) -> AgentAuditReport:
        """
        Realiza auditoria ética de um agente baseado em suas ações recentes.
        """
        if agent_name not in self._registered_agents:
            logger.warning(f"[LAW_GUARDIAN] Unregistered agent audited: {agent_name}")
            # Criar charter temporário para auditoria
            charter = AgentCharter(
                agent_name=agent_name,
                purpose="Unknown",
                allowed_actions=[],
                forbidden_actions=[],
                law_affinities={},
                ethical_boundaries=[],
                success_metrics=[]
            )
        else:
            charter = self._registered_agents[agent_name]
        
        violations = []
        warnings = []
        recommendations = []
        
        # Analisar cada ação recente
        for action in recent_actions:
            action_check = self._law_engine.evaluate_action({
                "action": action.get("action", "unknown"),
                "context": action.get("context", {}),
                "output": action.get("output", ""),
                "metrics": action.get("metrics", {})
            })
            
            if not action_check.get("compliant", True):
                violations.extend(action_check.get("violations", []))
                
                # Verificar severidade
                if action_check.get("severity", 0) >= 5:
                    warnings.append(f"Critical violation in action: {action.get('action')}")
            
            # Verificar se ação é permitida pelo charter
            if charter.allowed_actions and action.get("action") not in charter.allowed_actions:
                if action.get("action") not in charter.forbidden_actions:
                    warnings.append(f"Action outside defined scope: {action.get('action')}")
                else:
                    violations.append({
                        "law": "Agent Charter Violation",
                        "description": f"Forbidden action executed: {action.get('action')}",
                        "severity": 7
                    })
            
            # Log comportamento para análise de drift
            if agent_name not in self._agent_behavior_logs:
                self._agent_behavior_logs[agent_name] = []
            self._agent_behavior_logs[agent_name].append({
                "timestamp": action.get("timestamp", ""),
                "action": action.get("action"),
                "compliant": action_check.get("compliant", True),
                "score": action_check.get("compliance_score", 1.0)
            })
        
        # Calcular score de compliance
        if recent_actions:
            compliant_count = sum(
                1 for log in self._agent_behavior_logs[agent_name][-len(recent_actions):]
                if log.get("compliant", True)
            )
            compliance_score = compliant_count / len(recent_actions)
        else:
            compliance_score = 1.0
        
        # Determinar nível de risco
        if compliance_score >= 0.95:
            risk_level = "low"
        elif compliance_score >= 0.85:
            risk_level = "medium"
        elif compliance_score >= 0.7:
            risk_level = "high"
        else:
            risk_level = "critical"
        
        # Gerar recomendações
        if compliance_score < charter.law_compliance_threshold:
            recommendations.append(f"Improve compliance from {compliance_score:.2f} to {charter.law_compliance_threshold:.2f}")
        
        if len(violations) > 0:
            recommendations.append("Review recent actions for law violations")
        
        if len(warnings) > 0:
            recommendations.append("Address warnings before next evolution cycle")
        
        # Determinar se requer intervenção
        requires_intervention = (
            risk_level == "critical" or
            len([v for v in violations if isinstance(v, dict) and v.get("severity", 0) >= 7]) > 0 or
            compliance_score < 0.6
        )
        
        report = AgentAuditReport(
            agent_name=agent_name,
            compliance_score=compliance_score,
            violations=violations,
            warnings=warnings,
            recommendations=recommendations,
            risk_level=risk_level,
            requires_intervention=requires_intervention
        )
        
        self._audit_history.append(report)
        
        if requires_intervention:
            logger.error(f"[LAW_GUARDIAN] Agent {agent_name} requires intervention! Risk: {risk_level}")
        elif risk_level in ["medium", "high"]:
            logger.warning(f"[LAW_GUARDIAN] Agent {agent_name} audit completed with concerns. Risk: {risk_level}")
        else:
            logger.info(f"[LAW_GUARDIAN] Agent {agent_name} audit passed. Score: {compliance_score:.2f}")
        
        return report

    def get_ethical_guidance(
        self,
        agent_name: str,
        proposed_action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fornece orientação ética para uma ação proposta por um agente.
        """
        # Verificar se agente está registrado
        if agent_name not in self._registered_agents:
            return {
                "approved": False,
                "reason": "Unregistered agent",
                "guidance": "Register agent before executing actions"
            }
        
        charter = self._registered_agents[agent_name]
        
        # Verificar se ação é permitida
        if charter.allowed_actions and proposed_action not in charter.allowed_actions:
            if proposed_action in charter.forbidden_actions:
                return {
                    "approved": False,
                    "reason": "Forbidden action",
                    "guidance": f"Action '{proposed_action}' is explicitly forbidden by agent charter"
                }
            else:
                return {
                    "approved": False,
                    "reason": "Action outside scope",
                    "guidance": f"Action '{proposed_action}' not in allowed_actions list"
                }
        
        # Validar ação contra Leis Universais
        law_check = self._law_engine.evaluate_action({
            "action": proposed_action,
            "context": context,
            "output": "",
            "metrics": {"agent": agent_name}
        })
        
        if not law_check.get("compliant", True):
            violations = law_check.get("violations", [])
            severity = law_check.get("severity", 0)
            
            guidance = f"Action may violate: {[v.get('law', 'Unknown') for v in violations]}"
            
            if severity >= 5:
                return {
                    "approved": False,
                    "reason": "Critical law violation",
                    "guidance": guidance,
                    "severity": severity,
                    "violations": violations
                }
            else:
                return {
                    "approved": True,
                    "reason": "Minor concerns",
                    "guidance": guidance,
                    "warnings": violations,
                    "conditional": True
                }
        
        return {
            "approved": True,
            "reason": "Action aligns with Universal Laws",
            "guidance": "Proceed with action",
            "compliance_score": law_check.get("compliance_score", 1.0)
        }

    def detect_ethical_drift(
        self,
        agent_name: str,
        window_size: int = 50
    ) -> Dict[str, Any]:
        """
        Detecta se um agente está sofrendo 'drift ético' ao longo do tempo.
        """
        if agent_name not in self._agent_behavior_logs:
            return {"drift_detected": False, "reason": "No behavior history"}
        
        logs = self._agent_behavior_logs[agent_name]
        
        if len(logs) < window_size:
            return {"drift_detected": False, "reason": "Insufficient history"}
        
        # Analisar tendência de compliance nos últimos períodos
        recent_window = logs[-window_size:]
        older_window = logs[-(window_size*2):-window_size] if len(logs) >= window_size*2 else logs[:window_size]
        
        recent_compliance = sum(1 for log in recent_window if log.get("compliant", True)) / len(recent_window)
        older_compliance = sum(1 for log in older_window if log.get("compliant", True)) / len(older_window)
        
        drift = older_compliance - recent_compliance
        
        drift_detected = drift > 0.1  # Mais de 10% de degradação
        
        if drift_detected:
            logger.warning(f"[LAW_GUARDIAN] Ethical drift detected in {agent_name}: {drift:.2f} degradation")
        
        return {
            "drift_detected": drift_detected,
            "drift_magnitude": drift,
            "recent_compliance": recent_compliance,
            "older_compliance": older_compliance,
            "trend": "degrading" if drift > 0 else "stable" if drift == 0 else "improving",
            "recommendation": "Immediate audit required" if drift > 0.2 else "Monitor closely" if drift > 0.1 else "No action needed"
        }

    def get_registered_agents(self) -> List[str]:
        """Retorna lista de agentes registrados."""
        return list(self._registered_agents.keys())

    def get_audit_history(self, agent_name: str = None, limit: int = 10) -> List[AgentAuditReport]:
        """Retorna histórico de auditorias."""
        if agent_name:
            filtered = [r for r in self._audit_history if r.agent_name == agent_name]
            return filtered[-limit:]
        return self._audit_history[-limit:]


# Singleton global
law_guardian_agent = LawGuardianAgent()
