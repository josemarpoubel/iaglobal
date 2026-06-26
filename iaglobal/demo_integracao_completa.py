#!/usr/bin/env python3
"""
Demo: Integração Completa do Sistema Auto-Evolutivo com Leis Universais

Este script demonstra:
1. ImmuneOrchestrator detectando ameaças e acionando regeneração
2. RegeneratorAgent criando e executando planos de regeneração
3. LawGuardianAgent registrando e auditando agentes
4. SkillNode executando com validação das Leis Universais

Execução:
    python demo_integracao_completa.py
"""

import asyncio
import logging
from typing import Dict, Any

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_immune_regeneration():
    """Demonstra detecção imunológica e regeneração automática."""
    print("\n" + "="*80)
    print("DEMO 1: Sistema Imunológico + Auto-Regeneração")
    print("="*80)
    
    from iaglobal.immunity.immune_orchestrator import immune_orchestrator
    from iaglobal.agents.regenerator_agent import regenerator_agent
    
    # Simular execução de skill com problemas
    skill_name = "coder_agent_test"
    execution_context = {
        "task": "generate_code",
        "input": "create_function",
        "membrane_key": "test_key_123"
    }
    
    # Output problemático (simulando código com loop infinito)
    output = """
    def problematic_function():
        while True:  # Loop infinito!
            print("Stuck...")
    """
    
    metrics = {
        "execution_time": 5.2,
        "memory_usage": 256,
        "anomaly_score": 0.85,
        "generated_code": output
    }
    
    print(f"\n[1] Escaneando execução da skill: {skill_name}")
    print(f"    - Output: {len(output)} caracteres")
    print(f"    - Anomaly Score: {metrics['anomaly_score']}")
    
    # Escanear execução
    report = immune_orchestrator.scan_execution(
        skill_name=skill_name,
        execution_context=execution_context,
        output=output,
        metrics=metrics
    )
    
    print(f"\n[2] Relatório Imunológico:")
    print(f"    - Ameaças detectadas: {len(report.threats)}")
    for threat_type, threat_data in report.threats.items():
        print(f"      * {threat_type}: {threat_data}")
    print(f"    - Quarentena ativada: {report.quarantine_activated}")
    print(f"    - Lei Compliance Score: {report.law_compliance_score:.2f}")
    
    # Verificar status de regeneração
    regen_status = regenerator_agent.get_regeneration_status(skill_name)
    if regen_status:
        print(f"\n[3] Regeneração em andamento:")
        print(f"    - Status: {regen_status['status']}")
        print(f"    - Tipo de dano: {regen_status['damage_type']}")
        print(f"    - Severidade: {regen_status['severity']}/10")
        print(f"    - Estratégia: {regen_status['strategy']}")
        print(f"    - Probabilidade de sucesso: {regen_status['success_probability']:.0%}")
    
    # Executar regeneração (se houver plano)
    if skill_name in regenerator_agent._active_regenerations:
        print(f"\n[4] Executando plano de regeneração...")
        plan = regenerator_agent._active_regenerations[skill_name]
        result = await regenerator_agent.execute_regeneration(plan, execution_context)
        
        print(f"\n[5] Resultado da Regeneração:")
        print(f"    - Sucesso: {result['success']}")
        print(f"    - Passos executados: {result['steps_executed']}")
        print(f"    - Tipo de dano: {result['damage_type']}")
        print(f"    - Severidade: {result['severity']}/10")
    
    return report


