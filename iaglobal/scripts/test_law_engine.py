#!/usr/bin/env python3
# ============================================================
# DEMONSTRAÇÃO: MOTOR DE CONFORMIDADE DAS LEIS UNIVERSAIS
# ============================================================
"""
Este script demonstra o LawComplianceEngine em ação, validando
propostas de evolução contra as 15 Leis Universais.

Execução:
    python scripts/test_law_engine.py
"""

import sys
import json
from pathlib import Path

# Adiciona o root do projeto ao path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from iaglobal.core.law_engine import (
    law_compliance_engine,
    ComplianceStatus,
    LEIS_UNIVERSAIS,
)
from iaglobal.obsidian.omnimind import omni_mind


def print_header(title: str) -> None:
    """Imprime cabeçalho formatado."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_proposal(proposal_type: str, data: dict) -> None:
    """Imprime detalhes da proposta."""
    print(f"📋 Tipo: {proposal_type}")
    print(f"📄 Dados:")
    for key, value in list(data.items())[:5]:
        if isinstance(value, dict):
            print(f"   {key}: {json.dumps(value, indent=2)[:100]}...")
        else:
            print(f"   {key}: {value}")
    if len(data) > 5:
        print(f"   ... e mais {len(data) - 5} campos")
    print()


def print_report(report) -> None:
    """Imprime relatório de conformidade."""
    status_emoji = {
        ComplianceStatus.APPROVED: "✅",
        ComplianceStatus.REJECTED: "❌",
        ComplianceStatus.REQUIRES_REVISION: "⚠️",
    }
    
    print(f"Status: {status_emoji[report.status]} {report.status.value.upper()}")
    print(f"Score de Conformidade: {report.score_conformidade:.2f}")
    print(f"Leis Aplicadas: {len(report.leis_aplicadas)}")
    print(f"Violações: {len(report.violations)}")
    
    if report.violations:
        print("\n🔴 Violações Detectadas:")
        for i, v in enumerate(report.violations, 1):
            print(f"\n  {i}. {v.lei} (Severidade: {v.severidade}/5)")
            print(f"     Descrição: {v.descricao}")
            print(f"     Sugestão: {v.sugestao_correcao}")
    
    if report.orientacao_omnimind:
        print(f"\n💡 Orientação da OmniMind:")
        # Imprime com word wrap simples
        words = report.orientacao_omnimind.split()
        line = "   "
        for word in words:
            if len(line) + len(word) > 75:
                print(line)
                line = "   " + word + " "
            else:
                line += word + " "
        if line.strip():
            print(line)
    
    print()


def test_case_1_aprovado() -> None:
    """Caso 1: Proposta bem-formada que deve ser APROVADA."""
    print_header("CASO 1: Proposta Bem-Formada (Deve ser APROVADA)")
    
    proposal_data = {
        "reasoning": "Otimização de performance através de caching semântico",
        "justificativa": "Reduzir latência em 40% conforme métricas",
        "parent_version": "gen_5",
        "generation": 6,
        "strategy": "FastEvolutionStrategy",
        "mutation_rate": 0.15,
        "performance_metrics": {
            "latency_ms": 2500,  # Abaixo de 5000ms - OK
        },
        "resource_usage": {
            "nadph_reserve": 0.85,  # Acima de 0.3 - OK
        },
        "lineage_marker": "agent_x_gen5",
    }
    
    print_proposal("mutation", proposal_data)
    
    report = law_compliance_engine.validate_proposal(
        proposal_type="mutation",
        proposal_data=proposal_data,
        contexto={
            "agent_id": "test_agent_001",
            "generation": 6,
            "task": "Otimizar sistema de cache semântico",
        },
    )
    
    print_report(report)
    assert report.status == ComplianceStatus.APPROVED, "Caso 1 falhou!"
    print("✅ Caso 1 PASSED\n")


def test_case_2_rejeitado_sem_reasoning() -> None:
    """Caso 2: Proposta SEM reasoning deve ser REJEITADA/REVISÃO."""
    print_header("CASO 2: Proposta Sem Reasoning (Deve requerer revisão)")
    
    proposal_data = {
        # "reasoning" faltando - viola Lei do Pensamento
        "parent_version": "gen_5",
        "generation": 6,
        "strategy": "DeepEvolutionStrategy",
        "mutation_rate": 0.3,
    }
    
    print_proposal("mutation", proposal_data)
    
    report = law_compliance_engine.validate_proposal(
        proposal_type="mutation",
        proposal_data=proposal_data,
        contexto={
            "agent_id": "test_agent_002",
            "generation": 6,
        },
    )
    
    print_report(report)
    
    # Deve ter violação da Lei do Pensamento
    leis_violadas = [v.lei for v in report.violations]
    assert "Lei do Pensamento" in leis_violadas, "Deveria violar Lei do Pensamento!"
    print("✅ Caso 2 PASSED\n")


def test_case_3_novo_agente_incompleto() -> None:
    """Caso 3: Novo agente sem estrutura fractal deve ser REJEITADO."""
    print_header("CASO 3: Novo Agente Incompleto (Deve requerer revisão)")
    
    proposal_data = {
        "reasoning": "Criar novo agente especialista em segurança",
        "nome": "security_agent",
        # Faltam: geracao, linhagem, proposito, skills
    }
    
    print_proposal("new_agent", proposal_data)
    
    report = law_compliance_engine.validate_proposal(
        proposal_type="new_agent",
        proposal_data=proposal_data,
        contexto={
            "agent_id": "evolution_engine",
        },
    )
    
    print_report(report)
    
    # Deve ter violação da Lei da Correspondência
    leis_violadas = [v.lei for v in report.violations]
    assert "Lei da Correspondência" in leis_violadas, "Deveria violar Lei da Correspondência!"
    assert "Lei da Replicação" in leis_violadas, "Deveria violar Lei da Replicação!"
    print("✅ Caso 3 PASSED\n")


def test_case_4_homeostase_critica() -> None:
    """Caso 4: NADPH crítico deve ser REJEITADO imediatamente."""
    print_header("CASO 4: Reserva de NADPH Crítica (Deve ser REJEITADA)")
    
    proposal_data = {
        "reasoning": "Tentar evolução mesmo com recursos baixos",
        "parent_version": "gen_10",
        "generation": 11,
        "resource_usage": {
            "nadph_reserve": 0.05,  # Crítico! Abaixo de 0.1
        },
    }
    
    print_proposal("regeneration", proposal_data)
    
    report = law_compliance_engine.validate_proposal(
        proposal_type="regeneration",
        proposal_data=proposal_data,
        contexto={
            "agent_id": "homeostasis_controller",
        },
    )
    
    print_report(report)
    
    # Deve ser REJEITADO devido à severidade 5
    assert report.status == ComplianceStatus.REJECTED, "Deveria ser REJEITADO!"
    leis_violadas = [v.lei for v in report.violations]
    assert "Lei da Homeostase" in leis_violadas, "Deveria violar Lei da Homeostase!"
    print("✅ Caso 4 PASSED\n")


def test_case_5_memoria_imunologica() -> None:
    """Caso 5: Erro sem aprendizado extraído deve violar memória imunológica."""
    print_header("CASO 5: Erro Sem Aprendizado (Deve violar Memória Imunológica)")
    
    proposal_data = {
        "reasoning": "Registrar erro ocorrido",
        "error": "Timeout na API externa",
        "failure": "ConnectionError após 30s",
        # learning_extracted: False (faltando)
    }
    
    print_proposal("regeneration", proposal_data)
    
    report = law_compliance_engine.validate_proposal(
        proposal_type="regeneration",
        proposal_data=proposal_data,
        contexto={
            "agent_id": "failure_analyzer",
        },
    )
    
    print_report(report)
    
    leis_violadas = [v.lei for v in report.violations]
    assert "Lei da Memória Imunológica" in leis_violadas, "Deveria violar Lei da Memória Imunológica!"
    print("✅ Caso 5 PASSED\n")


def mostrar_estado_engine() -> None:
    """Mostra estado atual do engine."""
    print_header("ESTADO ATUAL DO LAW COMPLIANCE ENGINE")
    
    estado = law_compliance_engine.estado()
    print(f"Total de Propostas: {estado['total_proposals']}")
    print(f"Aprovadas: {estado['approved']}")
    print(f"Rejeitadas: {estado['rejected']}")
    print(f"Requerem Revisão: {estado['requires_revision']}")
    print(f"Taxa de Aprovação: {estado['approval_rate']:.1%}")
    print(f"Histórico (tamanho): {estado['historico_size']}")
    print()


def mostrar_historico() -> None:
    """Mostra histórico recente de auditoria."""
    print_header("HISTÓRICO RECENTE DE AUDITORIA")
    
    historico = law_compliance_engine.get_audit_history(limit=5)
    
    for i, entry in enumerate(historico, 1):
        status_emoji = {
            "approved": "✅",
            "rejected": "❌",
            "requires_revision": "⚠️",
        }
        emoji = status_emoji.get(entry["status"], "❓")
        print(f"{i}. {emoji} {entry['proposal_type']} | "
              f"Score: {entry['score_conformidade']:.2f} | "
              f"Violações: {len(entry['violations'])}")
    print()


def main() -> int:
    """Função principal."""
    print_header("🏛️ DEMONSTRAÇÃO: MOTOR DE CONFORMIDADE DAS LEIS UNIVERSAIS 🏛️")
    
    print(f"📜 Total de Leis Universais Carregadas: {len(LEIS_UNIVERSAIS)}\n")
    
    print("Leis Ativas:")
    for i, lei in enumerate(LEIS_UNIVERSAIS, 1):
        nome_lei = lei.split(":")[0] if ":" in lei else lei.split(".")[0]
        print(f"  {i:2d}. {nome_lei}")
    print()
    
    # Executa casos de teste
    test_case_1_aprovado()
    test_case_2_rejeitado_sem_reasoning()
    test_case_3_novo_agente_incompleto()
    test_case_4_homeostase_critica()
    test_case_5_memoria_imunologica()
    
    # Mostra estatísticas
    mostrar_estado_engine()
    mostrar_historico()
    
    print_header("🎉 TODOS OS TESTES PASSARAM! 🎉")
    print("\nO LawComplianceEngine está funcionando corretamente.")
    print("Ele garante que toda autoevolução e autorregeneração")
    print("respeite as 15 Leis Universais de Raymond Holliwell.\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
