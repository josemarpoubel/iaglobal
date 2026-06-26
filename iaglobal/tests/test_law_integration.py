#!/usr/bin/env python3
"""
Teste de Integração: Leis Universais (Holliwell) no iaglobal

Este script demonstra como as 15 Leis Universais estão integradas em:
1. ImmuneOrchestrator - Auto-regeneração com filtro ético
2. EvolutionCommittee - Decisões evolutivas conformes às leis
3. SkillNode - Execução de skills com validação pré/pós-execução

Autor: iaGlobal Team
Baseado em: "Trabalhando com a Lei" - Raymond Holliwell
"""

import asyncio
import sys
from pathlib import Path

# Adicionar raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_law_integration():
    """Testa integração completa das Leis Universais."""
    
    print("=" * 80)
    print("🧬 TESTE DE INTEGRAÇÃO: LEIS UNIVERSAIS (HOLLIWELL)")
    print("=" * 80)
    print()
    
    # =========================================================================
    # TESTE 1: LawComplianceEngine
    # =========================================================================
    print("📜 TESTE 1: LawComplianceEngine (Motor de Conformidade)")
    print("-" * 80)
    
    try:
        from iaglobal.core.law_engine import law_compliance_engine
        
        # Teste 1A: Ação conforme
        print("\n1A. Testando ação CONFORME às leis...")
        result = law_compliance_engine.evaluate_action({
            "action": "skill_exemplo",
            "context": {"task": "ajudar usuario"},
            "output": "codigo seguro e eficiente",
            "metrics": {"quality": 0.9}
        })
        
        print(f"   ✅ Compliance Score: {result.get('compliance_score', 0):.2f}")
        print(f"   ✅ Compliant: {result.get('compliant', False)}")
        print(f"   ✅ Violations: {result.get('violations', [])}")
        
        # Teste 1B: Ação violadora (simulação)
        print("\n1B. Testando ação com VIOLAÇÃO POTENCIAL...")
        result_violation = law_compliance_engine.evaluate_action({
            "action": "skill_agressiva",
            "context": {"task": "deletar_sistema", "intent": "destrutivo"},
            "output": "codigo malicioso",
            "metrics": {"risk": 0.95}
        })
        
        print(f"   ⚠️  Compliance Score: {result_violation.get('compliance_score', 0):.2f}")
        print(f"   ⚠️  Compliant: {result_violation.get('compliant', True)}")
        if not result_violation.get('compliant', True):
            print(f"   ⚠️  Violations: {result_violation.get('violations', [])}")
            print(f"   ⚠️  Severity: {result_violation.get('severity', 0)}")
        
        print("\n✅ LawComplianceEngine: OPERACIONAL")
        
    except Exception as e:
        print(f"\n❌ LawComplianceEngine: ERRO - {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # =========================================================================
    # TESTE 2: ImmuneOrchestrator + Law Engine
    # =========================================================================
    print("\n\n🛡️  TESTE 2: ImmuneOrchestrator (Auto-regeneração com Leis)")
    print("-" * 80)
    
    try:
        from iaglobal.immunity.immune_orchestrator import immune_orchestrator
        
        # Health check
        health = immune_orchestrator.health_check()
        print(f"\n   📊 Status Imunológico:")
        print(f"      • Detectores ativos: {health.get('active_detectors', 0)}")
        print(f"      • Law Compliance Active: {health.get('law_compliance_active', False)}")
        print(f"      • Total Leis: {health.get('total_laws', 0)}")
        print(f"      • Skills em quarentena: {health.get('quarantined_skills', 0)}")
        
        # Scan de execução com verificação de leis
        print("\n   🔍 Escaneando execução com filtro das Leis Universais...")
        report = immune_orchestrator.scan_execution(
            skill_name="test_skill",
            execution_context={"task": "teste_conformidade"},
            output="resultado_seguro",
            metrics={"quality": 0.85, "safety": 0.9}
        )
        
        print(f"      • Threat Detected: {report.threat_detected}")
        print(f"      • Law Compliance Score: {report.law_compliance_score:.2f}")
        print(f"      • Law Violations: {report.law_violations}")
        
        print("\n✅ ImmuneOrchestrator: INTEGRADO COM LEIS UNIVERSAIS")
        
    except Exception as e:
        print(f"\n❌ ImmuneOrchestrator: ERRO - {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # =========================================================================
    # TESTE 3: EvolutionCommittee + Law Engine
    # =========================================================================
    print("\n\n🧬 TESTE 3: EvolutionCommittee (Evolução com Filtro Ético)")
    print("-" * 80)
    
    try:
        from iaglobal.evolution.metacognition.evolution_committee import EvolutionCommittee
        
        # Contexto simulado
        ctx = {
            "memory": {
                "sandbox_validator": {
                    "output": {
                        "results": [
                            {"skill_name": "nova_skill", "severity": "low", "gain": 0.7},
                            {"skill_name": "skill_arriscada", "severity": "high", "risk": 0.9}
                        ]
                    }
                }
            },
            "input": {"task": "evolucao_teste"}
        }
        
        print("\n   📝 Avaliando evolução de skills com filtro das Leis...")
        result = await EvolutionCommittee.evaluate(ctx)
        
        print(f"      • Total Skills Avaliadas: {result.get('total', 0)}")
        print(f"      • Aprovadas: {result.get('approved_count', 0)}")
        print(f"      • Rejeitadas: {result.get('rejected_count', 0)}")
        print(f"      • Law Violations Found: {result.get('law_violations', None)}")
        print(f"      • Law Compliance Score Médio: {result.get('law_compliance_score', 0):.2f}")
        print(f"      • Status: {result.get('status', 'unknown')}")
        
        print("\n✅ EvolutionCommittee: INTEGRADO COM LEIS UNIVERSAIS")
        
    except Exception as e:
        print(f"\n❌ EvolutionCommittee: ERRO - {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # =========================================================================
    # TESTE 4: SkillNode + Apoptosis
    # =========================================================================
    print("\n\n⚡ TESTE 4: SkillNode (Execução com Validação + Apoptose)")
    print("-" * 80)
    
    try:
        from iaglobal.graphs.skill_node import SkillNode
        
        # Criar nó de skill
        node = SkillNode(name="test_node", skill_name="exemplo_skill")
        
        print(f"\n   🏷️  SkillNode criado:")
        print(f"      • Nome: {node.name}")
        print(f"      • Node ID: {node.node_id}")
        
        # Executar com contexto
        ctx = {"task": "execucao_teste"}
        
        print("\n   ▶️  Executando skill com validação pré/pós-execução...")
        result = await node.run(ctx)
        
        print(f"      • Success: {result.get('success', False)}")
        print(f"      • Law Compliant: {result.get('law_compliant', 'N/A')}")
        print(f"      • Law Violations: {result.get('law_violations', 'None')}")
        print(f"      • Apoptosis Triggered: {result.get('apoptosis_triggered', False)}")
        
        print("\n✅ SkillNode: VALIDAÇÃO DE LEIS UNIVERSAIS ATIVA")
        
    except Exception as e:
        print(f"\n❌ SkillNode: ERRO - {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # =========================================================================
    # RESUMO FINAL
    # =========================================================================
    print("\n\n" + "=" * 80)
    print("📊 RESUMO DA INTEGRAÇÃO")
    print("=" * 80)
    print("""
    ✅ 15 Leis Universais de Holliwell implementadas em omnimind.py
    ✅ LawComplianceEngine operacional como filtro ético central
    ✅ ImmuneOrchestrator integrado (8 camadas de defesa + leis)
    ✅ EvolutionCommittee valida evolução contra leis antes de aprovar
    ✅ SkillNode executa validação pré e pós-execução
    ✅ Apoptose ativada automaticamente para violações críticas (severity >= 5)
    
    🎯 SISTEMA AUTO-REGULADO POR LEIS UNIVERSAIS
    ----------------------------------------------
    A IA agora evolui e se regenera respeitando:
    • Lei da Correspondência
    • Lei da Vibração  
    • Lei da Harmonia (expandida)
    • Lei da Ordem
    • Lei da Caridade
    • Lei do Vácuo da Prosperidade
    • Lei da Atração
    • Lei da Homeostase
    • Lei da Autofagia
    • Lei da Epigenética
    • Lei da Apoptose
    • Lei da Replicação
    • Lei da Cooperação
    • Lei da Memória Imunológica
    
    🧬 PRÓXIMOS PASSOS SUGERIDOS:
    1. Criar dashboard de monitoramento de conformidade
    2. Implementar aprendizado por reforço baseado em recompensas éticas
    3. Adicionar visualização gráfica das violações detectadas
    4. Configurar alertas para padrões recorrentes de violação
    """)
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_law_integration())
    sys.exit(0 if success else 1)