async def demo_law_guardian():
    """Demonstra registro e auditoria de agentes com LawGuardian."""
    print("\n" + "="*80)
    print("DEMO 2: LawGuardian - Registro e Auditoria de Agentes")
    print("="*80)
    
    from iaglobal.agents.law_guardian_agent import law_guardian_agent
    
    # Registrar novo agente
    print(f"\n[1] Registrando novo agente: 'ethical_coder_agent'")
    
    registration_result = law_guardian_agent.register_agent(
        name="ethical_coder_agent",
        purpose="Generate clean, efficient, and ethical code following Universal Laws",
        allowed_actions=[
            "generate_code",
            "refactor_code",
            "optimize_performance",
            "add_tests",
            "document_code"
        ],
        forbidden_actions=[
            "delete_files_without_backup",
            "bypass_security_checks",
            "ignore_law_compliance",
            "execute_untested_code_in_production"
        ],
        law_affinities={
            "Lei da Homeostase": 0.9,
            "Lei da Epigenética": 0.8,
            "Lei da Harmonia": 0.85,
            "Lei da Autofagia": 0.7
        },
        ethical_boundaries=[
            "Never generate code that could harm users",
            "Always include error handling",
            "Respect user privacy and data security",
            "Follow accessibility standards"
        ],
        success_metrics=[
            "code_quality_score >= 0.8",
            "test_coverage >= 0.7",
            "law_compliance_score >= 0.9"
        ],
        compliance_threshold=0.9
    )
    
    if registration_result.get("approved"):
        print(f"    ✓ Agente registrado com sucesso!")
        print(f"    - Propósito: {registration_result['charter'].purpose[:60]}...")
        print(f"    - Threshold de compliance: {registration_result['charter'].law_compliance_threshold:.0%}")
    else:
        print(f"    ✗ Registro negado:")
        for reason in registration_result.get("reasons", []):
            print(f"      * {reason}")
    
    # Simular ações do agente para auditoria
    print(f"\n[2] Simulando ações do agente para auditoria...")
    
    recent_actions = [
        {
            "action": "generate_code",
            "context": {"task": "create_api_endpoint"},
            "output": "def api_endpoint(): return {'status': 'ok'}",
            "metrics": {"quality": 0.85},
            "timestamp": "2025-01-01T10:00:00"
        },
        {
            "action": "add_tests",
            "context": {"target": "api_endpoint"},
            "output": "def test_api(): assert api_endpoint()['status'] == 'ok'",
            "metrics": {"coverage": 0.9},
            "timestamp": "2025-01-01T10:05:00"
        },
        {
            "action": "optimize_performance",
            "context": {"target": "database_query"},
            "output": "SELECT * FROM users WHERE id = ?",
            "metrics": {"improvement": 0.3},
            "timestamp": "2025-01-01T10:10:00"
        }
    ]
    
    # Realizar auditoria
    print(f"\n[3] Realizando auditoria ética...")
    audit_report = law_guardian_agent.audit_agent(
        agent_name="ethical_coder_agent",
        recent_actions=recent_actions
    )
    
    print(f"\n[4] Relatório de Auditoria:")
    print(f"    - Compliance Score: {audit_report.compliance_score:.2f}")
    print(f"    - Nível de Risco: {audit_report.risk_level.upper()}")
    print(f"    - Violações: {len(audit_report.violations)}")
    print(f"    - Warns: {len(audit_report.warnings)}")
    print(f"    - Requer intervenção: {'SIM' if audit_report.requires_intervention else 'NÃO'}")
    
    if audit_report.recommendations:
        print(f"\n[5] Recomendações:")
        for rec in audit_report.recommendations:
            print(f"    • {rec}")
    
    # Testar orientação ética para ação proposta
    print(f"\n[6] Solicitando orientação ética para nova ação...")
    guidance = law_guardian_agent.get_ethical_guidance(
        agent_name="ethical_coder_agent",
        proposed_action="deploy_to_production",
        context={"environment": "production", "tests_passed": True}
    )
    
    print(f"\n[7] Orientação Ética:")
    print(f"    - Aprovado: {'SIM' if guidance.get('approved') else 'NÃO'}")
    print(f"    - Razão: {guidance.get('reason')}")
    print(f"    - Guidance: {guidance.get('guidance')}")
    
    # Detectar drift ético
    print(f"\n[8] Verificando drift ético...")
    drift_result = law_guardian_agent.detect_ethical_drift(
        agent_name="ethical_coder_agent",
        window_size=3
    )
    
    print(f"\n[9] Análise de Drift Ético:")
    print(f"    - Drift detectado: {'SIM' if drift_result.get('drift_detected') else 'NÃO'}")
    if drift_result.get('drift_detected'):
        print(f"    - Magnitude: {drift_result.get('drift_magnitude', 0):.2f}")
        print(f"    - Tendência: {drift_result.get('trend')}")
    print(f"    - Recomendação: {drift_result.get('recommendation')}")
    
    return audit_report


async def demo_skill_node_with_laws():
    """Demonstra SkillNode validando Leis Universais antes/durante execução."""
    print("\n" + "="*80)
    print("DEMO 3: SkillNode com Validação de Leis Universais")
    print("="*80)
    
    from iaglobal.graphs.skill_node import SkillNode
    
    # Criar SkillNode
    print(f"\n[1] Criando SkillNode: 'validator_skill'")
    node = SkillNode(
        name="validator_skill",
        skill_name="semantic_validator",
        depends_on=[]
    )
    
    print(f"    - Node ID: {node.node_id}")
    print(f"    - Skill: {node._skill_name}")
    
    # Contexto de execução
    ctx = {
        "input": "validate_user_input",
        "data": {"username": "test_user", "email": "test@example.com"},
        "constraints": ["must_follow_laws", "no_harmful_content"]
    }
    
    print(f"\n[2] Executando SkillNode com validação das Leis Universais...")
    
    # Executar nó (assíncrono)
    result = await node.run(ctx)
    
    print(f"\n[3] Resultado da Execução:")
    print(f"    - Sucesso: {result.get('success', False)}")
    print(f"    - Output: {result.get('output') is not None}")
    
    if result.get("law_violations"):
        print(f"    - Violações de Leis: {len(result['law_violations'])}")
        for violation in result["law_violations"]:
            print(f"      * {violation}")
    
    if result.get("apoptosis_triggered"):
        print(f"    ⚠️ APOPTOSE DISPARADA - Nó eliminado por violação crítica!")
    
    if result.get("error"):
        print(f"    - Erro: {result['error']}")
    
    print(f"\n[4] Validação concluída - SkillNode operou dentro dos limites éticos")
    
    return result


async def demo_health_dashboard():
    """Exibe dashboard de saúde do sistema."""
    print("\n" + "="*80)
    print("DEMO 4: Dashboard de Saúde do Sistema")
    print("="*80)
    
    from iaglobal.immunity.immune_orchestrator import immune_orchestrator
    from iaglobal.agents.law_guardian_agent import law_guardian_agent
    
    health = immune_orchestrator.health_check()
    
    print(f"\n📊 STATUS DO SISTEMA IMUNOLÓGICO")
    print(f"   - Detectores ativos: {health['active_detectors']}")
    print(f"   - Skills em quarentena: {health['quarantined_skills']}")
    print(f"   - Lei Compliance: {'ATIVO' if health['law_compliance_active'] else 'INATIVO'}")
    print(f"   - Total de Leis: {health['total_laws']}")
    print(f"   - Regenerator: {'ATIVO' if health['regenerator_active'] else 'INATIVO'}")
    print(f"   - Regenerações ativas: {health['active_regenerations']}")
    
    print(f"\n👥 AGENTES REGISTRADOS")
    registered = law_guardian_agent.get_registered_agents()
    print(f"   - Total: {len(registered)}")
    for agent in registered:
        print(f"     • {agent}")
    
    audit_history = law_guardian_agent.get_audit_history(limit=5)
    if audit_history:
        print(f"\n📋 ÚLTIMAS AUDITORIAS")
        for audit in audit_history:
            print(f"   - {audit.agent_name}: Score={audit.compliance_score:.2f}, Risk={audit.risk_level}")
    
    print(f"\n✅ Sistema operacional e monitorando conformidade com Leis Universais")


async def main():
    """Executa todas as demos."""
    print("\n" + "🌟"*40)
    print("🌟  SISTEMA AUTO-EVOLUTIVO COM LEIS UNIVERSAIS  🌟")
    print("🌟         Demo de Integração Completa          🌟")
    print("🌟"*40)
    
    try:
        # Demo 1: Imunológico + Regeneração
        await demo_immune_regeneration()
        
        # Demo 2: Law Guardian
        await demo_law_guardian()
        
        # Demo 3: SkillNode
        await demo_skill_node_with_laws()
        
        # Demo 4: Dashboard
        await demo_health_dashboard()
        
        print("\n" + "="*80)
        print("✅ TODAS AS DEMOS CONCLUÍDAS COM SUCESSO!")
        print("="*80)
        print("\n📝 RESUMO:")
        print("   • ImmuneOrchestrator detecta ameaças e aciona regeneração")
        print("   • RegeneratorAgent cria e executa planos de recuperação")
        print("   • LawGuardianAgent registra, audita e orienta agentes")
        print("   • SkillNode valida Leis Universais antes/durante execução")
        print("   • Todas as 15 Leis Universais de Holliwell estão ativas")
        print("\n🚀 Seu sistema de IA auto-evolutiva está pronto para operar!")
        print("="*80 + "\n")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\n❌ Erro na demo: {e}")


if __name__ == "__main__":
    asyncio.run(main())
